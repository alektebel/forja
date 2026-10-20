"""
Request Batching — From Scratch
=================================
Build request batching primitives to understand:
- Time-window batching: collect requests for N ms then dispatch as one batch
- Size-window batching: flush when batch reaches a size threshold
- DataLoader pattern: deduplicate identical keys within a batch
- Batch result fan-out: distribute individual results back to callers
- Pipeline batching: stream of requests auto-grouped into batches

Batching reduces per-request overhead by amortizing fixed costs:
  - DB round trips (N inserts → 1 batch INSERT)
  - Network latency (N small payloads → 1 large payload)
  - API calls (N requests → 1 batch API call within quota)

Learning Path:
1. Implement size-window batch collector
2. Implement time-window batch flusher
3. Implement DataLoader (deduplicate + fan-out)
4. Implement async pipeline batcher (auto-flush by time or size)
5. Think about: how does DynamoDB BatchWriteItem / BatchGetItem work?
   - Max 25 items per batch; unprocessed items are returned for retry
"""

import time
import threading
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar

K = TypeVar("K")
V = TypeVar("V")


# ---------------------------------------------------------------------------
# Step 1: Size-Window Batch Collector
# ---------------------------------------------------------------------------

class SizeBatcher:
    """Collect items and flush when the batch reaches a size threshold.

    TODO:
    - add(item): add an item; if len(batch) >= batch_size, flush and return the batch
    - flush(): return and reset the current batch
    - The batch is a plain list; callers process the returned list
    """

    def __init__(self, batch_size: int, flush_fn: Optional[Callable[[List], None]] = None):
        """
        Args:
            batch_size: flush when batch reaches this size
            flush_fn: optional callback called with the batch on each flush
        """
        self.batch_size = batch_size
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()

    def add(self, item: Any) -> Optional[List[Any]]:
        """Add an item to the batch; flush and return batch if at capacity.

        Returns the flushed batch (list) if a flush occurred, else None.

        TODO:
        1. Append item to self._batch
        2. If len(self._batch) >= batch_size: return self.flush()
        3. Return None
        """
        # TODO: implement add
        raise NotImplementedError("Implement SizeBatcher.add")

    def flush(self) -> List[Any]:
        """Flush and return the current batch; reset to empty.

        TODO:
        1. batch = self._batch; self._batch = []
        2. If self._flush_fn: call it with batch
        3. Return batch
        """
        # TODO: implement flush
        raise NotImplementedError("Implement SizeBatcher.flush")

    @property
    def pending(self) -> int:
        """Number of items waiting in the current batch."""
        return len(self._batch)


# ---------------------------------------------------------------------------
# Step 2: Time-Window Batch Flusher
# ---------------------------------------------------------------------------

class TimeBatcher:
    """Collect items and flush every `window_ms` milliseconds.

    A background thread triggers the flush; items arrive from any thread.

    TODO:
    - add(item): thread-safely append to current batch
    - _flush_loop(): background thread; sleep window_ms; flush; repeat
    - flush(): swap out the current batch; call flush_fn with collected items
    - stop(): stop the background thread cleanly
    """

    def __init__(self, window_ms: float, flush_fn: Callable[[List], None]):
        """
        Args:
            window_ms: flush interval in milliseconds
            flush_fn: called with the batch list on each flush
        """
        self.window_ms = window_ms
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        # TODO: start the background flush thread
        self._thread: Optional[threading.Thread] = None
        self._start()

    def _start(self) -> None:
        """Start the background flush thread.

        TODO: create a daemon thread targeting self._flush_loop; start it
        """
        # TODO: implement _start
        raise NotImplementedError("Implement TimeBatcher._start")

    def add(self, item: Any) -> None:
        """Thread-safely add an item to the current batch.

        TODO: with self._lock: self._batch.append(item)
        """
        # TODO: implement add
        raise NotImplementedError("Implement TimeBatcher.add")

    def flush(self) -> List[Any]:
        """Atomically swap out the batch and invoke flush_fn.

        TODO:
        1. with self._lock: batch = self._batch; self._batch = []
        2. If batch: self._flush_fn(batch)
        3. Return batch
        """
        # TODO: implement flush
        raise NotImplementedError("Implement TimeBatcher.flush")

    def _flush_loop(self) -> None:
        """Background thread: sleep window_ms, then flush, repeat until stopped.

        TODO:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.window_ms / 1000)
            self.flush()
        """
        # TODO: implement _flush_loop
        raise NotImplementedError("Implement TimeBatcher._flush_loop")

    def stop(self) -> None:
        """Stop the background thread and flush remaining items."""
        # TODO: set stop event, flush remaining, join thread
        raise NotImplementedError("Implement TimeBatcher.stop")


# ---------------------------------------------------------------------------
# Step 3: DataLoader (deduplicate + fan-out)
# ---------------------------------------------------------------------------

class DataLoader:
    """Batch loader that deduplicates identical keys and fans out results.

    Pattern (popularised by Facebook's DataLoader for GraphQL):
      1. Many concurrent callers each request a key: load("user:1"), load("user:2"), load("user:1")
      2. Within a tick (time window), collect all requested keys
      3. Deduplicate keys: {user:1, user:2}
      4. Batch-fetch: batch_fn(["user:1", "user:2"]) → {"user:1": ..., "user:2": ...}
      5. Fan out: deliver result to all callers who requested each key

    TODO:
    - load(key): return a "future" (threading.Event + result slot) for this key;
      enqueue key for the next batch
    - _dispatch(): collect pending keys, deduplicate, call batch_fn, set all futures
    - The batch_fn signature: fn(keys: List[str]) → Dict[str, Any]
    """

    def __init__(self, batch_fn: Callable[[List[str]], Dict[str, Any]],
                 window_ms: float = 5.0):
        self._batch_fn = batch_fn
        self.window_ms = window_ms
        self._pending: Dict[str, List[threading.Event]] = {}   # key → list of waiters
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._dispatch_timer: Optional[threading.Timer] = None

    def load(self, key: str) -> Any:
        """Schedule key for batch loading; block until result is available.

        TODO:
        1. Create a threading.Event for this call
        2. With self._lock: append event to self._pending[key]
        3. If no dispatch timer is running: schedule self._dispatch after window_ms
        4. Wait on the event
        5. Return self._results[key]
        """
        # TODO: implement load
        raise NotImplementedError("Implement DataLoader.load")

    def _dispatch(self) -> None:
        """Collect pending keys, batch-fetch, fan out results to waiters.

        TODO:
        1. Swap out self._pending (under lock): pending = self._pending; self._pending = {}
        2. keys = list(pending.keys())  ← deduplicated automatically (dict keys are unique)
        3. results = self._batch_fn(keys)
        4. For each key: self._results[key] = results.get(key)
        5. For each event in pending[key]: event.set()
        """
        # TODO: implement _dispatch
        raise NotImplementedError("Implement DataLoader._dispatch")


# ---------------------------------------------------------------------------
# Step 4: Pipeline Batcher (auto-flush by time or size)
# ---------------------------------------------------------------------------

class PipelineBatcher:
    """Combines time-window and size-window flushing: flush whichever comes first.

    TODO:
    - add(item): add to batch; flush if batch_size reached
    - _timer_flush(): called by background timer; flush if anything pending
    - flush(): flush current batch and reset timer
    """

    def __init__(self, batch_size: int, window_ms: float,
                 flush_fn: Callable[[List], None]):
        self.batch_size = batch_size
        self.window_ms = window_ms
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def add(self, item: Any) -> None:
        """Add item; flush if batch_size reached; start timer if first item.

        TODO:
        1. with self._lock: append item; start timer if it's the first item
        2. If len >= batch_size: flush()
        """
        # TODO: implement add
        raise NotImplementedError("Implement PipelineBatcher.add")

    def flush(self) -> List[Any]:
        """Flush current batch; cancel timer; return flushed items.

        TODO:
        1. with self._lock: swap batch; cancel timer
        2. If batch: call self._flush_fn(batch)
        3. Return batch
        """
        # TODO: implement flush
        raise NotImplementedError("Implement PipelineBatcher.flush")

    def _start_timer(self) -> None:
        """Start a one-shot timer to flush after window_ms if not already running."""
        # TODO: if no timer: self._timer = threading.Timer(window_ms/1000, self.flush); start
        raise NotImplementedError("Implement PipelineBatcher._start_timer")


# ---------------------------------------------------------------------------
# Step 5: Batching in Databases (discussion)
# ---------------------------------------------------------------------------

"""
Database Batching Patterns:

1. Bulk INSERT:
   - Single INSERT with many rows: INSERT INTO events VALUES (…),(…),(…)
   - 100x faster than N individual INSERTs (single round trip, single lock)
   - PostgreSQL: COPY FROM for bulk loads (even faster)

2. DynamoDB BatchWriteItem:
   - Max 25 items per call; handles up to 16MB of data
   - Unprocessed items returned → must retry with backoff
   - Not transactional: partial batch can succeed

3. Redis Pipelining:
   - Send multiple commands without waiting for each reply
   - commands = [SET k1 v1, SET k2 v2, ...]; reply = pipeline.execute()
   - Reduces N RTTs to 1 RTT (all sent in one TCP segment)
   - Different from MULTI/EXEC (transactions) — pipelining is not atomic

4. Kafka Batching:
   - Producer batches messages until batch.size bytes OR linger.ms elapsed
   - Single network write per batch
   - Consumer fetches up to max.partition.fetch.bytes per partition per poll

5. DataLoader Pattern Trade-offs:
   - Pros: drastically reduces DB round trips in GraphQL / N+1 query scenarios
   - Cons: adds latency equal to the batch window (typically 1-10ms)
   - Key insight: amortize fixed network RTT across many logical requests
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing SizeBatcher...")
    flushed_batches = []
    batcher = SizeBatcher(batch_size=3, flush_fn=lambda b: flushed_batches.append(b[:]))

    assert batcher.add(1) is None
    assert batcher.add(2) is None
    batch = batcher.add(3)   # triggers flush
    assert batch == [1, 2, 3], f"expected [1,2,3], got {batch}"
    assert len(flushed_batches) == 1

    batcher.add(4)
    remainder = batcher.flush()
    assert remainder == [4], f"expected [4], got {remainder}"
    print("  SizeBatcher: OK")

    print("Testing TimeBatcher...")
    time_batches = []
    tb = TimeBatcher(window_ms=50.0, flush_fn=lambda b: time_batches.append(b[:]))
    tb.add("a")
    tb.add("b")
    time.sleep(0.12)  # wait for at least one flush
    tb.stop()
    assert any("a" in b for b in time_batches), \
        f"items should have been flushed by timer: {time_batches}"
    print("  TimeBatcher: OK")

    print("Testing DataLoader...")
    fetch_count = [0]

    def batch_fetch(keys: List[str]) -> Dict[str, Any]:
        fetch_count[0] += 1
        return {k: k.upper() for k in keys}

    loader = DataLoader(batch_fetch, window_ms=20.0)
    results = []
    errors = []

    def do_load(key):
        try:
            results.append(loader.load(key))
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=do_load, args=("user:1",)),
        threading.Thread(target=do_load, args=("user:2",)),
        threading.Thread(target=do_load, args=("user:1",)),  # duplicate
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"unexpected errors: {errors}"
    assert "USER:1" in results and "USER:2" in results, f"unexpected results: {results}"
    assert fetch_count[0] == 1, \
        f"all keys should be fetched in one batch call, got {fetch_count[0]}"
    print("  DataLoader: OK")

    print("Testing PipelineBatcher (size trigger)...")
    pipe_batches = []
    pb = PipelineBatcher(batch_size=3, window_ms=200.0,
                         flush_fn=lambda b: pipe_batches.append(b[:]))
    pb.add("x")
    pb.add("y")
    pb.add("z")   # triggers size flush
    time.sleep(0.05)
    assert len(pipe_batches) >= 1, "size flush should have occurred"
    assert pipe_batches[0] == ["x", "y", "z"], f"unexpected batch: {pipe_batches}"
    print("  PipelineBatcher: OK")

    print("\nAll request batching tests passed!")


if __name__ == "__main__":
    _test()
