"""
Throttling — From Scratch
==========================
Build throttling mechanisms to understand:
- Leaky bucket: smooth outbound rate regardless of burst
- Delayed response throttling: slow down (not reject) over-limit callers
- Queue-based throttling: buffer and process at a controlled rate
- Adaptive throttling: adjust rate based on downstream health signals

Throttling vs Rate Limiting:
  - Rate limiting REJECTS excess requests (429 Too Many Requests)
  - Throttling SLOWS DOWN or QUEUES excess requests (processes them, just slower)

Learning Path:
1. Implement a leaky bucket that drains at a fixed rate
2. Implement delay-based throttling (sleep before processing)
3. Implement a throttled worker queue (enqueue; drain at a fixed rate)
4. Think about: how does TCP congestion control use backpressure?
   - Sliding window, slow-start, AIMD (Additive Increase Multiplicative Decrease)
"""

import time
import threading
import queue
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Step 1: Leaky Bucket
# ---------------------------------------------------------------------------

class LeakyBucket:
    """Leaky bucket: requests fill a bucket; it drains at a fixed outbound rate.

    Unlike token bucket (which allows bursts), leaky bucket produces a perfectly
    smooth output stream regardless of the input burst shape.

    Model:
      - bucket has capacity (max queue depth)
      - water drips out at drain_rate items/second
      - excess overflows (rejected)

    TODO:
    - Track bucket_level (float) and last_leak_time
    - On each add(amount):
      1. Compute elapsed = now - last_leak_time
      2. Reduce bucket_level by elapsed * drain_rate (minimum 0)
      3. Update last_leak_time = now
      4. If bucket_level + amount > capacity: return False (overflow)
      5. Else: bucket_level += amount; return True
    """

    def __init__(self, capacity: float, drain_rate: float):
        """
        Args:
            capacity: maximum bucket depth (burst size)
            drain_rate: units drained per second (outbound rate)
        """
        self.capacity = capacity
        self.drain_rate = drain_rate
        self._level: float = 0.0
        self._last_leak: float = time.time()
        self._lock = threading.Lock()

    def add(self, amount: float = 1.0) -> bool:
        """Try to add `amount` to the bucket.

        Returns True if added (request accepted), False if bucket overflows.

        TODO: implement leaky bucket check
        """
        # TODO: implement leaky bucket
        raise NotImplementedError("Implement LeakyBucket.add")

    @property
    def level(self) -> float:
        """Current bucket fill level (after accounting for leakage)."""
        # TODO: return current level after computing elapsed drain
        raise NotImplementedError("Implement LeakyBucket.level")


# ---------------------------------------------------------------------------
# Step 2: Delay-Based Throttler
# ---------------------------------------------------------------------------

class DelayThrottler:
    """Throttler that delays requests instead of rejecting them.

    Each key is allowed `rate` calls per `window_seconds`, but over-limit
    calls are delayed (slept) until their slot is available — not rejected.

    Use case: outgoing API calls where you must not exceed a vendor's rate
    limit but also cannot drop requests.

    TODO:
    - Track the next_allowed_time per key
    - On throttle(key):
      1. Compute when this request is allowed: max(now, next_allowed_time[key])
      2. Update next_allowed_time[key] += 1/rate  (one slot consumed)
      3. Sleep until allowed_time if it is in the future
    """

    def __init__(self, rate: float, window_seconds: float = 1.0):
        """
        Args:
            rate: allowed calls per window_seconds
            window_seconds: the window duration (default 1 second)
        """
        self.interval = window_seconds / rate  # seconds per allowed call
        self._next_allowed: dict = {}           # key → next allowed timestamp
        self._lock = threading.Lock()

    def throttle(self, key: str) -> float:
        """Block until this call is allowed; return how long we slept (seconds).

        TODO: implement delay-based throttling
        """
        # TODO: implement delay throttling
        raise NotImplementedError("Implement DelayThrottler.throttle")


# ---------------------------------------------------------------------------
# Step 3: Throttled Worker Queue
# ---------------------------------------------------------------------------

class ThrottledWorker:
    """Queue-based throttler: enqueue tasks; a worker drains at a fixed rate.

    Pattern:
      - Producers push tasks onto a bounded queue (backpressure if full)
      - A single background worker pulls tasks and processes them with a
        minimum inter-task delay of 1/rate seconds

    TODO:
    - Start a daemon worker thread in __init__
    - The worker loops: get task from queue, call it, sleep(1/rate)
    - submit(fn, *args) puts (fn, args) on the queue; return a Future-like object
      so callers can get the result
    """

    def __init__(self, rate: float, queue_size: int = 100):
        """
        Args:
            rate: maximum tasks processed per second
            queue_size: max items buffered before submit() blocks
        """
        self.rate = rate
        self._interval = 1.0 / rate
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._results: dict = {}  # task_id → result
        self._task_counter = 0
        # TODO: start the worker daemon thread
        self._start_worker()

    def _start_worker(self) -> None:
        """Start background worker thread.

        TODO:
        1. Create a daemon thread targeting self._worker_loop
        2. Start it
        """
        # TODO: implement _start_worker
        raise NotImplementedError("Implement ThrottledWorker._start_worker")

    def _worker_loop(self) -> None:
        """Drain the queue at self.rate tasks/second.

        TODO:
        1. Loop forever
        2. Get (task_id, fn, args) from queue (blocking)
        3. Call fn(*args), store result in self._results[task_id]
        4. Sleep self._interval between tasks
        """
        # TODO: implement _worker_loop
        raise NotImplementedError("Implement ThrottledWorker._worker_loop")

    def submit(self, fn: Callable, *args: Any) -> int:
        """Enqueue a task; return a task_id to retrieve the result later.

        TODO:
        1. Increment self._task_counter (use lock)
        2. Put (task_id, fn, args) on the queue
        3. Return task_id
        """
        # TODO: implement submit
        raise NotImplementedError("Implement ThrottledWorker.submit")

    def get_result(self, task_id: int, timeout: float = 5.0) -> Any:
        """Wait for and return the result of task_id.

        TODO: poll self._results[task_id] until available or timeout
        """
        # TODO: implement get_result
        raise NotImplementedError("Implement ThrottledWorker.get_result")


# ---------------------------------------------------------------------------
# Step 4: Adaptive Throttling (discussion)
# ---------------------------------------------------------------------------

"""
Adaptive Throttling:

Used in Google's Stubby / gRPC and many internal proxy systems.

Algorithm: Client-side throttling based on success/failure ratio.
  accept_probability = max(0, (requests - K * accepts) / (requests + 1))
  where K is a tuning constant (e.g. 1.1 — allow 10% overhead)
  If random() < accept_probability → throttle the request locally

Why this helps:
  - Prevents thundering herd when a downstream is sick
  - Clients shed load without a central coordinator
  - Each client converges to just above the server's capacity

TCP Congestion Control Analogy:
  - Slow Start: begin with small window, double each RTT until loss
  - Congestion Avoidance: grow linearly (+1 MSS/RTT)
  - Fast Retransmit/Fast Recovery: on triple dup-ACK, halve window
  - AIMD: Additive Increase Multiplicative Decrease — provably fair
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing LeakyBucket...")
    bucket = LeakyBucket(capacity=3.0, drain_rate=1.0)
    results = [bucket.add(1.0) for _ in range(4)]
    assert results[:3] == [True, True, True], f"first 3 should be accepted: {results}"
    assert results[3] is False, f"4th should overflow: {results}"
    # After 2 seconds, 2 units drain; can add 2 more
    time.sleep(2.1)
    assert bucket.add(2.0) is True, "should accept after draining"
    print("  LeakyBucket: OK")

    print("Testing DelayThrottler...")
    throttler = DelayThrottler(rate=10.0)  # 10 calls/sec → 100ms apart
    start = time.time()
    throttler.throttle("user1")  # first call: no delay
    throttler.throttle("user1")  # second call: ~100ms delay
    elapsed = time.time() - start
    assert elapsed >= 0.09, f"second call should be delayed ~100ms, got {elapsed:.3f}s"
    print("  DelayThrottler: OK")

    print("Testing ThrottledWorker...")
    worker = ThrottledWorker(rate=20.0)  # 20 tasks/sec
    results_list = []
    task_ids = [worker.submit(lambda x: x * 2, i) for i in range(3)]
    for tid in task_ids:
        results_list.append(worker.get_result(tid, timeout=5.0))
    assert results_list == [0, 2, 4], f"unexpected results: {results_list}"
    print("  ThrottledWorker: OK")

    print("\nAll throttling tests passed!")


if __name__ == "__main__":
    _test()
