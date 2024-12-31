import time
import math
import threading
from .base import BaseLeakyBucketStorage

class InMemoryLeakyBucketStorage(BaseLeakyBucketStorage):
    """
    Thread-safe in-memory storage.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # current "bucket" level
        self._level = 0.0
        self._last_check = time.time()

        # hourly limit
        self._hourly_count = 0.0
        self._hourly_start = time.time()
        
        # # daily limit
        # self._daily_count = 0.0
        # self._daily_start = time.time()

        # concurrency lock for thread safety
        self._lock = threading.RLock()
        
    @property
    def max_level(self) -> float:
        return self._max_level
    
    @property
    def max_hourly_level(self) -> float:
        return self._max_hourly_level
    
    @property
    def max_daily_level(self) -> float:
        return self._max_daily_level
        
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
            self._reset_hour_if_needed()
            # If we've exceeded hourly limit, block
            if self._hourly_count >= self.max_hourly_level:
                return False
            
            self._leak()

            requested = self._level + amount
            if requested <= self.max_level:
                # Notify waiters if we have capacity
                self.maybe_notify_waiters()
                return True
            return False

    def increment_level(self, amount: float) -> None:
        with self._lock:
            # Increment both the current bucket usage and the hourly usage
            self._level += amount
            self._hourly_count += 1
