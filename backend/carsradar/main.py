import argparse
import logging

import uvicorn

from .api import create_app
from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Cars Radar server")
    parser.add_argument("--source", help="rtsp:// or srt:// stream URL, or a recorded video file")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()

    settings = Settings(**{k: v for k, v in vars(args).items() if v is not None})
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
