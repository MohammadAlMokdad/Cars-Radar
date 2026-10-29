"""Per-car state that outlives a single frame. Later stages (speed, plate, color, make/model) attach to it."""

from collections import Counter
from dataclasses import dataclass, field

from .detector import Detection

# A track must be seen this many times before it's shown, which hides one-frame false positives.
MIN_HITS_TO_SHOW = 3


@dataclass
class TrackState:
    id: int
    first_pts: float
    last_pts: float
    box: tuple[float, float, float, float]
    hits: int = 0
    class_votes: Counter = field(default_factory=Counter)

    @property
    def cls(self) -> str:
        # The detector can flicker between car/truck on one vehicle; the majority over the track is stable.
        return self.class_votes.most_common(1)[0][0]

    def to_ui(self) -> dict:
        return {"id": self.id, "box": [round(v, 1) for v in self.box], "lines": [f"#{self.id} {self.cls}"]}


class TrackRegistry:
    def __init__(self, forget_after_s: float = 3.0) -> None:
        self.forget_after_s = forget_after_s
        self.tracks: dict[int, TrackState] = {}

    def update(self, detections: list[Detection], pts: float) -> list[TrackState]:
        """Fold this frame's detections in and return the tracks visible in it that are ready to show."""
        visible = []
        for det in detections:
            state = self.tracks.get(det.track_id)
            if state is None:
                state = self.tracks[det.track_id] = TrackState(det.track_id, pts, pts, det.box)
            state.box = det.box
            state.last_pts = pts
            state.hits += 1
            state.class_votes[det.cls] += 1
            if state.hits >= MIN_HITS_TO_SHOW:
                visible.append(state)

        self.tracks = {tid: s for tid, s in self.tracks.items() if pts - s.last_pts <= self.forget_after_s}
        return visible
