# Py Leaky Bucket

An implementation of the leaky bucket algorithm in python, with different persistence options for use in high throughput, multi process/worker applications. This is a useful package when managing integrations with various API's that have different rate limits.



## What's in it?

The package includes:

- **Leaky Bucket Algorithm**: A flexible rate-limiting algorithm that supports various persistence backends.
- **Persistence Backends**:
  - **In-Memory**: Fast, lightweight, and great for single-process applications.
  - **Redis**: Suitable for distributed, multi-worker environments.
  - **SQLite**: A file-based backend that supports high concurrency in single-node setups (honestly not the best option for high-throughput due to the nature of sqlite and the need to deadlock the database - better to use the redis option if possible)
- **Hourly Limit Support**: Control total operations over a rolling hourly window in addition to per-second rate limits.
- **Thread-Safe and Process-Safe**: Implements proper locking mechanisms to ensure safe concurrent usage.
- **Asynchronous and Synchronous**: Works in both `asyncio`-based and synchronous applications.
- **Decorators and Context Managers**: Simplify integration with your existing functions and methods.



### Installation

Easy to install:

```
pip install leaky-bucket-py
```



## Usage:



#### Redis backend with async bucket:

```python
import asyncio
import redis
from leakybucket.bucket import AsyncLeakyBucket
from leakybucket.persistence.redis import RedisLeakyBucketStorage

# Connect to Redis
redis_conn = redis.Redis(host='localhost', port=6379, db=0)

# Create a new Redis storage backend
storage = RedisLeakyBucketStorage(
    redis_conn,
    redis_key="api_bucket",
    max_rate=5,
    time_period=1
)

# Create a new LeakyBucket instance
bucket = AsyncLeakyBucket(storage)

# Make requests using the bucket as a context manager
async def make_requests():
    async def make_request():
        async with bucket:  # block if the rate limit is exceeded
            print("Making request")
            await asyncio.sleep(1)
    await asyncio.gather(*[make_request() for i in range(10)])


# or use a decorator to rate limit a coroutine
@bucket.throttle()
async def make_request(index):
    print(f"Making request {index}")
    await asyncio.sleep(1)


async def main():
    await make_requests()
    await asyncio.gather(*[make_request(i) for i in range(10)])


asyncio.run(main())
```



#### Memory backend:

###### Synchronous:

```python
import httpx
from leakybucket.bucket import LeakyBucket
from leakybucket.persistence.memory import InMemoryLeakyBucketStorage

# Create a new Memory storage backend (3 requests per second)
storage = InMemoryLeakyBucketStorage(max_rate=3, time_period=1)

# Create a new LeakyBucket instance
throttler = LeakyBucket(storage)

@throttler.throttle()
def fetch_data(api_url: str):
    response = httpx.get(api_url)
    data = response.json()
    print(data)
    return data

def main():
    # make multiple requests
    api_url = "https://jsonplaceholder.typicode.com/posts/1"
    results = []
    for _ in range(10):
        results.append(fetch_data(api_url))
    print(results)

main()

```

###### Asynchronous:

```python
import asyncio
import httpx
from leakybucket.bucket import AsyncLeakyBucket
from leakybucket.persistence.memory import InMemoryLeakyBucketStorage

# Create a new Memory storage backend (3 requests per second)
storage = InMemoryLeakyBucketStorage(max_rate=3, time_period=1)

# Create a new LeakyBucket instance
async_throttler = AsyncLeakyBucket(storage)

@async_throttler.throttle()
async def async_fetch_data(api_url):
    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        data = response.json()
        print(data)
        return data

async def main():
    # make multiple requests
    api_url = "https://jsonplaceholder.typicode.com/posts/1"
    tasks = [async_fetch_data(api_url) for _ in range(10)]
    results = await asyncio.gather(*tasks)
    print(results)

asyncio.run(main())

```



#### Sqlite backend:

```python
import time
from leakybucket.bucket import LeakyBucket
from leakybucket.persistence.sqlite import SqliteLeakyBucketStorage

# Create a shared SQLite bucket
bucket = LeakyBucket(
    SqliteLeakyBucketStorage(
        db_path="leakybucket.db", 
        max_rate=10, 
        time_period=10
    )
)

# Decorate the function
@bucket.throttle()
def make_request(index):
    print(f"Making request {index}")

def main():
    for i in range(35):
        make_request(i)

main()

```




