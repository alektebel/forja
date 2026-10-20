"""
Circuit Breaker & Reliability Patterns — From Scratch
======================================================
Build reliability patterns to understand:
- Circuit breaker: prevent cascade failures by fast-failing to a failing dependency
- Retry with exponential backoff + jitter
- Timeout decorator
- Bulkhead: isolate resource pools to prevent one tenant from starving others
- Backpressure: bounded queues that reject when full

Learning Path:
1. Implement a timeout wrapper using threading
2. Implement retry with exponential backoff (from message_queue.py — reuse pattern)
3. Implement circuit breaker (CLOSED → OPEN → HALF-OPEN state machine)
4. Implement bulkhead using semaphores
5. Implement a bounded queue for backpressure
6. Think about: how would you implement these in a microservice framework?
"""

import time
import random
import threading
import functools
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Step 1: Timeout
# ---------------------------------------------------------------------------

class TimeoutError(Exception):
    pass


def with_timeout(seconds: float):
    """Decorator that raises TimeoutError if the wrapped function takes too long.

    TODO:
    1. Run the decorated function in a daemon thread
    2. Use thread.join(timeout=seconds)
    3. If still alive after timeout: raise TimeoutError
    4. If thread raised an exception: re-raise it
    5. Return the function's return value

    Hint: use a list to capture the result/exception from the thread.
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = [None]
            exc = [None]

            def target():
                try:
                    result[0] = fn(*args, **kwargs)
                except Exception as e:
                    exc[0] = e

            # TODO: start thread, join with timeout, check result
            raise NotImplementedError("Implement with_timeout decorator")

        return wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# Step 2: Retry with backoff
# ---------------------------------------------------------------------------

def retry(max_attempts: int = 3, base_delay: float = 0.5, cap_delay: float = 30.0,
          jitter: bool = True, exceptions: tuple = (Exception,)):
    """Decorator that retries the wrapped function on failure with exponential backoff.

    TODO:
    1. On each attempt, call the function
    2. If it succeeds, return the result
    3. If it raises an exception in `exceptions`:
       - If attempts exhausted, re-raise
       - Otherwise compute backoff delay and sleep
    4. Repeat

    Backoff formula: delay = min(cap_delay, base_delay * 2^attempt)
    With jitter: delay = random.uniform(0, delay)
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        # TODO: compute backoff delay and sleep
                        raise NotImplementedError("Implement retry backoff sleep")
            raise last_exc  # type: ignore
        return wrapper  # type: ignore
    return decorator


# ---------------------------------------------------------------------------
# Step 3: Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "CLOSED"        # normal operation; failures are counted
    OPEN = "OPEN"            # failing fast; no calls go through
    HALF_OPEN = "HALF_OPEN"  # probe: allow one call to test if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""
    pass


class CircuitBreaker:
    """Circuit breaker state machine.

    State transitions:
      CLOSED → OPEN:      failure_count >= failure_threshold within window
      OPEN → HALF_OPEN:   after recovery_timeout seconds have elapsed
      HALF_OPEN → CLOSED: probe call succeeds
      HALF_OPEN → OPEN:   probe call fails

    TODO:
    1. Initialize state=CLOSED, failure_count=0, last_failure_time=None
    2. Implement call(fn, *args, **kwargs):
       a. If OPEN: check if recovery_timeout elapsed → transition to HALF_OPEN
          Otherwise: raise CircuitBreakerOpenError
       b. If HALF_OPEN: allow exactly one probe call
          - On success: reset to CLOSED
          - On failure: back to OPEN, reset timer
       c. If CLOSED: call fn
          - On success: (optionally reset failure count on a long enough success streak)
          - On failure: increment failure_count; if >= threshold → OPEN
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0,
                 window_seconds: float = 60.0):
        """
        Args:
            failure_threshold: number of failures before opening
            recovery_timeout: seconds to wait before probing (OPEN → HALF_OPEN)
            window_seconds: failures older than this are ignored (rolling window)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """Execute fn through the circuit breaker.

        TODO: implement state machine transitions described above
        """
        # TODO: implement circuit breaker call
        raise NotImplementedError("Implement CircuitBreaker.call")

    def _record_success(self) -> None:
        """Handle a successful call.

        TODO: reset failure_count; if HALF_OPEN → transition to CLOSED
        """
        # TODO: implement _record_success
        raise NotImplementedError("Implement _record_success")

    def _record_failure(self) -> None:
        """Handle a failed call.

        TODO:
        - Increment failure_count, record last_failure_time
        - If failure_count >= threshold: transition to OPEN, record opened_at
        - If HALF_OPEN: transition back to OPEN
        """
        # TODO: implement _record_failure
        raise NotImplementedError("Implement _record_failure")

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._opened_at = None


# ---------------------------------------------------------------------------
# Step 4: Bulkhead
# ---------------------------------------------------------------------------

class Bulkhead:
    """Bulkhead pattern: limit concurrent calls to a dependency per caller/tenant.

    Prevents one misbehaving caller from exhausting all connections/threads.
    Uses a semaphore to cap concurrent inflight requests.

    TODO:
    1. Use a threading.Semaphore(max_concurrent) per key
    2. On call: acquire semaphore (with optional timeout)
    3. After call (success or failure): release semaphore
    """

    def __init__(self, max_concurrent: int = 10, timeout: float = 1.0):
        """
        Args:
            max_concurrent: max simultaneous calls allowed per key
            timeout: seconds to wait for a slot; raises if exceeded
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphores: dict = {}
        self._lock = threading.Lock()

    def _get_semaphore(self, key: str) -> threading.Semaphore:
        """Get or create a semaphore for this key."""
        # TODO: safely get-or-create semaphore
        raise NotImplementedError("Implement _get_semaphore")

    def call(self, key: str, fn: Callable, *args, **kwargs) -> Any:
        """Execute fn within the bulkhead for key.

        TODO:
        1. Get semaphore for key
        2. Try to acquire within self.timeout
        3. If not acquired: raise RuntimeError("Bulkhead full for {key}")
        4. Execute fn(*args, **kwargs)
        5. Release semaphore in finally block
        """
        # TODO: implement bulkhead call
        raise NotImplementedError("Implement Bulkhead.call")


# ---------------------------------------------------------------------------
# Step 5: Bounded Queue (Backpressure)
# ---------------------------------------------------------------------------

class BoundedQueue:
    """A bounded queue that applies backpressure by rejecting when full.

    Backpressure = signaling upstream to slow down when you're overwhelmed.
    Pattern: if queue is full, reject with error or block (configurable).

    TODO:
    - Use threading.Queue(maxsize=capacity)
    - put_nowait: raises if full (backpressure mode — reject)
    - get_nowait: raises if empty
    - put with timeout: block for a bit, then raise (soft backpressure)
    """

    def __init__(self, capacity: int):
        import queue
        self._queue = queue.Queue(maxsize=capacity)
        self.capacity = capacity
        self.rejected = 0

    def put(self, item: Any, block: bool = False, timeout: float = 0.0) -> bool:
        """Put an item in the queue.

        TODO:
        - If block=False: use put_nowait; on Full increment rejected, return False
        - If block=True: use put(timeout=timeout); on Full increment rejected, return False
        - Return True on success
        """
        import queue
        # TODO: implement put with backpressure
        raise NotImplementedError("Implement BoundedQueue.put")

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Any]:
        """Get an item from the queue, or None if empty/timeout."""
        import queue
        # TODO: implement get
        raise NotImplementedError("Implement BoundedQueue.get")

    @property
    def depth(self) -> int:
        return self._queue.qsize()


# ---------------------------------------------------------------------------
# Step 6: Graceful Degradation (discussion)
# ---------------------------------------------------------------------------

"""
Graceful Degradation Patterns:

1. Stale cache:
   - On DB timeout, return cached (possibly stale) data with a Cache-Control: stale header
   - Better than returning 500

2. Feature flags:
   - Disable expensive features under load (e.g., personalization, recommendations)
   - Return generic response instead

3. Fallback response:
   - If recommendations service is down, return popular items from local cache
   - If search is down, return an error message but keep the rest of the page working

4. Load shedding:
   - Check server CPU/queue depth; if overloaded, return 503 immediately
   - Include Retry-After header so clients back off
   - Prioritize: shed background jobs first, then low-priority user requests

5. Multi-AZ:
   - Deploy in 3 AZs; use weighted health-check routing
   - On AZ failure: shift traffic to remaining AZs (2x load → ensure 2x capacity headroom)
   - Database: synchronous replica in same region AZ-2; async replica cross-region
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing with_timeout...")
    @with_timeout(0.1)
    def slow():
        time.sleep(1.0)

    @with_timeout(1.0)
    def fast():
        return 42

    try:
        slow()
        assert False, "should have raised TimeoutError"
    except TimeoutError:
        pass
    assert fast() == 42
    print("  with_timeout: OK")

    print("Testing retry...")
    call_count = [0]

    @retry(max_attempts=3, base_delay=0.01, jitter=False)
    def flaky():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("transient error")
        return "ok"

    result = flaky()
    assert result == "ok"
    assert call_count[0] == 3
    print("  retry: OK")

    print("Testing CircuitBreaker...")
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED

    def failing_fn():
        raise ConnectionError("service down")

    def ok_fn():
        return "ok"

    # Trigger failures to open circuit
    for _ in range(3):
        try:
            cb.call(failing_fn)
        except ConnectionError:
            pass

    assert cb.state == CircuitState.OPEN, f"circuit should be OPEN, got {cb.state}"

    # Circuit open → fast fail
    try:
        cb.call(ok_fn)
        assert False, "should raise CircuitBreakerOpenError"
    except CircuitBreakerOpenError:
        pass

    # Wait for recovery timeout
    time.sleep(0.25)

    # Should transition to HALF_OPEN and succeed
    result = cb.call(ok_fn)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED, f"circuit should be CLOSED after probe, got {cb.state}"
    print("  CircuitBreaker: OK")

    print("Testing Bulkhead...")
    bulkhead = Bulkhead(max_concurrent=2, timeout=0.1)

    results = []
    errors = []

    def slow_task():
        time.sleep(0.2)
        return "done"

    def run(key):
        try:
            r = bulkhead.call(key, slow_task)
            results.append(r)
        except RuntimeError as e:
            errors.append(str(e))

    threads = [threading.Thread(target=run, args=("tenant-A",)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 2, f"only 2 should succeed (got {len(results)})"
    assert len(errors) == 2, f"2 should be rejected (got {len(errors)})"
    print("  Bulkhead: OK")

    print("Testing BoundedQueue (backpressure)...")
    q = BoundedQueue(capacity=2)
    assert q.put("a") is True
    assert q.put("b") is True
    assert q.put("c") is False   # rejected — queue full
    assert q.rejected == 1
    assert q.get() == "a"
    print("  BoundedQueue: OK")

    print("\nAll reliability pattern tests passed!")


if __name__ == "__main__":
    _test()
