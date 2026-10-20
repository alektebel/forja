"""
Throttling — Complete Solution
"""

import time
import threading
import queue
from typing import Any, Callable, Optional


class LeakyBucket:
    def __init__(self, capacity: float, drain_rate: float):
        self.capacity = capacity
        self.drain_rate = drain_rate
        self._level: float = 0.0
        self._last_leak: float = time.time()
        self._lock = threading.Lock()

    def add(self, amount: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_leak
            self._level = max(0.0, self._level - elapsed * self.drain_rate)
            self._last_leak = now
            if self._level + amount > self.capacity:
                return False
            self._level += amount
            return True

    @property
    def level(self) -> float:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_leak
            return max(0.0, self._level - elapsed * self.drain_rate)


class DelayThrottler:
    def __init__(self, rate: float, window_seconds: float = 1.0):
        self.interval = window_seconds / rate
        self._next_allowed: dict = {}
        self._lock = threading.Lock()

    def throttle(self, key: str) -> float:
        with self._lock:
            now = time.time()
            allowed_at = max(now, self._next_allowed.get(key, now))
            self._next_allowed[key] = allowed_at + self.interval
        sleep_time = allowed_at - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
        return max(0.0, sleep_time)


class ThrottledWorker:
    def __init__(self, rate: float, queue_size: int = 100):
        self.rate = rate
        self._interval = 1.0 / rate
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._results: dict = {}
        self._task_counter = 0
        self._start_worker()

    def _start_worker(self) -> None:
        t = threading.Thread(target=self._worker_loop, daemon=True)
        t.start()

    def _worker_loop(self) -> None:
        while True:
            task_id, fn, args = self._queue.get()
            try:
                result = fn(*args)
            except Exception as e:
                result = e
            with self._lock:
                self._results[task_id] = result
            time.sleep(self._interval)

    def submit(self, fn: Callable, *args: Any) -> int:
        with self._lock:
            self._task_counter += 1
            task_id = self._task_counter
        self._queue.put((task_id, fn, args))
        return task_id

    def get_result(self, task_id: int, timeout: float = 5.0) -> Any:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if task_id in self._results:
                    return self._results.pop(task_id)
            time.sleep(0.01)
        raise TimeoutError(f"task {task_id} did not complete in {timeout}s")


def _test():
    print("Testing LeakyBucket...")
    bucket = LeakyBucket(capacity=3.0, drain_rate=1.0)
    results = [bucket.add(1.0) for _ in range(4)]
    assert results[:3] == [True, True, True]
    assert results[3] is False
    time.sleep(2.1)
    assert bucket.add(2.0) is True
    print("  LeakyBucket: OK")

    print("Testing DelayThrottler...")
    throttler = DelayThrottler(rate=10.0)
    start = time.time()
    throttler.throttle("user1")
    throttler.throttle("user1")
    elapsed = time.time() - start
    assert elapsed >= 0.09
    print("  DelayThrottler: OK")

    print("Testing ThrottledWorker...")
    worker = ThrottledWorker(rate=20.0)
    task_ids = [worker.submit(lambda x: x * 2, i) for i in range(3)]
    results_list = [worker.get_result(tid, timeout=5.0) for tid in task_ids]
    assert results_list == [0, 2, 4]
    print("  ThrottledWorker: OK")

    print("\nAll throttling tests passed!")


if __name__ == "__main__":
    _test()
