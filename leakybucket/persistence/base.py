import abc
import math
import asyncio
from typing import Dict


class BaseLeakyBucketStorage(abc.ABC):
    """
    Abstract base class that defines the interface required by the LeakyBucket.
    
    Supports both synchronous and asynchronous implementations.
    
    To ensure burst supported rate limiting, set the max_rate higher than the time_period. 
    For example, setting max_rate=3.0 and time_period=1.0 will immediately fill the bucket, and then slowly drip.
    Alternatively, if you set the max_rate=10.0 and time_period=10.0, the bucket will drip at a constant rate, with no burst.
    
    """

    def __init__(
        self, 
        max_rate: float = 20.0, 
        time_period: float = 60.0, 
        max_hourly_level: float = math.inf,
        max_daily_level: float = math.inf,
    ):
        """
        :param max_rate: The maximum rate of the bucket.
        :param time_period: The time period in seconds for the max rate.
        :param max_hourly_level: The maximum hourly rate.
        :param max_daily_level: The maximum daily rate. NOT IMPLEMENTED
        """
        self._max_level = max_rate
        self._rate_per_sec = max_rate / time_period
        self._max_hourly_level = max_hourly_level
        self._max_daily_level = max_daily_level
        self._waiters: Dict[asyncio.Task, asyncio.Future] = {}

    @abc.abstractmethod
    def has_capacity(self, amount: float) -> bool:
        """Check if the requested capacity (amount) is currently available."""

    @abc.abstractmethod
    def increment_level(self, amount: float) -> None:
        """Increment the usage level in the storage by amount."""

    @property
    @abc.abstractmethod
    def max_level(self) -> float:
        """Return the maximum capacity for the bucket."""
    
    @property
    @abc.abstractmethod
    def max_hourly_level(self) -> float:
        """Return the maximum hourly capacity for the bucket."""
    
    @property
    @abc.abstractmethod
    def max_daily_level(self) -> float:
        """Return the maximum daily capacity for the bucket."""
        
    @property
    @abc.abstractmethod
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
