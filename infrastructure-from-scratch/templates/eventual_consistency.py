"""
Eventual Consistency — From Scratch
=====================================
Build eventually-consistent data structures to understand:
- Conflict-free Replicated Data Types (CRDTs): counters, sets
- Vector clocks: track causality across distributed nodes
- Last-Writer-Wins (LWW): resolve conflicts by timestamp
- Read-repair: fix stale replicas on read
- Anti-entropy: background sync to converge replicas

Key insight: in distributed systems you often trade strong consistency for
availability (CAP theorem). Eventual consistency means all replicas *will*
converge given no new writes and sufficient time.

Learning Path:
1. Implement a G-Counter CRDT (grow-only, merge by max per node)
2. Implement a LWW-Register (last-writer-wins per key)
3. Implement a vector clock for causal ordering
4. Implement a replica with read-repair
5. Think about: how does Cassandra's read-repair and hinted handoff work?
"""

import time
import threading
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: G-Counter CRDT (Grow-Only Counter)
# ---------------------------------------------------------------------------

class GCounter:
    """Grow-only counter CRDT.

    Each node increments only its own slot; the global value is the sum.
    Merge is performed component-wise with max() — conflict-free.

    TODO:
    - Store a dict: node_id → count
    - increment(node_id): add 1 to that node's slot
    - value(): sum of all slots
    - merge(other: GCounter): for each node, take max of both counters
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._counts: Dict[str, int] = {}

    def increment(self) -> None:
        """Increment this node's counter.

        TODO: add 1 to self._counts[self.node_id]
        """
        # TODO: implement increment
        raise NotImplementedError("Implement GCounter.increment")

    def value(self) -> int:
        """Return the global count (sum of all node counts).

        TODO: return sum of all values in self._counts
        """
        # TODO: implement value
        raise NotImplementedError("Implement GCounter.value")

    def merge(self, other: "GCounter") -> None:
        """Merge another GCounter into this one (take component-wise max).

        TODO:
        1. For each node_id in other._counts:
           self._counts[node_id] = max(self._counts.get(node_id, 0), other._counts[node_id])
        """
        # TODO: implement merge
        raise NotImplementedError("Implement GCounter.merge")

    def state(self) -> Dict[str, int]:
        """Return a copy of the internal state (for replication)."""
        return dict(self._counts)


# ---------------------------------------------------------------------------
# Step 2: LWW-Register (Last-Writer-Wins)
# ---------------------------------------------------------------------------

class LWWRegister:
    """Last-Writer-Wins register: the write with the highest timestamp wins.

    Simple conflict resolution: no semantic merging, just take the latest write.
    Used in Cassandra (with wall clock) and Redis (with sequence numbers).

    TODO:
    - Store (value, timestamp) per key
    - write(key, value, timestamp): update only if timestamp > stored timestamp
    - read(key): return value, or None if not set
    - merge(other: LWWRegister): for each key, keep the write with higher timestamp
    """

    def __init__(self):
        self._data: Dict[str, Tuple[Any, float]] = {}  # key → (value, timestamp)

    def write(self, key: str, value: Any, timestamp: Optional[float] = None) -> None:
        """Write key=value with a timestamp (defaults to now).

        TODO: only update if timestamp >= stored timestamp for this key
        """
        # TODO: implement write with LWW semantics
        raise NotImplementedError("Implement LWWRegister.write")

    def read(self, key: str) -> Optional[Any]:
        """Return the current value for key, or None.

        TODO: return self._data[key][0] if key present, else None
        """
        # TODO: implement read
        raise NotImplementedError("Implement LWWRegister.read")

    def merge(self, other: "LWWRegister") -> None:
        """Merge another register into this one (LWW per key).

        TODO: for each key in other._data, call self.write with that key/value/ts
        """
        # TODO: implement merge
        raise NotImplementedError("Implement LWWRegister.merge")


# ---------------------------------------------------------------------------
# Step 3: Vector Clock
# ---------------------------------------------------------------------------

class VectorClock:
    """Vector clock for tracking causality across distributed nodes.

    Each node maintains a counter per known node.
    On send: increment own counter.
    On receive: component-wise max, then increment own counter.

    Comparison:
      A < B (A happened-before B) if every component of A <= B and at least one <
      A || B (concurrent) if neither A < B nor B < A

    TODO:
    - Store dict: node_id → logical_time
    - tick(node_id): increment node_id's clock
    - update(received_clock): merge then tick
    - happened_before(other): check if self < other per Lamport rules
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._clock: Dict[str, int] = {node_id: 0}

    def tick(self) -> Dict[str, int]:
        """Increment this node's logical clock and return a copy of the clock.

        TODO: self._clock[self.node_id] += 1; return copy
        """
        # TODO: implement tick
        raise NotImplementedError("Implement VectorClock.tick")

    def update(self, received: Dict[str, int]) -> Dict[str, int]:
        """Receive a clock from another node: merge then tick own counter.

        TODO:
        1. For each (node, time) in received: self._clock[node] = max(self._clock.get(node,0), time)
        2. self._clock[self.node_id] += 1
        3. Return a copy
        """
        # TODO: implement update
        raise NotImplementedError("Implement VectorClock.update")

    def happened_before(self, other: "VectorClock") -> bool:
        """Return True if self happened-before other (self < other).

        TODO:
        - All nodes in self._clock have value <= corresponding value in other._clock
        - At least one is strictly less
        """
        # TODO: implement happened_before
        raise NotImplementedError("Implement VectorClock.happened_before")

    def concurrent_with(self, other: "VectorClock") -> bool:
        """Return True if self and other are concurrent (neither happened before the other).

        TODO: not self.happened_before(other) and not other.happened_before(self)
        """
        # TODO: implement concurrent_with
        raise NotImplementedError("Implement VectorClock.concurrent_with")

    def copy(self) -> Dict[str, int]:
        return dict(self._clock)


# ---------------------------------------------------------------------------
# Step 4: Replica with Read-Repair
# ---------------------------------------------------------------------------

class Replica:
    """Simulates a single data replica with LWW storage."""

    def __init__(self, replica_id: str):
        self.replica_id = replica_id
        self._store: Dict[str, Tuple[Any, float]] = {}  # key → (value, ts)
        self.lag: float = 0.0  # simulated replication lag

    def write(self, key: str, value: Any, timestamp: float) -> None:
        if timestamp >= self._store.get(key, (None, -1))[1]:
            self._store[key] = (value, timestamp)

    def read(self, key: str) -> Optional[Tuple[Any, float]]:
        return self._store.get(key)


class EventuallyConsistentStore:
    """Multi-replica store with read-repair for eventual consistency.

    Read-repair: on a quorum read, compare replicas; if some are stale,
    send them the newer version in the background.

    TODO:
    - write(key, value): write to ALL replicas with current timestamp
    - read(key): read from ALL replicas; return the newest value;
      trigger read_repair for any replica that returned a stale value
    - _read_repair(key, newest_value, newest_ts, stale_replicas): update stale replicas
    """

    def __init__(self, replicas: list):
        self._replicas = replicas
        self.repair_count = 0

    def write(self, key: str, value: Any) -> None:
        """Write key=value to all replicas.

        TODO: set timestamp = time.time(); call replica.write on each replica
        """
        # TODO: implement write
        raise NotImplementedError("Implement EventuallyConsistentStore.write")

    def read(self, key: str) -> Optional[Any]:
        """Read from all replicas; return newest value; trigger read-repair.

        TODO:
        1. Collect (value, ts) from each replica; track replicas that returned None (missing)
        2. Find the newest (highest ts) among replicas that had data
        3. For any replica with an older ts OR missing: call _read_repair
        4. Return the newest value
        """
        # TODO: implement read with read-repair
        raise NotImplementedError("Implement EventuallyConsistentStore.read")

    def _read_repair(self, key: str, value: Any, timestamp: float,
                     stale_replicas: list) -> None:
        """Update stale replicas with the authoritative value.

        TODO: for each stale replica, call replica.write(key, value, timestamp)
        """
        # TODO: implement read-repair
        raise NotImplementedError("Implement EventuallyConsistentStore._read_repair")


# ---------------------------------------------------------------------------
# Step 5: Anti-Entropy & Convergence (discussion)
# ---------------------------------------------------------------------------

"""
Anti-Entropy Patterns:

1. Merkle Trees (used by DynamoDB, Cassandra):
   - Build a hash tree over key ranges
   - Compare root hash with peer: if same, subtree is identical
   - Recursively descend to find divergent ranges
   - Only sync divergent ranges → efficient over large datasets

2. Gossip Protocol:
   - Each node randomly picks a peer and exchanges state summaries
   - After O(log N) rounds, all nodes converge
   - Used by Cassandra for node membership and ring topology
   - Pros: no single point of failure, self-healing
   - Cons: eventual (not immediate) convergence, extra bandwidth

3. Read-Repair vs Anti-Entropy:
   - Read-repair: fix stale data lazily on reads (no background overhead)
   - Anti-entropy: fix stale data eagerly in the background (catches cold data)
   - DynamoDB uses both: read-repair + background anti-entropy daemon

4. Conflict Resolution Strategies:
   - LWW (Last Writer Wins): simple, but clock skew can lose data
   - CRDT: provably convergent, no conflicts possible
   - Application-level merge: most flexible, app defines what "latest" means
   - Vector clocks: expose conflicts to the application layer to resolve

5. Consistency Levels (Cassandra / DynamoDB style):
   - ONE:    return on first replica response (lowest latency, stalest read)
   - QUORUM: W + R > N (e.g. W=2, R=2, N=3) — consistent under normal ops
   - ALL:    all replicas must respond (highest consistency, lowest availability)
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing GCounter...")
    c1 = GCounter("node1")
    c2 = GCounter("node2")
    c1.increment()
    c1.increment()
    c2.increment()
    assert c1.value() == 2
    assert c2.value() == 1
    c1.merge(c2)
    assert c1.value() == 3
    c2.merge(c1)
    assert c2.value() == 3  # both converge
    print("  GCounter: OK")

    print("Testing LWWRegister...")
    reg1 = LWWRegister()
    reg2 = LWWRegister()
    reg1.write("x", "old", timestamp=1.0)
    reg2.write("x", "new", timestamp=2.0)
    reg1.merge(reg2)
    assert reg1.read("x") == "new", "LWW should keep newer value"
    reg1.write("x", "stale", timestamp=0.5)  # older timestamp, should be ignored
    assert reg1.read("x") == "new", "LWW should reject older timestamp"
    print("  LWWRegister: OK")

    print("Testing VectorClock...")
    vc_a = VectorClock("A")
    vc_b = VectorClock("B")
    vc_a.tick()                      # A: {A:1}
    vc_a.tick()                      # A: {A:2}
    clock_a = vc_a.copy()            # {A:2}
    vc_b.update(clock_a)             # B receives A: {A:2, B:1}
    clock_b = vc_b.copy()            # {A:2, B:1}
    vc_a.update(clock_b)             # A receives B: {A:3, B:1}
    # vc_b={A:2,B:1} happened-before vc_a={A:3,B:1}: A:2<3, B:1=1
    assert vc_b.happened_before(vc_a) is True  # B < A
    assert vc_a.happened_before(vc_b) is False
    print("  VectorClock: OK")

    print("Testing EventuallyConsistentStore with read-repair...")
    r1 = Replica("r1")
    r2 = Replica("r2")
    r3 = Replica("r3")
    # Simulate r3 missing a write (e.g., was briefly offline)
    store = EventuallyConsistentStore([r1, r2, r3])
    store.write("k", "v1")
    # Manually make r3 stale
    r3._store.clear()
    result = store.read("k")
    assert result == "v1", f"expected 'v1', got {result}"
    assert store.repair_count > 0, "read-repair should have triggered"
    # After repair, r3 should have the value
    assert r3.read("k") is not None, "r3 should be repaired"
    print("  EventuallyConsistentStore (read-repair): OK")

    print("\nAll eventual consistency tests passed!")


if __name__ == "__main__":
    _test()
