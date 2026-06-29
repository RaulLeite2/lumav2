from __future__ import annotations

import time
from collections import deque


class CommandRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._buckets: dict[tuple[int, str], deque[float]] = {}

    def allow(self, guild_id: int, command_name: str) -> tuple[bool, float]:
        now = time.monotonic()
        key = (guild_id, command_name)
        bucket = self._buckets.setdefault(key, deque())

        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(0.0, self.window_seconds - (now - bucket[0]))
            return False, retry_after

        bucket.append(now)
        return True, 0.0
