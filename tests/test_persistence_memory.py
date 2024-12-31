import asyncio
import time
import pytest
from leakybucket.bucket import AsyncLeakyBucket
from leakybucket.persistence.memory import InMemoryLeakyBucketStorage
from leakybucket.decorators import (
    rate_limit,
    a_rate_limit,
    direct_rate_limit,
    a_direct_rate_limit,
)

def test_memory_storage():
    storage = InMemoryLeakyBucketStorage(max_rate=5, time_period=5, max_hourly_level=10)
    
    assert storage.has_capacity(1) # Initially, bucket should have capacity

    # Increment usage
    storage.increment_level(1)
    assert not storage.has_capacity(5)  # Shouldn't allow more than max rate
    assert storage.has_capacity(3)  # Remaining capacity

    # Exceed hourly limit
    for _ in range(10):
        storage.increment_level(1)
    assert not storage.has_capacity(1)  # Hourly limit exceeded

    # Simulate passage of time to "leak" capacity
    time.sleep(6)
    assert storage.has_capacity(1)  # Now it has capacity again
    
@pytest.mark.asyncio
async def test_async_leaky_bucket_memory():
    storage = InMemoryLeakyBucketStorage(max_rate=5, time_period=5)
    bucket = AsyncLeakyBucket(storage)

    async def make_request():
        async with bucket:
            return "success"

    # Make multiple requests within rate limit
    tasks = [make_request() for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert results == ["success"] * 5

    # Exceed rate limit
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire(), timeout=1)
    
@pytest.mark.asyncio
async def test_async_decorator_memory():
    storage = InMemoryLeakyBucketStorage(max_rate=5, time_period=5)
    bucket = AsyncLeakyBucket(storage)

    @a_rate_limit(bucket)
    async def make_request(index):
        return f"success {index}"

    # Make multiple requests within rate limit
    tasks = [make_request(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    assert results == [f"success {i}" for i in range(5)]

    # Exceed rate limit
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bucket.acquire(), timeout=1)
