"""
Hot Partition Mitigation — From Scratch
=========================================
Build strategies to distribute load away from hot partitions:
- Write scattering with random suffix salting
- Scatter-gather reads that reassemble scattered writes
- Adaptive key rebalancing based on access frequency
- Time-bucketed keys to distribute bursty time-series writes
- Virtual node sharding (augments consistent_hash.py)

Hot partition problem: when one shard/partition receives disproportionate
traffic (e.g., a celebrity's posts, a trending item), the node hosting
that partition becomes the bottleneck while others sit idle.

Learning Path:
1. Implement write-scatter: add salt suffix to spread writes across N copies
2. Implement scatter-gather read: read all N copies and combine
3. Implement an access-frequency tracker to detect hot keys
4. Implement time-bucketed keys for time-series workloads
5. Think about: how does DynamoDB's adaptive capacity work?
   - Automatically allocates more capacity to hot partitions
   - Vs. manual: split partitions, add shards, use DAX caching layer
"""

import time
import threading
import random
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: Write Scattering
# ---------------------------------------------------------------------------

class ScatteredWriter:
    """Distribute writes for a hot key across N shards using a salt suffix.

    Instead of writing `user:celebrity:posts` to one shard, write to:
      `user:celebrity:posts:0`, `user:celebrity:posts:1`, ..., `user:celebrity:posts:N-1`
    choosing the suffix randomly each time.

    Reads must then query ALL N shards and combine results (scatter-gather).

    TODO:
    - write(key, value, shard_store): pick a random shard 0..N-1; store under
      f"{key}:{shard}" in shard_store
    - scatter_keys(key): return the list of N sharded key strings for key
    """

    def __init__(self, num_shards: int = 10):
        self.num_shards = num_shards

    def write(self, key: str, value: Any, shard_store: Dict[str, List[Any]]) -> str:
        """Write value to a random shard of key; return the sharded key used.

        TODO:
        1. Pick shard_id = random.randint(0, num_shards - 1)
        2. sharded_key = f"{key}:{shard_id}"
        3. shard_store.setdefault(sharded_key, []).append(value)
        4. Return sharded_key
        """
        # TODO: implement write scatter
        raise NotImplementedError("Implement ScatteredWriter.write")

    def scatter_keys(self, key: str) -> List[str]:
        """Return all N sharded key names for this key.

        TODO: return [f"{key}:{i}" for i in range(num_shards)]
        """
        # TODO: implement scatter_keys
        raise NotImplementedError("Implement ScatteredWriter.scatter_keys")


# ---------------------------------------------------------------------------
# Step 2: Scatter-Gather Read
# ---------------------------------------------------------------------------

class ScatterGatherReader:
    """Read all shards for a hot key and merge the results.

    TODO:
    - read(key, shard_store, merge_fn): call scatter_keys, fetch each shard,
      apply merge_fn to combine results
    - The merge_fn might be: sum counters, concatenate lists, take max
    """

    def __init__(self, writer: ScatteredWriter):
        self._writer = writer

    def read(self, key: str, shard_store: Dict[str, List[Any]],
             merge_fn: Optional[Callable] = None) -> Any:
        """Gather all shards of key and merge them.

        Default merge_fn: flatten all lists into one list.

        TODO:
        1. Get all shard keys via self._writer.scatter_keys(key)
        2. Collect shard_store.get(shard_key, []) for each shard key
        3. Apply merge_fn (default: concatenate lists)
        4. Return merged result
        """
        # TODO: implement scatter-gather read
        raise NotImplementedError("Implement ScatterGatherReader.read")


# ---------------------------------------------------------------------------
# Step 3: Hot Key Detector
# ---------------------------------------------------------------------------

class HotKeyDetector:
    """Track access frequency and identify hot keys using a sliding window.

    A key is "hot" if it exceeds hot_threshold requests in the window.

    TODO:
    - record(key): record an access to key at current time
    - get_hot_keys(threshold): return list of (key, count) for keys where
      count > threshold in the current window
    - Prune old records outside the window on each call to record()
    """

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        self._access_log: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, key: str) -> None:
        """Record an access to key.

        TODO:
        1. Append current time to self._access_log[key]
        2. Prune timestamps older than (now - window_seconds) for ALL keys
           (can prune lazily — just the current key is fine for efficiency)
        """
        # TODO: implement record
        raise NotImplementedError("Implement HotKeyDetector.record")

    def get_hot_keys(self, threshold: int) -> List[Tuple[str, int]]:
        """Return (key, count) for keys with count > threshold in the window.

        TODO:
        1. Compute cutoff = now - window_seconds
        2. For each key: count timestamps > cutoff
        3. Filter to count > threshold, sort by count descending
        """
        # TODO: implement get_hot_keys
        raise NotImplementedError("Implement HotKeyDetector.get_hot_keys")

    def count(self, key: str) -> int:
        """Return access count for key in the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            return sum(1 for ts in self._access_log[key] if ts > cutoff)


# ---------------------------------------------------------------------------
# Step 4: Time-Bucketed Keys
# ---------------------------------------------------------------------------

class TimeBucketedStore:
    """Store time-series data under time-bucketed keys to avoid hot partitions.

    Problem: writing all events to `metrics:api_calls` funnels to one partition.
    Solution: write to `metrics:api_calls:2024-01-15:14` (hourly buckets), etc.
    Queries aggregate across buckets.

    TODO:
    - write(metric, value, timestamp): store under bucketed key
    - read_range(metric, start_ts, end_ts): aggregate across all buckets in range
    - _bucket_key(metric, timestamp): compute the bucket key for a timestamp
    """

    def __init__(self, bucket_size_seconds: int = 3600):
        """
        Args:
            bucket_size_seconds: size of each time bucket in seconds (default: 1 hour)
        """
        self.bucket_size = bucket_size_seconds
        self._store: Dict[str, List[Any]] = defaultdict(list)

    def _bucket_key(self, metric: str, timestamp: float) -> str:
        """Compute the bucket key for a metric at a given timestamp.

        TODO: bucket_id = int(timestamp // bucket_size)
              return f"{metric}:{bucket_id}"
        """
        # TODO: implement _bucket_key
        raise NotImplementedError("Implement TimeBucketedStore._bucket_key")

    def write(self, metric: str, value: Any, timestamp: Optional[float] = None) -> str:
        """Write a value to the appropriate time bucket.

        TODO:
        1. timestamp = timestamp or time.time()
        2. key = _bucket_key(metric, timestamp)
        3. self._store[key].append(value)
        4. Return key
        """
        # TODO: implement write
        raise NotImplementedError("Implement TimeBucketedStore.write")

    def read_range(self, metric: str, start_ts: float, end_ts: float,
                   aggregate_fn: Optional[Callable] = None) -> Any:
        """Aggregate values for metric across all buckets in [start_ts, end_ts].

        Default aggregate: return a flat list of all values.

        TODO:
        1. Compute all bucket_ids in range:
           first_bucket = int(start_ts // bucket_size)
           last_bucket  = int(end_ts // bucket_size)
        2. Collect self._store[f"{metric}:{bid}"] for bid in range(first, last+1)
        3. Flatten and apply aggregate_fn
        """
        # TODO: implement read_range
        raise NotImplementedError("Implement TimeBucketedStore.read_range")


# ---------------------------------------------------------------------------
# Step 5: Partition Rebalancing (discussion)
# ---------------------------------------------------------------------------

"""
Partition Rebalancing Strategies:

1. Consistent Hashing with Virtual Nodes (see consistent_hash.py):
   - Each physical node owns multiple virtual nodes on the ring
   - When a node is added: only its neighbors' keys migrate
   - When a node is hot: increase its virtual node count temporarily
   
2. Range-Based Sharding with Split:
   - Partition key range [0, MAX] split evenly across N shards
   - On hotspot: split the hot shard into two → redistribute half its range
   - Used by HBase, Google Spanner, CockroachDB

3. Scatter-Gather Trade-offs:
   - Writes: O(1) — write to one shard
   - Reads: O(N) — must query all shards
   - Good when writes >> reads (e.g., counters, event streams)
   - Bad when reads >> writes (consider caching or read replicas instead)

4. DynamoDB Adaptive Capacity:
   - Automatically detects hot partitions
   - Reallocates throughput capacity from underutilized to hot partitions
   - Partition splitting: hot partition is split when it reaches capacity limit
   - Burst capacity: unused capacity from previous minutes can absorb spikes

5. Application-Level Mitigations:
   - Cache hot items at application layer (avoid hitting DB at all)
   - Read replicas: route hot reads to replicas
   - Precompute aggregates: don't read all shards live; aggregate via background job
   - Exponential backoff on throttling: avoid amplifying the hot partition storm
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing ScatteredWriter + ScatterGatherReader...")
    writer = ScatteredWriter(num_shards=5)
    reader = ScatterGatherReader(writer)
    store: Dict[str, List[Any]] = {}

    # Write 20 items for a hot key
    for i in range(20):
        writer.write("hot:celebrity:posts", f"post_{i}", store)

    # Verify they're spread across shards
    shard_keys = writer.scatter_keys("hot:celebrity:posts")
    counts = {k: len(store.get(k, [])) for k in shard_keys}
    non_empty = sum(1 for c in counts.values() if c > 0)
    assert non_empty >= 2, f"writes should be spread across shards, got {counts}"

    # Scatter-gather read should return all 20 items
    all_posts = reader.read("hot:celebrity:posts", store)
    assert len(all_posts) == 20, f"expected 20 posts, got {len(all_posts)}"
    print("  ScatteredWriter + ScatterGatherReader: OK")

    print("Testing HotKeyDetector...")
    detector = HotKeyDetector(window_seconds=60.0)
    for _ in range(50):
        detector.record("viral:tweet:123")
    for _ in range(5):
        detector.record("normal:tweet:456")

    hot = detector.get_hot_keys(threshold=10)
    keys = [k for k, _ in hot]
    assert "viral:tweet:123" in keys, f"viral tweet should be hot: {hot}"
    assert "normal:tweet:456" not in keys, f"normal tweet should not be hot: {hot}"
    print("  HotKeyDetector: OK")

    print("Testing TimeBucketedStore...")
    ts_store = TimeBucketedStore(bucket_size_seconds=3600)
    base_ts = 1_700_000_000.0  # arbitrary epoch timestamp

    # Write events in two different hourly buckets
    ts_store.write("requests", 1, timestamp=base_ts)
    ts_store.write("requests", 2, timestamp=base_ts + 100)
    ts_store.write("requests", 3, timestamp=base_ts + 3601)  # next bucket

    # Read range spanning both buckets
    all_vals = ts_store.read_range("requests", base_ts, base_ts + 7200)
    assert sorted(all_vals) == [1, 2, 3], f"expected [1,2,3], got {sorted(all_vals)}"

    # Aggregate with sum
    total = ts_store.read_range("requests", base_ts, base_ts + 7200, aggregate_fn=sum)
    assert total == 6, f"expected sum=6, got {total}"
    print("  TimeBucketedStore: OK")

    print("\nAll hot partition mitigation tests passed!")


if __name__ == "__main__":
    _test()
