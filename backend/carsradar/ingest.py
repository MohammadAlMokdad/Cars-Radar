"""Video input: a live stream (the phone via MediaMTX) or a recorded clip, decoded on a background thread."""

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import av
import numpy as np

from .common import Latest, RateMeter

log = logging.getLogger(__name__)

RECONNECT_DELAY_S = 2.0

# Keep ffmpeg from buffering: the pipeline always wants the newest frame, not a smooth backlog.
LOW_LATENCY_OPTIONS = {"fflags": "nobuffer", "flags": "low_delay"}


@dataclass(frozen=True)
class Frame:
    image: np.ndarray  # BGR, full resolution
    pts: float  # seconds on the stream's clock, kept monotonic across file loops and reconnects
    index: int  # increasing counter assigned by the source
    decoded_at: float = field(default_factory=time.monotonic)


class VideoSource:
    """Decodes `url` forever, publishing each frame to `frames`. Live streams reconnect; files loop.

    Recorded clips are replayed at real-time pace so the rest of the pipeline sees them exactly
    as it would see the phone: frames it can't keep up with are dropped, not queued.
    """

    def __init__(self, url: str, loop_file: bool = True) -> None:
        self.url = url
        self.is_file = Path(url).is_file()
        self.loop_file = loop_file
        self.frames: Latest[Frame] = Latest()
        self.fps = RateMeter()
        self.connected = False
        self.resolution: tuple[int, int] | None = None
        self._index = 0
        self._pts_offset = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="video-source", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._decode_until_end()
            except (av.FFmpegError, OSError) as exc:
                log.warning("video source %s: %s", self.url, exc)
            self.connected = False
            self.fps.reset()
            if self.is_file and not self.loop_file:
                break
            self._stop.wait(0 if self.is_file else RECONNECT_DELAY_S)

    def _decode_until_end(self) -> None:
        options = {} if self.is_file else dict(LOW_LATENCY_OPTIONS)
        if self.url.startswith("rtsp://"):
            options["rtsp_transport"] = "tcp"

        with av.open(self.url, options=options, timeout=(10.0, 5.0)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            frame_duration = 1.0 / float(stream.average_rate) if stream.average_rate else 1 / 30
            log.info("opened %s (%sx%s, %s)", self.url, stream.width, stream.height, stream.codec_context.name)
            self.connected = True

            first_pts: float | None = None
            elapsed = 0.0
            wall_start = time.monotonic()
            for av_frame in container.decode(stream):
                if self._stop.is_set():
                    return
                # Joining a live stream mid-GOP yields grey smeared frames until the next keyframe; skip them.
                if av_frame.time is None or av_frame.is_corrupt or (first_pts is None and not av_frame.key_frame):
                    continue
                if first_pts is None:
                    first_pts = av_frame.time
                elapsed = av_frame.time - first_pts

                if self.is_file:
                    delay = wall_start + elapsed - time.monotonic()
                    if delay > 0 and self._stop.wait(delay):
                        return

                image = av_frame.to_ndarray(format="bgr24")
                self.resolution = (image.shape[1], image.shape[0])
                self._index += 1
                self.frames.put(Frame(image=image, pts=self._pts_offset + elapsed, index=self._index))
                self.fps.tick()

            # Continue the clock past the end so pts never goes backwards when a clip loops.
            self._pts_offset += elapsed + frame_duration
