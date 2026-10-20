"""
Rate Limiter — Complete Solution
"""

import time
import threading
import random
from collections import deque
from typing import Dict, Tuple


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, Tuple[int, int]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            current_window = int(now / self.window_seconds)
            window_id, count = self._windows.get(key, (-1, 0))
            if window_id != current_window:
                count = 0
            if count >= self.limit:
                return False
            self._windows[key] = (current_window, count + 1)
            return True


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            tokens, last_refill = self._buckets.get(key, (float(self.capacity), now))
            elapsed = now - last_refill
            tokens = min(self.capacity, tokens + elapsed * self.refill_rate)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1.0, now)
            return True


class SlidingWindowLogRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._logs: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            log = self._logs.setdefault(key, deque())
            while log and log[0] <= cutoff:
                log.popleft()
            if len(log) >= self.limit:
                return False
            log.append(now)
            return True


class SlidingWindowCounterRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, Tuple[int, int, int]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            current_window = int(now / self.window_seconds)
            elapsed_in_window = now % self.window_seconds
            overlap = 1.0 - (elapsed_in_window / self.window_seconds)

            stored_window, curr_count, prev_count = self._windows.get(key, (current_window, 0, 0))

            if stored_window != current_window:
                if current_window - stored_window == 1:
                    prev_count = curr_count
                else:
                    prev_count = 0
                curr_count = 0
                stored_window = current_window

            estimated = prev_count * overlap + curr_count
            if estimated >= self.limit:
                self._windows[key] = (stored_window, curr_count, prev_count)
                return False
            self._windows[key] = (stored_window, curr_count + 1, prev_count)
            return True


def _test():
    print("Testing FixedWindowRateLimiter...")
    lim = FixedWindowRateLimiter(limit=3, window_seconds=60)
    results = [lim.is_allowed("user1") for _ in range(5)]
    assert results[:3] == [True, True, True]
    assert results[3:] == [False, False]
    print("  FixedWindowRateLimiter: OK")

    print("Testing TokenBucketRateLimiter...")
    lim = TokenBucketRateLimiter(capacity=3, refill_rate=1.0)
    results = [lim.is_allowed("user2") for _ in range(4)]
    assert results[:3] == [True, True, True]
    assert results[3] is False
    time.sleep(1.1)
    assert lim.is_allowed("user2") is True
    print("  TokenBucketRateLimiter: OK")

    print("Testing SlidingWindowLogRateLimiter...")
    lim = SlidingWindowLogRateLimiter(limit=3, window_seconds=60)
    results = [lim.is_allowed("user3") for _ in range(4)]
    assert results[:3] == [True, True, True]
    assert results[3] is False
    print("  SlidingWindowLogRateLimiter: OK")

    print("Testing SlidingWindowCounterRateLimiter...")
    lim = SlidingWindowCounterRateLimiter(limit=3, window_seconds=60)
    results = [lim.is_allowed("user4") for _ in range(4)]
    assert results[:3] == [True, True, True]
    assert results[3] is False
    print("  SlidingWindowCounterRateLimiter: OK")

    print("\nAll rate limiter tests passed!")


if __name__ == "__main__":
    _test()
