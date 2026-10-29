"""Vehicle detection (Ultralytics YOLO) and tracking (ByteTrack) on full-resolution frames."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import YAML, IterableSimpleNamespace

from .config import DATA_DIR, Settings

# COCO classes the stock model already detects.
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
TRACKER_CONFIG = Path(__file__).with_name("bytetrack.yaml")
MODELS_DIR = DATA_DIR / "models"


@dataclass(frozen=True)
class Detection:
    track_id: int
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in full-frame pixels
    cls: str
    conf: float


class Detector:
    def __init__(self, settings: Settings) -> None:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.model = YOLO(MODELS_DIR / settings.model)
        self.imgsz = settings.imgsz
        self.conf = settings.conf
        self.roi = settings.roi
        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.precision = 16 if self.device != "cpu" else 32
        # Driven directly rather than via model.track(): that path replaces each box with the tracker's
        # Kalman estimate, which visibly trails fast cars. Here the tracker only assigns IDs.
        self.tracker = BYTETracker(IterableSimpleNamespace(**YAML.load(TRACKER_CONFIG)))

    def update(self, image: np.ndarray) -> list[Detection]:
        x0, y0, crop = crop_roi(image, self.roi)
        result = self.model.predict(
            crop,
            classes=list(VEHICLE_CLASSES),
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            quantize=self.precision,
            verbose=False,
        )[0]
        boxes = result.boxes.cpu().numpy()
        tracks = self.tracker.update(boxes, crop)
        if len(tracks) == 0:
            return []

        detections = []
        for track_id, idx in zip(tracks[:, 4].astype(int), tracks[:, -1].astype(int)):
            x1, y1, x2, y2 = boxes.xyxy[idx].tolist()
            cls = VEHICLE_CLASSES[int(boxes.cls[idx])]
            detections.append(Detection(int(track_id), (x1 + x0, y1 + y0, x2 + x0, y2 + y0), cls, float(boxes.conf[idx])))
        return detections


def crop_roi(
    image: np.ndarray, roi: tuple[float, float, float, float] | None
) -> tuple[int, int, np.ndarray]:
    """Crop to the road region (fractions of width/height) so the model's input pixels go to the street."""
    if roi is None:
        return 0, 0, image
    height, width = image.shape[:2]
    x1, y1, x2, y2 = round(roi[0] * width), round(roi[1] * height), round(roi[2] * width), round(roi[3] * height)
    return x1, y1, image[y1:y2, x1:x2]
