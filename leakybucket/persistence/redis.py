import time
from typing import Callable
import redis
import math
from redis.exceptions import WatchError
from .base import BaseLeakyBucketStorage

class RedisLeakyBucketStorage(BaseLeakyBucketStorage):
    """
    Redis-based storage with watch/multi/exec for concurrency safety.
    """

    def __init__(
        self,
        redis_conn: redis.Redis,
        redis_key: str = "default_bucket",
        max_bucket_rate: float = 20.0,
        time_period: float = 60.0,
        max_hourly_level: float = math.inf,
        max_retries: int = 10,
        retry_sleep: float = 0.01
    ):
        super().__init__()
        self.redis = redis_conn
        self.key = f"lb:{redis_key}"
        self.hourly_key = f"{self.key}:hourly"
        self.last_check_key = f"{self.key}:last_check"

        self._max_level = max_bucket_rate
        self._rate_per_sec = max_bucket_rate / time_period
        self._max_hourly_level = max_hourly_level

        self._max_retries = max_retries
        self._retry_sleep = retry_sleep

        # Initialize the keys
        if not self.redis.get(self.key):
            self.redis.set(self.key, "0.0") # initial level
            
        if not self.redis.get(self.hourly_key):
            self.redis.set(self.hourly_key, "0")
            self.redis.expire(self.hourly_key, 60 * 60)  # 1 hour expiry
            
        if not self.redis.get(self.last_check_key):
            self.redis.set(self.last_check_key, str(time.time())) # initial time

    @property
    def max_level(self) -> float:
        return self._max_level

    @property
    def rate_per_sec(self) -> float:
        return self._rate_per_sec

    def _atomic_check_and_update(self, update_fn: Callable):
        """
        Helper that uses Redis WATCH / MULTI / EXEC to do an atomic
        read-modify-write cycle. Repeats on WatchError up to _max_retries times.
        
        The update_fn should take the args current level, hourly usage, and last check time
        and return a tuple of new values (new_level, new_hourly_usage, new_last_check).
        """
        for _ in range(self._max_retries):
            try:
                with self.redis.pipeline() as pipe:
                    # watch relevant keys
                    pipe.watch(self.key, self.hourly_key, self.last_check_key)

                    # read current values from redis
                    current_level = float(pipe.get(self.key) or "0")
                    last_check = float(pipe.get(self.last_check_key) or "0")
                    hour_used = float(pipe.get(self.hourly_key) or "0")

                    # run the custom logic, which returns the new values
                    new_values = update_fn(current_level, hour_used, last_check)

                    if new_values is None:
                        # means capacity check failed, do an un-watched reset
                        pipe.unwatch()
                        return None

                    # new_values = (new_level, new_hour_used, new_last_check)
                    new_level, new_hour_used, new_last_check = new_values

                    pipe.multi()
                    pipe.set(self.key, str(new_level))
                    pipe.set(self.hourly_key, str(new_hour_used))
                    pipe.set(self.last_check_key, str(new_last_check))
                    pipe.execute()  # attempt commit
                return new_values
            except WatchError:
                time.sleep(self._retry_sleep)
                continue
        raise RuntimeError("Failed to update Redis after max_retries due to concurrency conflicts")

    def has_capacity(self, amount: float) -> bool:
        """
        Returns True if there's enough capacity in the bucket and under hourly limit.
        """
        def update_fn(current_level, hour_used, last_check):
            # Hourly check
            if hour_used >= self._max_hourly_level:
                return None  # signals failure

            now = time.time()
            elapsed = now - last_check
            decrement = elapsed * self._rate_per_sec
            new_level = max(current_level - decrement, 0)

            requested = new_level + amount
            if requested <= self._max_level:
                # capacity is enough, proceed
                return (new_level, hour_used, now)  # update level, but DO NOT yet increment usage
            else:
                return None

        result = self._atomic_check_and_update(update_fn)
        if result is None:
            return False
        # If we got new_values, capacity is available
        self.maybe_notify_waiters()
        return True

    def increment_level(self, amount: float) -> None:
        """
        Actually increments the usage in the bucket + hourly usage.
        """
        def update_fn(current_level, hour_used, last_check):
            now = time.time()
            elapsed = now - last_check
            decrement = elapsed * self._rate_per_sec
            new_level = max(current_level - decrement, 0) + amount
            new_hour_used = hour_used + 1
            return (new_level, new_hour_used, now)

        self._atomic_check_and_update(update_fn)
