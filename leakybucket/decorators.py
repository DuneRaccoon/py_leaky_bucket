import functools
from typing import Callable, Any, Coroutine, Optional

from .bucket import LeakyBucket, AsyncLeakyBucket
from .persistence.base import BaseLeakyBucketStorage


def rate_limit(bucket: LeakyBucket, amount: float = 1.0):
    """
    Synchronous decorator that reuses an existing LeakyBucket instance.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bucket.acquire(amount=amount)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def a_rate_limit(bucket: AsyncLeakyBucket, amount: float = 1.0):
    """
    Asynchronous decorator that reuses an existing AsyncLeakyBucket instance.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await bucket.acquire(amount=amount)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def direct_rate_limit(
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


def a_direct_rate_limit(
    max_rate: float,
    time_period: float = 60.0,
    storage_cls=BaseLeakyBucketStorage,
    storage_kwargs: Optional[dict] = None,
    amount: float = 1.0,
):
    """
    Creates a new storage backend instance (by default in-memory)
    each time the decorator is defined. Typically not ideal if you
    have a lot of calls and need a persistent store (like Redis).
    """
    if storage_kwargs is None:
        storage_kwargs = {}

    storage = storage_cls(max_rate, time_period, **storage_kwargs)
    bucket = AsyncLeakyBucket(storage)

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await bucket.acquire(amount=amount)
            return await func(*args, **kwargs)
        return wrapper

    return decorator