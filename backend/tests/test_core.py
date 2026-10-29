import json
import threading
from dataclasses import dataclass

import numpy as np

from carsradar.api import pack_result
from carsradar.common import Latest
from carsradar.detector import Detection, crop_roi
from carsradar.pipeline import Result
from carsradar.tracks import MIN_HITS_TO_SHOW, TrackRegistry


@dataclass
class Item:
    index: int


def test_latest_returns_only_newer_items():
    box = Latest()
    assert box.wait_newer(0, timeout=0.01) is None
    box.put(Item(1))
    box.put(Item(2))
    assert box.wait_newer(0, timeout=0.01).index == 2  # the overwritten item 1 is skipped, not queued
    assert box.wait_newer(2, timeout=0.01) is None


def test_latest_wakes_waiting_reader():
    box = Latest()
    threading.Timer(0.05, box.put, args=(Item(1),)).start()
    assert box.wait_newer(0, timeout=2).index == 1


def test_crop_roi_offsets_map_back_to_full_frame():
    image = np.zeros((2160, 3840, 3), np.uint8)
    x0, y0, crop = crop_roi(image, (0.25, 0.5, 0.75, 1.0))
    assert (x0, y0) == (960, 1080)
    assert crop.shape[:2] == (1080, 1920)
    assert crop_roi(image, None)[2] is image


def test_track_registry_hides_new_tracks_then_forgets_stale_ones():
    registry = TrackRegistry(forget_after_s=1.0)
    car = Detection(7, (0, 0, 10, 10), "car", 0.9)
    for i in range(MIN_HITS_TO_SHOW - 1):
        assert registry.update([car], pts=i * 0.1) == []
    visible = registry.update([car], pts=0.5)
    assert [s.id for s in visible] == [7]

    registry.update([], pts=2.0)
    assert 7 not in registry.tracks


def test_track_class_is_majority_vote():
    registry = TrackRegistry()
    for i, cls in enumerate(["car", "truck", "car", "car"]):
        registry.update([Detection(1, (0, 0, 10, 10), cls, 0.9)], pts=i * 0.1)
    assert registry.tracks[1].cls == "car"


def test_pack_result_layout():
    result = Result(index=3, pts=1.5, width=3840, height=2160, jpeg=b"\xff\xd8jpeg", tracks=[], latency_ms=12.34)
    msg = pack_result(result, {"connected": True})
    n = int.from_bytes(msg[:4], "little")
    header = json.loads(msg[4 : 4 + n])
    assert header["index"] == 3 and header["width"] == 3840 and header["latency_ms"] == 12.3
    assert msg[4 + n :] == b"\xff\xd8jpeg"
