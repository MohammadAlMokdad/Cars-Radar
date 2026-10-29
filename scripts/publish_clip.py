"""Push a recorded clip into MediaMTX in real time, standing in for the phone so the live path can be tested.

    uv --directory backend run python ../scripts/publish_clip.py ../data/clips/street.mp4
"""

import argparse
import time

import av


def publish_once(clip: str, url: str) -> None:
    with av.open(clip) as src, av.open(url, mode="w", format="rtsp", options={"rtsp_transport": "tcp"}) as dst:
        in_stream = src.streams.video[0]
        out_stream = dst.add_stream_from_template(in_stream)
        start = time.monotonic()
        first_dts = None
        for packet in src.demux(in_stream):
            if packet.dts is None:
                continue
            if first_dts is None:
                first_dts = packet.dts
            wait = float((packet.dts - first_dts) * in_stream.time_base) - (time.monotonic() - start)
            if wait > 0:
                time.sleep(wait)
            packet.stream = out_stream
            dst.mux(packet)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("clip")
    parser.add_argument("--url", default="rtsp://127.0.0.1:8554/live/cam")
    parser.add_argument("--once", action="store_true", help="stop at the end instead of looping")
    args = parser.parse_args()

    while True:
        publish_once(args.clip, args.url)
        if args.once:
            break


if __name__ == "__main__":
    main()
