from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitExceededError(Exception):
    """Raised when a caller exceeds the configured rate limit."""


class InMemoryRateLimiter:
    def __init__(self, *, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - 60

        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit_per_minute:
                raise RateLimitExceededError(f"Rate limit exceeded for {key}")

            bucket.append(now)
