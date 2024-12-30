import abc
import asyncio
from typing import Dict


class BaseLeakyBucketStorage(abc.ABC):
    """
    Abstract base class that defines the interface required by the LeakyBucket.
    """

    def __init__(self):
        self._waiters: Dict[asyncio.Task, asyncio.Future] = {}

    @abc.abstractmethod
    def has_capacity(self, amount: float) -> bool:
        """Check if the requested capacity (amount) is currently available."""

    @abc.abstractmethod
    def increment_level(self, amount: float) -> None:
        """Increment the usage level in the storage by amount."""

    @abc.abstractproperty
    def max_level(self) -> float:
        """Return the maximum capacity for the bucket."""
    
    @abc.abstractproperty
    def rate_per_sec(self) -> float:
        """Return how quickly the bucket drains per second."""

    def add_waiter(self, task: asyncio.Task, fut: asyncio.Future):
        """
        Register a waiter (the waiting Future) so that if capacity becomes
        available earlier, we can wake the waiter sooner than a full timeout.
        """
        self._waiters[task] = fut

    def remove_waiter(self, task: asyncio.Task):
        """
        Remove a waiter from the queue after we finish waiting.
        """
        self._waiters.pop(task, None)

    def maybe_notify_waiters(self):
        """
        If capacity is now available, notify the earliest waiter(s).
        """
        for fut in self._waiters.values():
            if not fut.done():
                fut.set_result(True)
                # break after notifying the first waiter,
                # or continue if you want to notify all.
                break
