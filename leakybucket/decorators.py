import functools
import time

from .bucket import LeakyBucket
from .persistence.base import BaseLeakyBucketStorage

def sync_rate_limit(
    max_rate: float,
    time_period: float = 60.0,
    storage_cls=BaseLeakyBucketStorage,
    storage_kwargs=None,
    amount: float = 1.0,
):
    """
    Synchronous decorator that creates a new storage instance
    each time the decorator is defined. 
    """
    if storage_kwargs is None:
        storage_kwargs = {}
    storage = storage_cls(max_rate, time_period, **storage_kwargs)
    bucket = LeakyBucket(storage)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bucket.acquire(amount=amount)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def sync_rate_limit_with_bucket(bucket: LeakyBucket, amount: float = 1.0):
    """
    Synchronous decorator that reuses an existing LeakyBucket instance.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bucket.acquire(amount=amount)
            return func(*args, **kwargs)
        return wrapper
    return decorator
