import time
import sqlite3
import threading
import math
from .base import BaseLeakyBucketStorage

class SqliteLeakyBucketStorage(BaseLeakyBucketStorage):
    """
    Thread-safe SQLite-based storage for the async leaky bucket.
    Uses a table 'buckets' with columns:
      bucket_key TEXT PRIMARY KEY,
      level REAL,
      last_check REAL,
      hourly_count REAL,
      hourly_start REAL
    We make a 'BEGIN IMMEDIATE' transaction for concurrency control
    and retry if locked.
    
    ***This isn't a good choice for high-throughput applications.***
    """

    def __init__(
        self,
        db_path: str,
        bucket_key: str = "default_bucket",
        max_bucket_rate: float = 20.0,
        time_period: float = 60.0,
        max_hourly_level: float = math.inf,
        max_retries: int = 10,
        retry_sleep: float = 0.01
    ):
        super().__init__()
        self.db_path = db_path
        self.bucket_key = bucket_key
        self._max_level = max_bucket_rate
        self._rate_per_sec = max_bucket_rate / time_period
        self._max_hourly_level = max_hourly_level

        # concurrency control
        self._lock = threading.RLock()
        self._max_retries = max_retries
        self._retry_sleep = retry_sleep

        # init table and row
        self._init_table()
        self._init_bucket()

    @property
    def max_level(self) -> float:
        return self._max_level

    @property
    def rate_per_sec(self) -> float:
        return self._rate_per_sec

    def _init_table(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS buckets (
                    bucket_key TEXT PRIMARY KEY,
                    level REAL,
                    last_check REAL,
                    hourly_count REAL,
                    hourly_start REAL
                )
                """
            )
            conn.commit()

    def _init_bucket(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT bucket_key FROM buckets WHERE bucket_key = ?", (self.bucket_key,))
            row = c.fetchone()
            if not row:
                now = time.time()
                c.execute(
                    """
                    INSERT INTO buckets
                    (bucket_key, level, last_check, hourly_count, hourly_start)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (self.bucket_key, 0.0, now, 0.0, now)
                )
            conn.commit()

    def _transaction(self, callback):
        """
        Helper that runs `callback(conn, cursor)` inside a
        BEGIN IMMEDIATE transaction. Retries on lock.
        """
        for _ in range(self._max_retries):
            with self._lock:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.isolation_level = None  # manage transactions manually
                        c = conn.cursor()
                        c.execute("BEGIN IMMEDIATE")
                        result = callback(conn, c)
                        conn.commit()
                    return result
                except sqlite3.OperationalError as e:
                    # likely "database is locked"
                    time.sleep(self._retry_sleep)
                    continue
        raise RuntimeError("Failed to acquire SQLite lock after multiple retries")

    def _leak(self, conn, c):
        # Leak the bucket
        c.execute(
            "SELECT level, last_check FROM buckets WHERE bucket_key = ?",
            (self.bucket_key,)
        )
        row = c.fetchone()
        if not row:
            return
        current_level, last_check = row
        now = time.time()
        elapsed = now - last_check
        decrement = elapsed * self._rate_per_sec
        new_level = max(current_level - decrement, 0)
        c.execute(
            """
            UPDATE buckets
            SET level = ?, last_check = ?
            WHERE bucket_key = ?
            """,
            (new_level, now, self.bucket_key),
        )

    def _reset_hour_if_needed(self, conn, c):
        c.execute(
            "SELECT hourly_count, hourly_start FROM buckets WHERE bucket_key = ?",
            (self.bucket_key,)
        )
        row = c.fetchone()
        if not row:
            return
        hour_used, hour_start = row
        now = time.time()
        if now - hour_start >= 3600:
            # reset
            c.execute(
                """
                UPDATE buckets
                SET hourly_count = 0, hourly_start = ?
                WHERE bucket_key = ?
                """,
                (now, self.bucket_key)
            )

    def has_capacity(self, amount: float) -> bool:
        def _has_capacity(conn, c):
            self._reset_hour_if_needed(conn, c)

            # Check hourly_count
            c.execute(
                "SELECT hourly_count FROM buckets WHERE bucket_key = ?",
                (self.bucket_key,)
            )
            row = c.fetchone()
            if not row:
                return False
            hour_used = row[0]
            if hour_used >= self._max_hourly_level:
                return False

            # leak
            self._leak(conn, c)

            # check if we can add 'amount'
            c.execute(
                "SELECT level FROM buckets WHERE bucket_key = ?",
                (self.bucket_key,)
            )
            row = c.fetchone()
            if not row:
                return False
            current_level = row[0]
            requested = current_level + amount
            if requested <= self._max_level:
                # If capacity found, we can try to notify waiters outside
                # but we do not have an async event here. We'll just let the base call do that.
                return True
            return False

        return self._transaction(lambda conn, c: _has_capacity(conn, c))

    def increment_level(self, amount: float) -> None:
        def _increment_level(conn, c):
            # We also increment hourly usage
            c.execute(
                "SELECT level, hourly_count FROM buckets WHERE bucket_key = ?",
                (self.bucket_key,)
            )
            row = c.fetchone()
            if not row:
                return
            current_level, hour_used = row
            new_level = current_level + amount
            new_hour_used = hour_used + 1
            c.execute(
                """
                UPDATE buckets
                SET level = ?, hourly_count = ?
                WHERE bucket_key = ?
                """,
                (new_level, new_hour_used, self.bucket_key)
            )

        self._transaction(lambda conn, c: _increment_level(conn, c))
