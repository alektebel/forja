"""
Request Batching — Complete Solution
"""

import time
import threading
from typing import Any, Callable, Dict, List, Optional


class SizeBatcher:
    def __init__(self, batch_size: int, flush_fn: Optional[Callable[[List], None]] = None):
        self.batch_size = batch_size
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()

    def add(self, item: Any) -> Optional[List[Any]]:
        with self._lock:
            self._batch.append(item)
            if len(self._batch) >= self.batch_size:
                return self._flush_locked()
        return None

    def flush(self) -> List[Any]:
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> List[Any]:
        batch = self._batch
        self._batch = []
        if self._flush_fn and batch:
            self._flush_fn(batch)
        return batch

    @property
    def pending(self) -> int:
        return len(self._batch)


class TimeBatcher:
    def __init__(self, window_ms: float, flush_fn: Callable[[List], None]):
        self.window_ms = window_ms
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start()

    def _start(self) -> None:
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()

    def add(self, item: Any) -> None:
        with self._lock:
            self._batch.append(item)

    def flush(self) -> List[Any]:
        with self._lock:
            batch = self._batch
            self._batch = []
        if batch:
            self._flush_fn(batch)
        return batch

    def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.window_ms / 1000.0)
            self.flush()

    def stop(self) -> None:
        self._stop_event.set()
        self.flush()
        if self._thread:
            self._thread.join(timeout=1.0)


class DataLoader:
    def __init__(self, batch_fn: Callable[[List[str]], Dict[str, Any]],
                 window_ms: float = 5.0):
        self._batch_fn = batch_fn
        self.window_ms = window_ms
        self._pending: Dict[str, List[threading.Event]] = {}
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._dispatch_timer: Optional[threading.Timer] = None

    def load(self, key: str) -> Any:
        event = threading.Event()
        with self._lock:
            if key not in self._pending:
                self._pending[key] = []
            self._pending[key].append(event)
            if self._dispatch_timer is None:
                self._dispatch_timer = threading.Timer(
                    self.window_ms / 1000.0, self._dispatch)
                self._dispatch_timer.start()
        event.wait()
        return self._results.get(key)

    def _dispatch(self) -> None:
        with self._lock:
            pending = self._pending
            self._pending = {}
            self._dispatch_timer = None
        keys = list(pending.keys())
        results = self._batch_fn(keys)
        for key in keys:
            self._results[key] = results.get(key)
        for key, events in pending.items():
            for ev in events:
                ev.set()


class PipelineBatcher:
    def __init__(self, batch_size: int, window_ms: float,
                 flush_fn: Callable[[List], None]):
        self.batch_size = batch_size
        self.window_ms = window_ms
        self._flush_fn = flush_fn
        self._batch: List[Any] = []
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def add(self, item: Any) -> None:
        flush_now = False
        with self._lock:
            self._batch.append(item)
            if len(self._batch) == 1:
                self._start_timer()
            if len(self._batch) >= self.batch_size:
                flush_now = True
        if flush_now:
            self.flush()

    def flush(self) -> List[Any]:
        with self._lock:
            batch = self._batch
            self._batch = []
            if self._timer:
                self._timer.cancel()
                self._timer = None
        if batch:
            self._flush_fn(batch)
        return batch

    def _start_timer(self) -> None:
        if self._timer is None:
            self._timer = threading.Timer(self.window_ms / 1000.0, self.flush)
            self._timer.start()


def _test():
    print("Testing SizeBatcher...")
    flushed_batches = []
    batcher = SizeBatcher(batch_size=3, flush_fn=lambda b: flushed_batches.append(b[:]))
    assert batcher.add(1) is None
    assert batcher.add(2) is None
    batch = batcher.add(3)
    assert batch == [1, 2, 3]
    assert len(flushed_batches) == 1
    batcher.add(4)
    remainder = batcher.flush()
    assert remainder == [4]
    print("  SizeBatcher: OK")

    print("Testing TimeBatcher...")
    time_batches = []
    tb = TimeBatcher(window_ms=50.0, flush_fn=lambda b: time_batches.append(b[:]))
    tb.add("a")
    tb.add("b")
    time.sleep(0.12)
    tb.stop()
    assert any("a" in b for b in time_batches)
    print("  TimeBatcher: OK")

    print("Testing DataLoader...")
    fetch_count = [0]

    def batch_fetch(keys):
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
        threading.Thread(target=do_load, args=("user:1",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert "USER:1" in results and "USER:2" in results
    assert fetch_count[0] == 1
    print("  DataLoader: OK")

    print("Testing PipelineBatcher (size trigger)...")
    pipe_batches = []
    pb = PipelineBatcher(batch_size=3, window_ms=200.0,
                         flush_fn=lambda b: pipe_batches.append(b[:]))
    pb.add("x")
    pb.add("y")
    pb.add("z")
    time.sleep(0.05)
    assert len(pipe_batches) >= 1
    assert pipe_batches[0] == ["x", "y", "z"]
    print("  PipelineBatcher: OK")

    print("\nAll request batching tests passed!")


if __name__ == "__main__":
    _test()
