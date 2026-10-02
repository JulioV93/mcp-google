from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitExceededError(Exception):
    """Raised when a caller exceeds the configured rate limit."""


class InMemoryRateLimiter:
    def __init__(self, *, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._buckets: dict[object, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: object) -> None:
        now = time.monotonic()
        cutoff = now - 60

        with self._lock:
            # ponytail: bounded per-process scan; use a shared limiter for multiple replicas.
            for inactive in [
                item for item, values in self._buckets.items() if not values or values[-1] <= cutoff
            ]:
                del self._buckets[inactive]
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit_per_minute:
                raise RateLimitExceededError("Rate limit exceeded")

            bucket.append(now)
