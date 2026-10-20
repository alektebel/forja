"""
Rate Limiter — From Scratch
============================
Build rate limiting algorithms to understand:
- Token bucket: smooth rate + burst tolerance
- Sliding window log: precise but memory-heavy
- Sliding window counter: memory-efficient approximation
- Fixed window counter: simple but boundary spikes
- Distributed rate limiting with shared state

Learning Path:
1. Implement fixed window counter (simplest)
2. Implement token bucket (most common in practice)
3. Implement sliding window log (most precise)
4. Implement sliding window counter (best trade-off)
5. Think about: how would you distribute this across N servers?
   - Use Redis INCR + EXPIRE (atomic counter)
   - Lua script for atomic check-and-increment
   - Consistent hashing to always route same key to same node
"""

import time
import threading
from collections import deque
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Step 1: Fixed Window Counter
# ---------------------------------------------------------------------------

class FixedWindowRateLimiter:
    """Simplest rate limiter: count requests per fixed time window.

    Problem: burst at window boundary (e.g. 100 reqs at 0:59 + 100 reqs at 1:01
    = 200 reqs in 2 seconds despite 100/min limit).

    TODO:
    - Track a counter and the start of the current window per key
    - On each request:
      1. Compute current window = int(now / window_size)
      2. If window changed, reset counter to 0
      3. Increment counter
      4. Allow if counter <= limit, deny otherwise
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: Dict[str, Tuple[int, int]] = {}  # key → (window_id, count)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited.

        TODO: implement fixed window check
        """
        # TODO: implement fixed window rate limiting
        raise NotImplementedError("Implement FixedWindowRateLimiter.is_allowed")


# ---------------------------------------------------------------------------
# Step 2: Token Bucket
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """Token bucket: tokens refill at a steady rate; requests consume tokens.

    Allows short bursts (up to bucket capacity) while enforcing average rate.
    Most common algorithm in practice (used by AWS, GCP APIs).

    TODO:
    - Each key has: tokens (float), last_refill_time
    - On each request:
      1. Compute elapsed = now - last_refill_time
      2. Add elapsed * refill_rate tokens (cap at capacity)
      3. Update last_refill_time = now
      4. If tokens >= 1: consume 1 token, allow
      5. Otherwise: deny
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: maximum number of tokens (burst size)
            refill_rate: tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key → (tokens, last_refill)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if request allowed (consumes 1 token), False if limited.

        TODO: implement token bucket check
        """
        # TODO: implement token bucket rate limiting
        raise NotImplementedError("Implement TokenBucketRateLimiter.is_allowed")


# ---------------------------------------------------------------------------
# Step 3: Sliding Window Log
# ---------------------------------------------------------------------------

class SlidingWindowLogRateLimiter:
    """Sliding window log: track exact timestamps of all recent requests.

    Most precise algorithm. Memory: O(requests_in_window) per key.
    Practical for low-volume or when precision matters (e.g. payment APIs).

    TODO:
    - Each key has a deque of timestamps
    - On each request:
      1. Remove timestamps older than (now - window_seconds)
      2. If len(deque) < limit: append now, allow
      3. Otherwise: deny
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._logs: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if allowed, False if rate-limited.

        TODO: implement sliding window log
        """
        # TODO: implement sliding window log rate limiting
        raise NotImplementedError("Implement SlidingWindowLogRateLimiter.is_allowed")


# ---------------------------------------------------------------------------
# Step 4: Sliding Window Counter
# ---------------------------------------------------------------------------

class SlidingWindowCounterRateLimiter:
    """Sliding window counter: blend of fixed windows, memory-efficient.

    Formula: estimated_count = prev_window_count * overlap_ratio + curr_window_count
    where overlap_ratio = fraction of prev window still in the sliding window.

    TODO:
    - Track counts for current and previous windows per key
    - On each request:
      1. current_window = int(now / window_size)
      2. If window advanced, shift: prev=curr count, curr=0, update window id
      3. elapsed_in_window = now % window_size
      4. overlap = 1 - (elapsed_in_window / window_size)
      5. estimated = prev_count * overlap + curr_count
      6. If estimated < limit: increment curr_count, allow
      7. Otherwise: deny
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        # key → (window_id, curr_count, prev_count)
        self._windows: Dict[str, Tuple[int, int, int]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if allowed, False if rate-limited.

        TODO: implement sliding window counter
        """
        # TODO: implement sliding window counter rate limiting
        raise NotImplementedError("Implement SlidingWindowCounterRateLimiter.is_allowed")


# ---------------------------------------------------------------------------
# Step 5: Distributed considerations (discussion)
# ---------------------------------------------------------------------------

"""
Distributed Rate Limiting:

Option A — Centralized Redis:
  - Store counter in Redis: INCR key; EXPIRE key window_seconds
  - Atomic with Lua script:
      local count = redis.call('INCR', KEYS[1])
      if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
      return count
  - Pro: exact counts; Con: Redis is a single point of failure

Option B — Local approximation:
  - Each server tracks locally; periodically sync to Redis
  - Pro: low latency; Con: may allow ~N * limit across N servers briefly

Option C — Sticky routing:
  - Consistent hashing → same user always hits same server
  - Pro: no coordination needed; Con: uneven load if users differ in traffic

Rate limit headers to return (HTTP):
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 37
  X-RateLimit-Reset: 1640000000   (Unix timestamp when window resets)
  Retry-After: 30                  (seconds until retry allowed, on 429)
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing FixedWindowRateLimiter...")
    lim = FixedWindowRateLimiter(limit=3, window_seconds=60)
    results = [lim.is_allowed("user1") for _ in range(5)]
    assert results[:3] == [True, True, True], f"first 3 should be allowed: {results}"
    assert results[3:] == [False, False], f"next 2 should be denied: {results}"
    print("  FixedWindowRateLimiter: OK")

    print("Testing TokenBucketRateLimiter...")
    lim = TokenBucketRateLimiter(capacity=3, refill_rate=1.0)
    results = [lim.is_allowed("user2") for _ in range(4)]
    assert results[:3] == [True, True, True], f"first 3 should be allowed: {results}"
    assert results[3] is False, f"4th should be denied: {results}"
    time.sleep(1.1)
    assert lim.is_allowed("user2") is True, "should allow after refill"
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
