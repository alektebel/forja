"""
Circuit Breaker & Reliability Patterns — Complete Solution
"""

import time
import random
import threading
import functools
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class TimeoutError(Exception):
    pass


def with_timeout(seconds: float):
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

            t = threading.Thread(target=target, daemon=True)
            t.start()
            t.join(timeout=seconds)
            if t.is_alive():
                raise TimeoutError(f"Function timed out after {seconds}s")
            if exc[0]:
                raise exc[0]
            return result[0]

        return wrapper  # type: ignore
    return decorator


def retry(max_attempts: int = 3, base_delay: float = 0.5, cap_delay: float = 30.0,
          jitter: bool = True, exceptions: tuple = (Exception,)):
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
                        raw = min(cap_delay, base_delay * (2 ** attempt))
                        delay = random.uniform(0, raw) if jitter else raw
                        time.sleep(delay)
            raise last_exc  # type: ignore
        return wrapper  # type: ignore
    return decorator


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0,
                 window_seconds: float = 60.0):
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
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._opened_at >= self.recovery_timeout:  # type: ignore
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError("Circuit is OPEN")

        try:
            result = fn(*args, **kwargs)
            self._record_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception:
            self._record_failure()
            raise

    def _record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._last_failure_time = None
            self._state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN or \
               self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._opened_at = None


class Bulkhead:
    def __init__(self, max_concurrent: int = 10, timeout: float = 1.0):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphores: Dict[str, threading.Semaphore] = {}
        self._lock = threading.Lock()

    def _get_semaphore(self, key: str) -> threading.Semaphore:
        with self._lock:
            if key not in self._semaphores:
                self._semaphores[key] = threading.Semaphore(self.max_concurrent)
            return self._semaphores[key]

    def call(self, key: str, fn: Callable, *args, **kwargs) -> Any:
        sem = self._get_semaphore(key)
        acquired = sem.acquire(timeout=self.timeout)
        if not acquired:
            raise RuntimeError(f"Bulkhead full for {key}")
        try:
            return fn(*args, **kwargs)
        finally:
            sem.release()


class BoundedQueue:
    def __init__(self, capacity: int):
        import queue
        self._queue = queue.Queue(maxsize=capacity)
        self.capacity = capacity
        self.rejected = 0

    def put(self, item: Any, block: bool = False, timeout: float = 0.0) -> bool:
        import queue
        try:
            if block:
                self._queue.put(item, block=True, timeout=timeout)
            else:
                self._queue.put_nowait(item)
            return True
        except queue.Full:
            self.rejected += 1
            return False

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Any]:
        import queue
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    @property
    def depth(self) -> int:
        return self._queue.qsize()


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
        assert False
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

    assert flaky() == "ok"
    assert call_count[0] == 3
    print("  retry: OK")

    print("Testing CircuitBreaker...")
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED

    def failing_fn():
        raise ConnectionError("service down")

    def ok_fn():
        return "ok"

    for _ in range(3):
        try:
            cb.call(failing_fn)
        except ConnectionError:
            pass

    assert cb.state == CircuitState.OPEN

    try:
        cb.call(ok_fn)
        assert False
    except CircuitBreakerOpenError:
        pass

    time.sleep(0.25)
    result = cb.call(ok_fn)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED
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

    assert len(results) == 2
    assert len(errors) == 2
    print("  Bulkhead: OK")

    print("Testing BoundedQueue...")
    q = BoundedQueue(capacity=2)
    assert q.put("a") is True
    assert q.put("b") is True
    assert q.put("c") is False
    assert q.rejected == 1
    assert q.get() == "a"
    print("  BoundedQueue: OK")

    print("\nAll reliability pattern tests passed!")


if __name__ == "__main__":
    _test()
