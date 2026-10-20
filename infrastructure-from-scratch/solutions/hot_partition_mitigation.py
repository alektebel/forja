"""
Hot Partition Mitigation — Complete Solution
"""

import time
import threading
import random
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple


class ScatteredWriter:
    def __init__(self, num_shards: int = 10):
        self.num_shards = num_shards

    def write(self, key: str, value: Any, shard_store: Dict[str, List[Any]]) -> str:
        shard_id = random.randint(0, self.num_shards - 1)
        sharded_key = f"{key}:{shard_id}"
        shard_store.setdefault(sharded_key, []).append(value)
        return sharded_key

    def scatter_keys(self, key: str) -> List[str]:
        return [f"{key}:{i}" for i in range(self.num_shards)]


class ScatterGatherReader:
    def __init__(self, writer: ScatteredWriter):
        self._writer = writer

    def read(self, key: str, shard_store: Dict[str, List[Any]],
             merge_fn: Optional[Callable] = None) -> Any:
        shard_keys = self._writer.scatter_keys(key)
        collected = []
        for sk in shard_keys:
            collected.extend(shard_store.get(sk, []))
        if merge_fn is not None:
            return merge_fn(collected)
        return collected


class HotKeyDetector:
    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._access_log: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            self._access_log[key].append(now)
            self._access_log[key] = [t for t in self._access_log[key] if t > cutoff]

    def get_hot_keys(self, threshold: int) -> List[Tuple[str, int]]:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            counts = {
                key: sum(1 for ts in times if ts > cutoff)
                for key, times in self._access_log.items()
            }
        result = [(k, c) for k, c in counts.items() if c > threshold]
        return sorted(result, key=lambda x: x[1], reverse=True)

    def count(self, key: str) -> int:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            return sum(1 for ts in self._access_log[key] if ts > cutoff)


class TimeBucketedStore:
    def __init__(self, bucket_size_seconds: int = 3600):
        self.bucket_size = bucket_size_seconds
        self._store: Dict[str, List[Any]] = defaultdict(list)

    def _bucket_key(self, metric: str, timestamp: float) -> str:
        bucket_id = int(timestamp // self.bucket_size)
        return f"{metric}:{bucket_id}"

    def write(self, metric: str, value: Any, timestamp: Optional[float] = None) -> str:
        ts = timestamp if timestamp is not None else time.time()
        key = self._bucket_key(metric, ts)
        self._store[key].append(value)
        return key

    def read_range(self, metric: str, start_ts: float, end_ts: float,
                   aggregate_fn: Optional[Callable] = None) -> Any:
        first_bucket = int(start_ts // self.bucket_size)
        last_bucket = int(end_ts // self.bucket_size)
        collected = []
        for bid in range(first_bucket, last_bucket + 1):
            collected.extend(self._store.get(f"{metric}:{bid}", []))
        if aggregate_fn is not None:
            return aggregate_fn(collected)
        return collected


def _test():
    print("Testing ScatteredWriter + ScatterGatherReader...")
    writer = ScatteredWriter(num_shards=5)
    reader = ScatterGatherReader(writer)
    store: Dict[str, List[Any]] = {}
    for i in range(20):
        writer.write("hot:celebrity:posts", f"post_{i}", store)
    shard_keys = writer.scatter_keys("hot:celebrity:posts")
    counts = {k: len(store.get(k, [])) for k in shard_keys}
    non_empty = sum(1 for c in counts.values() if c > 0)
    assert non_empty >= 2
    all_posts = reader.read("hot:celebrity:posts", store)
    assert len(all_posts) == 20
    print("  ScatteredWriter + ScatterGatherReader: OK")

    print("Testing HotKeyDetector...")
    detector = HotKeyDetector(window_seconds=60.0)
    for _ in range(50):
        detector.record("viral:tweet:123")
    for _ in range(5):
        detector.record("normal:tweet:456")
    hot = detector.get_hot_keys(threshold=10)
    keys = [k for k, _ in hot]
    assert "viral:tweet:123" in keys
    assert "normal:tweet:456" not in keys
    print("  HotKeyDetector: OK")

    print("Testing TimeBucketedStore...")
    ts_store = TimeBucketedStore(bucket_size_seconds=3600)
    base_ts = 1_700_000_000.0
    ts_store.write("requests", 1, timestamp=base_ts)
    ts_store.write("requests", 2, timestamp=base_ts + 100)
    ts_store.write("requests", 3, timestamp=base_ts + 3601)
    all_vals = ts_store.read_range("requests", base_ts, base_ts + 7200)
    assert sorted(all_vals) == [1, 2, 3]
    total = ts_store.read_range("requests", base_ts, base_ts + 7200, aggregate_fn=sum)
    assert total == 6
    print("  TimeBucketedStore: OK")

    print("\nAll hot partition mitigation tests passed!")


if __name__ == "__main__":
    _test()
