"""
Eventual Consistency — Complete Solution
"""

import time
import threading
from typing import Any, Dict, Optional, Tuple


class GCounter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._counts: Dict[str, int] = {}

    def increment(self) -> None:
        self._counts[self.node_id] = self._counts.get(self.node_id, 0) + 1

    def value(self) -> int:
        return sum(self._counts.values())

    def merge(self, other: "GCounter") -> None:
        for node_id, count in other._counts.items():
            self._counts[node_id] = max(self._counts.get(node_id, 0), count)

    def state(self) -> Dict[str, int]:
        return dict(self._counts)


class LWWRegister:
    def __init__(self):
        self._data: Dict[str, Tuple[Any, float]] = {}

    def write(self, key: str, value: Any, timestamp: Optional[float] = None) -> None:
        ts = timestamp if timestamp is not None else time.time()
        current_ts = self._data.get(key, (None, float("-inf")))[1]
        if ts >= current_ts:
            self._data[key] = (value, ts)

    def read(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        return entry[0] if entry is not None else None

    def merge(self, other: "LWWRegister") -> None:
        for key, (value, ts) in other._data.items():
            self.write(key, value, ts)


class VectorClock:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._clock: Dict[str, int] = {node_id: 0}

    def tick(self) -> Dict[str, int]:
        self._clock[self.node_id] = self._clock.get(self.node_id, 0) + 1
        return dict(self._clock)

    def update(self, received: Dict[str, int]) -> Dict[str, int]:
        for node, t in received.items():
            self._clock[node] = max(self._clock.get(node, 0), t)
        self._clock[self.node_id] = self._clock.get(self.node_id, 0) + 1
        return dict(self._clock)

    def happened_before(self, other: "VectorClock") -> bool:
        all_nodes = set(self._clock) | set(other._clock)
        less_or_equal = all(
            self._clock.get(n, 0) <= other._clock.get(n, 0) for n in all_nodes
        )
        strictly_less = any(
            self._clock.get(n, 0) < other._clock.get(n, 0) for n in all_nodes
        )
        return less_or_equal and strictly_less

    def concurrent_with(self, other: "VectorClock") -> bool:
        return not self.happened_before(other) and not other.happened_before(self)

    def copy(self) -> Dict[str, int]:
        return dict(self._clock)


class Replica:
    def __init__(self, replica_id: str):
        self.replica_id = replica_id
        self._store: Dict[str, Tuple[Any, float]] = {}
        self.lag: float = 0.0

    def write(self, key: str, value: Any, timestamp: float) -> None:
        if timestamp >= self._store.get(key, (None, -1))[1]:
            self._store[key] = (value, timestamp)

    def read(self, key: str) -> Optional[Tuple[Any, float]]:
        return self._store.get(key)


class EventuallyConsistentStore:
    def __init__(self, replicas: list):
        self._replicas = replicas
        self.repair_count = 0

    def write(self, key: str, value: Any) -> None:
        ts = time.time()
        for replica in self._replicas:
            replica.write(key, value, ts)

    def read(self, key: str) -> Optional[Any]:
        responses = []
        missing = []
        for replica in self._replicas:
            entry = replica.read(key)
            if entry is not None:
                responses.append((replica, entry[0], entry[1]))
            else:
                missing.append(replica)

        if not responses:
            return None

        newest = max(responses, key=lambda x: x[2])
        newest_ts = newest[2]
        newest_val = newest[1]

        stale = [r for r, v, ts in responses if ts < newest_ts] + missing
        if stale:
            self._read_repair(key, newest_val, newest_ts, stale)

        return newest_val

    def _read_repair(self, key: str, value: Any, timestamp: float,
                     stale_replicas: list) -> None:
        for replica in stale_replicas:
            replica.write(key, value, timestamp)
            self.repair_count += 1


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
    assert c2.value() == 3
    print("  GCounter: OK")

    print("Testing LWWRegister...")
    reg1 = LWWRegister()
    reg2 = LWWRegister()
    reg1.write("x", "old", timestamp=1.0)
    reg2.write("x", "new", timestamp=2.0)
    reg1.merge(reg2)
    assert reg1.read("x") == "new"
    reg1.write("x", "stale", timestamp=0.5)
    assert reg1.read("x") == "new"
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
    assert vc_b.happened_before(vc_a) is True
    assert vc_a.happened_before(vc_b) is False
    print("  VectorClock: OK")

    print("Testing EventuallyConsistentStore with read-repair...")
    r1 = Replica("r1")
    r2 = Replica("r2")
    r3 = Replica("r3")
    store = EventuallyConsistentStore([r1, r2, r3])
    store.write("k", "v1")
    r3._store.clear()
    result = store.read("k")
    assert result == "v1"
    assert store.repair_count > 0
    assert r3.read("k") is not None
    print("  EventuallyConsistentStore: OK")

    print("\nAll eventual consistency tests passed!")


if __name__ == "__main__":
    _test()
