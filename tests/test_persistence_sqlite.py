import asyncio
import time
import os
import pytest
from leakybucket.bucket import LeakyBucket
from leakybucket.persistence.sqlite import SqliteLeakyBucketStorage
from leakybucket.decorators import sync_rate_limit, sync_rate_limit_with_bucket
from leakybucket.decorators_async import async_rate_limit, async_rate_limit_with_bucket


def test_sqlite_storage():
    storage = SqliteLeakyBucketStorage(
        db_path="test_bucket.db",
        bucket_key="test",
        max_bucket_rate=5,
        time_period=5,
        max_hourly_level=10,
    )

    # Initially, bucket should have capacity
    assert storage.has_capacity(1)

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
    

def test_sync_leaky_bucket_sqlite():
    storage = SqliteLeakyBucketStorage(
        db_path="test_bucket.db", bucket_key="test", max_bucket_rate=5, time_period=5
    )
    bucket = LeakyBucket(storage)

    def make_request():
        with bucket:
            return "success"

    # Make multiple requests within rate limit
    results = [make_request() for _ in range(5)]
    assert results == ["success"] * 5

    # Exceed rate limit
    with pytest.raises(RuntimeError):
        with bucket:
            pass  # Should block indefinitely (simulate timeout)

def test_sync_decorator_sqlite():
    storage = SqliteLeakyBucketStorage(
        db_path="test_bucket.db", bucket_key="test", max_bucket_rate=5, time_period=5
    )
    bucket = LeakyBucket(storage)

    @sync_rate_limit_with_bucket(bucket)
    def make_request(index):
        return f"success {index}"

    # Make multiple requests within rate limit
    results = [make_request(i) for i in range(5)]
    assert results == [f"success {i}" for i in range(5)]

    # Exceed rate limit
    with pytest.raises(RuntimeError):
        make_request(6)

def teardown_module(module):
    """Cleanup after tests."""
    if os.path.exists("test_bucket.db"):
        os.remove("test_bucket.db")
