import threading
import time
from typing import Generic, Protocol, TypeVar


class Indexed(Protocol):
    index: int


T = TypeVar("T", bound=Indexed)


class Latest(Generic[T]):
    """Single-slot mailbox: writers overwrite, readers wait for an item newer than the one they last saw.

    Slow readers skip items instead of building a backlog, which is what a live view wants.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._item: T | None = None

    def put(self, item: T) -> None:
        with self._cond:
            self._item = item
            self._cond.notify_all()

    def peek(self) -> T | None:
        with self._cond:
            return self._item

    def wait_newer(self, last_index: int, timeout: float) -> T | None:
        with self._cond:
            self._cond.wait_for(lambda: self._item is not None and self._item.index > last_index, timeout)
            item = self._item
            return item if item is not None and item.index > last_index else None


class RateMeter:
    """Exponentially smoothed events-per-second counter."""

    def __init__(self, smoothing: float = 0.9) -> None:
        self.smoothing = smoothing
        self.rate = 0.0
        self._last: float | None = None

    def tick(self) -> None:
        now = time.monotonic()
        if self._last is not None and now > self._last:
            instant = 1.0 / (now - self._last)
            self.rate = instant if self.rate == 0 else self.smoothing * self.rate + (1 - self.smoothing) * instant
        self._last = now

    def reset(self) -> None:
        self.rate = 0.0
        self._last = None
