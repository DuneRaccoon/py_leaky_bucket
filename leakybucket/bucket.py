import time
import asyncio
import functools
from typing import Callable, Any, Coroutine, Optional
from .persistence.base import BaseLeakyBucketStorage

_current_task = asyncio.current_task

class LeakyBucket:
    """
    A simple synchronous leaky bucket that
    delegates to a (sync-friendly) storage backend.
    """

    def __init__(self, storage_backend: BaseLeakyBucketStorage):
        self._storage = storage_backend

    def acquire(self, amount: float = 1.0):
        """
        Acquire the requested amount of capacity from the bucket.
        This can be called explicitly, or used as a context manager.
        """
        if amount > self._storage.max_level:
            raise ValueError("Cannot acquire more than the bucket capacity")

        while not self._storage.has_capacity(amount):
            # simple sleep roughly for the drip interval:
            time.sleep(1 / self._storage.rate_per_sec * amount)
        self._storage.increment_level(amount)
        
    def throttle(self, amount: float = 1.0):
        """
        Synchronous decorator
        
        Usage:
            ```python
            bucket = LeakyBucket(storage)
            
            @bucket.throttle()
            def func():
                print("Hello, world!")
            ```
        """
        def decorator(func: Callable[..., Any]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                self.acquire(amount=amount)
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None


class AsyncLeakyBucket:
    """
    An async leaky bucket that delegates storage to a BaseLeakyBucketStorage implementation.
    """

    def __init__(self, storage_backend: BaseLeakyBucketStorage):
        self._storage = storage_backend

    async def acquire(self, amount: float = 1.0) -> None:
        """
        Acquire the requested amount of capacity from the bucket.
        This can be called explicitly, or used as an async context manager.
        """
        loop = asyncio.get_event_loop()
        task = _current_task(loop)
        if amount > self._storage.max_level:
            raise ValueError("Cannot acquire more than the bucket capacity")

        while not self._storage.has_capacity(amount):
            fut = loop.create_future()
            self._storage.add_waiter(task, fut)
            try:
                # Wait for capacity or time out after ~the drip interval
                await asyncio.wait_for(
                    asyncio.shield(fut),
                    1 / self._storage.rate_per_sec * amount,
                )
            except asyncio.TimeoutError:
                pass
            finally:
                self._storage.remove_waiter(task)
        self._storage.increment_level(amount)

    def throttle(self, amount: float = 1.0):
        """
        Asynchronous decorator
        
        Usage:
            ```python
            bucket = AsyncLeakyBucket(storage)
            
            @bucket.throttle()
            async def func():
                print("Hello, world!")
            ```
        """
        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                await self.acquire(amount=amount)
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None