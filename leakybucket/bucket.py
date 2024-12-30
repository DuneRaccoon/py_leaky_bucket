import time
from .persistence.base import BaseLeakyBucketStorage

class LeakyBucket:
    """
    A simple synchronous leaky bucket that
    delegates to a (sync-friendly) storage backend.
    """

    def __init__(self, storage_backend: BaseLeakyBucketStorage):
        self._storage = storage_backend

    def acquire(self, amount: float = 1.0):
        if amount > self._storage.max_level:
            raise ValueError("Cannot acquire more than the bucket capacity")

        while not self._storage.has_capacity(amount):
            # simple sleep roughly for the drip interval:
            time.sleep(1 / self._storage.rate_per_sec * amount)
        self._storage.increment_level(amount)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None
