from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    """Runtime settings. Each field can be overridden by a CARSRADAR_<NAME> env var, the .env file, or the CLI."""

    model_config = SettingsConfigDict(env_prefix="CARSRADAR_", env_file=ROOT_DIR / ".env", extra="ignore")

    # rtsp:// or srt:// stream URL (MediaMTX re-serves the phone's SRT feed as RTSP), or a recorded clip path.
    source: str = "rtsp://127.0.0.1:8554/live/cam"
    loop_file: bool = True

    host: str = "127.0.0.1"
    port: int = 8000

    # Frames are downscaled to this width before going to the browser; detection always uses full resolution.
    display_width: int = 1600
    jpeg_quality: int = 80

    # Detector weights (downloaded into data/models on first run), input size and confidence threshold.
    model: str = "yolo26s.pt"
    imgsz: int = 1280
    conf: float = 0.25
    # Road region as fractions of the frame (x1, y1, x2, y2), e.g. [0, 0.3, 1, 0.8]; None = whole frame.
    roi: tuple[float, float, float, float] | None = None
