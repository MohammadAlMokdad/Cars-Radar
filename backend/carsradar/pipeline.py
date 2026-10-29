"""Per-frame processing loop: takes the newest decoded frame, runs the analysis stages, publishes a UI result."""

import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .common import Latest, RateMeter
from .config import Settings
from .detector import Detector
from .ingest import Frame, VideoSource
from .tracks import TrackRegistry

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Result:
    index: int
    pts: float
    width: int  # full-resolution frame size; track boxes are in these coordinates
    height: int
    jpeg: bytes  # downscaled frame for display
    tracks: list[dict]
    latency_ms: float  # decode → result published


class Pipeline:
    def __init__(self, source: VideoSource, settings: Settings) -> None:
        self.source = source
        self.settings = settings
        self.detector = Detector(settings)
        self.tracks = TrackRegistry()
        self.results: Latest[Result] = Latest()
        self.fps = RateMeter()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        last_index = 0
        while not self._stop.is_set():
            frame = self.source.frames.wait_newer(last_index, timeout=0.5)
            if frame is None:
                continue
            last_index = frame.index
            try:
                self.results.put(self._process(frame))
            except Exception:
                # One bad frame shouldn't freeze the live view; log it and move on to the next.
                log.exception("processing frame %d failed", frame.index)
                continue
            self.fps.tick()

    def _process(self, frame: Frame) -> Result:
        visible = self.tracks.update(self.detector.update(frame.image), frame.pts)
        height, width = frame.image.shape[:2]
        return Result(
            index=frame.index,
            pts=frame.pts,
            width=width,
            height=height,
            jpeg=encode_display_jpeg(frame.image, self.settings.display_width, self.settings.jpeg_quality),
            tracks=[state.to_ui() for state in visible],
            latency_ms=(time.monotonic() - frame.decoded_at) * 1000,
        )


def encode_display_jpeg(image: np.ndarray, max_width: int, quality: int) -> bytes:
    height, width = image.shape[:2]
    if width > max_width:
        image = cv2.resize(image, (max_width, round(height * max_width / width)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()
