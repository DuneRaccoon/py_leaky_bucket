import time
import math
import threading
from .base import BaseLeakyBucketStorage

class InMemoryLeakyBucketStorage(BaseLeakyBucketStorage):
    """
    Thread-safe in-memory storage.
    Also supports an hourly max limit, resetting each hour.
    """
    def __init__(self, max_rate: float, time_period: float = 60, max_hourly_level: float = math.inf):
        super().__init__()
        self._max_level = max_rate
        self._rate_per_sec = max_rate / time_period

        # Current "bucket" level
        self._level = 0.0
        self._last_check = time.time()

        # Hourly limit
        self._max_hourly_level = max_hourly_level
        self._hourly_count = 0.0
        self._hourly_start = time.time()  # Track when we started the hour

        # Concurrency lock
        self._lock = threading.RLock()

    @property
    def max_level(self) -> float:
        return self._max_level

    @property
    def rate_per_sec(self) -> float:
        return self._rate_per_sec

    def _reset_hour_if_needed(self):
        """Reset the hourly counter if more than 1 hour has passed."""
        now = time.time()
        if now - self._hourly_start >= 3600:
            self._hourly_count = 0.0
            self._hourly_start = now

    def _leak(self) -> None:
        """Decrease _level according to time elapsed."""
        now = time.time()
        elapsed = now - self._last_check
        decrement = elapsed * self._rate_per_sec
        self._level = max(self._level - decrement, 0)
        self._last_check = now

    def has_capacity(self, amount: float) -> bool:
        with self._lock:
            # Check / reset hourly usage
            self._reset_hour_if_needed()
            # If we've exceeded hourly limit, block
            if self._hourly_count >= self._max_hourly_level:
                return False
            
            self._leak()

            requested = self._level + amount
            if requested <= self._max_level:
                # Notify waiters if we have capacity
                self.maybe_notify_waiters()
                return True
            return False

    def increment_level(self, amount: float) -> None:
        with self._lock:
            # Increment both the current bucket usage and the hourly usage
            self._level += amount
            self._hourly_count += 1
