"""
Consistent Hashing — Complete Solution
"""

import hashlib
import bisect
from typing import Any, Dict, List, Optional, Tuple


def _hash(key: str) -> int:
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)


class HashRing:
    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._ring: List[Tuple[int, str]] = []
        self._nodes: set = set()

    def add_node(self, node: str) -> None:
        for i in range(self.virtual_nodes):
            pos = _hash(f"{node}#vnode{i}")
            bisect.insort(self._ring, (pos, node))
        self._nodes.add(node)

    def remove_node(self, node: str) -> None:
        self._ring = [(pos, n) for pos, n in self._ring if n != node]
        self._nodes.discard(node)

    def get_node(self, key: str) -> Optional[str]:
        if not self._ring:
            return None
        pos = _hash(key)
        positions = [p for p, _ in self._ring]
        idx = bisect.bisect_left(positions, pos)
        if idx == len(self._ring):
            idx = 0
        return self._ring[idx][1]

    @property
    def nodes(self) -> set:
        return set(self._nodes)

    def distribution(self, num_keys: int = 10_000) -> Dict[str, int]:
        counts: Dict[str, int] = {n: 0 for n in self._nodes}
        for i in range(num_keys):
            node = self.get_node(f"key:{i}")
            if node:
                counts[node] = counts.get(node, 0) + 1
        return counts

    def migration_count(self, keys: List[str], old_ring: "HashRing") -> int:
        count = 0
        for key in keys:
            if self.get_node(key) != old_ring.get_node(key):
                count += 1
        return count


class RendezvousHash:
    def __init__(self):
        self._nodes: List[str] = []

    def add_node(self, node: str) -> None:
        self._nodes.append(node)

    def remove_node(self, node: str) -> None:
        self._nodes.remove(node)

    def get_node(self, key: str) -> Optional[str]:
        if not self._nodes:
            return None
        return max(self._nodes, key=lambda n: _hash(f"{n}:{key}"))

    @property
    def nodes(self) -> List[str]:
        return list(self._nodes)


def _test():
    print("Testing HashRing...")
    ring = HashRing(virtual_nodes=100)
    ring.add_node("server-A")
    ring.add_node("server-B")
    ring.add_node("server-C")

    for i in range(100):
        node = ring.get_node(f"key:{i}")
        assert node in {"server-A", "server-B", "server-C"}

    dist = ring.distribution(10_000)
    for node, count in dist.items():
        assert 1500 < count < 5000, f"distribution off for {node}: {count}"
    print(f"  Distribution: {dist}")

    assert ring.get_node("my_special_key") == ring.get_node("my_special_key")
    print("  Consistent routing: OK")

    old_ring = HashRing(virtual_nodes=100)
    old_ring.add_node("server-A")
    old_ring.add_node("server-B")
    old_ring.add_node("server-C")

    new_ring = HashRing(virtual_nodes=100)
    new_ring.add_node("server-A")
    new_ring.add_node("server-B")
    new_ring.add_node("server-C")
    new_ring.add_node("server-D")

    test_keys = [f"key:{i}" for i in range(10_000)]
    migrated = new_ring.migration_count(test_keys, old_ring)
    pct = migrated / len(test_keys) * 100
    print(f"  Migration on adding 4th node: {migrated}/10000 ({pct:.1f}%)")
    assert 15 < pct < 35

    ring.remove_node("server-B")
    assert "server-B" not in ring.nodes
    for i in range(100):
        node = ring.get_node(f"key:{i}")
        assert node in {"server-A", "server-C"}
    print("  remove_node: OK")

    print("\nTesting RendezvousHash...")
    rh = RendezvousHash()
    rh.add_node("server-A")
    rh.add_node("server-B")
    rh.add_node("server-C")

    for i in range(100):
        assert rh.get_node(f"key:{i}") in {"server-A", "server-B", "server-C"}
    assert rh.get_node("stable_key") == rh.get_node("stable_key")
    print("  RendezvousHash: OK")

    print("\nAll consistent hashing tests passed!")


if __name__ == "__main__":
    _test()
