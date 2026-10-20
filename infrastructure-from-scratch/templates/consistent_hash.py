"""
Consistent Hashing — From Scratch
====================================
Build a consistent hashing ring to understand:
- Why consistent hashing prevents mass re-mapping when nodes join/leave
- Virtual nodes (vnodes) for better load distribution
- Node lookup: find the server responsible for a given key
- Adding/removing nodes with minimal key migration

Learning Path:
1. Implement a simple hash ring with add_node and get_node
2. Add virtual nodes (multiple positions per server on the ring)
3. Implement remove_node and verify only ~1/N keys migrate
4. Track key distribution across nodes for balance analysis
5. Think about: how does Cassandra/DynamoDB use consistent hashing?

Background:
  Regular hashing: server = hash(key) % N
    Problem: when N changes, almost ALL keys remap (cache invalidation storm)

  Consistent hashing: place both servers and keys on a ring (0 to 2^32)
    A key is served by the FIRST server clockwise on the ring
    Adding/removing 1 server → only ~1/N keys migrate (instead of all)
"""

import hashlib
import bisect
from typing import Any, Dict, List, Optional, Tuple


def _hash(key: str) -> int:
    """Hash a string key to a position on the ring (0 to 2^32 - 1).

    Uses MD5 for speed; real systems use MurmurHash3 or xxHash.
    """
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)


# ---------------------------------------------------------------------------
# Step 1: Basic Hash Ring
# ---------------------------------------------------------------------------

class HashRing:
    """Consistent hash ring.

    Internals:
      - _ring: sorted list of (hash_position, node_name) tuples
      - _nodes: set of node names currently on the ring
      - virtual_nodes: number of virtual positions per physical node

    TODO:
    1. Implement add_node(node):
       - For each vnode index 0..virtual_nodes:
           key = f"{node}#vnode{i}"
           position = _hash(key)
           bisect.insort(_ring, (position, node))
       - Add node to _nodes set
    2. Implement remove_node(node):
       - Remove all vnode positions for this node from _ring
       - Remove from _nodes set
    3. Implement get_node(key) → node_name:
       - hash_pos = _hash(key)
       - Find the first ring position >= hash_pos (binary search)
       - If past the end of ring, wrap around to ring[0]
       - Return the node at that position
    """

    def __init__(self, virtual_nodes: int = 150):
        """
        Args:
            virtual_nodes: number of virtual positions per physical node.
                           Higher = better load balance but more memory.
                           Typical values: 100–200.
        """
        self.virtual_nodes = virtual_nodes
        self._ring: List[Tuple[int, str]] = []  # sorted list of (position, node)
        self._nodes: set = set()

    def add_node(self, node: str) -> None:
        """Add a node to the ring with virtual_nodes virtual positions.

        TODO: add `virtual_nodes` entries to _ring using bisect.insort
        """
        # TODO: implement add_node
        raise NotImplementedError("Implement HashRing.add_node")

    def remove_node(self, node: str) -> None:
        """Remove a node and all its virtual positions from the ring.

        TODO: filter _ring to remove all entries for this node
        """
        # TODO: implement remove_node
        raise NotImplementedError("Implement HashRing.remove_node")

    def get_node(self, key: str) -> Optional[str]:
        """Return the node responsible for this key.

        TODO:
        1. If ring is empty, return None
        2. hash_pos = _hash(key)
        3. Use bisect.bisect_left on the positions to find insertion point
        4. If insertion point == len(_ring), wrap to index 0
        5. Return _ring[index][1] (the node name)
        """
        # TODO: implement get_node
        raise NotImplementedError("Implement HashRing.get_node")

    @property
    def nodes(self) -> set:
        return set(self._nodes)

    def distribution(self, num_keys: int = 10_000) -> Dict[str, int]:
        """Sample num_keys uniformly and return the key count per node.

        Useful for verifying load balance.
        """
        # TODO: generate num_keys sample keys, get_node for each, count per node
        counts: Dict[str, int] = {n: 0 for n in self._nodes}
        for i in range(num_keys):
            node = self.get_node(f"key:{i}")
            if node:
                counts[node] = counts.get(node, 0) + 1
        return counts

    def migration_count(self, keys: List[str], old_ring: "HashRing") -> int:
        """Count how many keys would migrate when comparing to an old ring config.

        TODO: for each key, if get_node differs between self and old_ring, count it
        """
        # TODO: implement migration_count
        raise NotImplementedError("Implement HashRing.migration_count")


# ---------------------------------------------------------------------------
# Step 2: Rendezvous Hashing (alternative to ring)
# ---------------------------------------------------------------------------

class RendezvousHash:
    """Rendezvous (highest random weight) hashing.

    Alternative to consistent hashing. For each key, pick the node with
    the highest hash(node + key). Simpler to implement, same migration properties.

    TODO:
    1. Implement get_node(key):
       - For each node, compute score = _hash(f"{node}:{key}")
       - Return the node with the maximum score
    """

    def __init__(self):
        self._nodes: List[str] = []

    def add_node(self, node: str) -> None:
        self._nodes.append(node)

    def remove_node(self, node: str) -> None:
        self._nodes.remove(node)

    def get_node(self, key: str) -> Optional[str]:
        """Return the node with highest score for this key.

        TODO: compute score per node and return argmax
        """
        if not self._nodes:
            return None
        # TODO: implement rendezvous hashing
        raise NotImplementedError("Implement RendezvousHash.get_node")

    @property
    def nodes(self) -> List[str]:
        return list(self._nodes)


# ---------------------------------------------------------------------------
# Step 3: Scale discussion
# ---------------------------------------------------------------------------

"""
Consistent Hashing in Practice:

Amazon DynamoDB / Cassandra:
  - Ring partitioned into N virtual tokens
  - Each physical node owns multiple non-contiguous token ranges (vnodes)
  - Replication: key → primary node + next (R-1) nodes on ring for redundancy

Redis Cluster:
  - NOT consistent hashing — uses fixed 16384 hash slots
  - slot = CRC16(key) % 16384
  - Each node owns a range of slots; simpler resharding than a ring

Load Distribution with vnodes:
  - Without vnodes: 3 nodes → ring split 3 ways → uneven if positions unlucky
  - With 150 vnodes/node: 3 nodes → 450 ring positions → much more even

Adding a Node:
  - New node steals ~1/N fraction of keys from each existing node
  - Only keys that hash to [predecessor..new_node) migrate
  - Other keys unaffected

Removing a Node:
  - Keys from the removed node migrate to its successor only
  - ~1/N keys move, rest stay put
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing HashRing...")
    ring = HashRing(virtual_nodes=100)
    ring.add_node("server-A")
    ring.add_node("server-B")
    ring.add_node("server-C")

    # All keys should resolve to one of the 3 nodes
    for i in range(100):
        node = ring.get_node(f"key:{i}")
        assert node in {"server-A", "server-B", "server-C"}, f"unexpected node: {node}"

    # Distribution should be roughly even
    dist = ring.distribution(10_000)
    for node, count in dist.items():
        # Each node should get roughly 33% ± 10%
        assert 1500 < count < 5000, f"distribution looks off for {node}: {count}/10000"
    print(f"  Distribution: {dist}")

    # Test consistent routing: same key always → same node
    node1 = ring.get_node("my_special_key")
    node2 = ring.get_node("my_special_key")
    assert node1 == node2
    print("  Consistent routing: OK")

    # Test minimal migration on node add
    old_ring = HashRing(virtual_nodes=100)
    old_ring.add_node("server-A")
    old_ring.add_node("server-B")
    old_ring.add_node("server-C")

    new_ring = HashRing(virtual_nodes=100)
    new_ring.add_node("server-A")
    new_ring.add_node("server-B")
    new_ring.add_node("server-C")
    new_ring.add_node("server-D")  # add 4th node

    test_keys = [f"key:{i}" for i in range(10_000)]
    migrated = new_ring.migration_count(test_keys, old_ring)
    migration_pct = migrated / len(test_keys) * 100
    print(f"  Migration on adding 4th node: {migrated}/10000 ({migration_pct:.1f}%)")
    # Expect ~25% (1/4) keys to migrate
    assert 15 < migration_pct < 35, f"unexpected migration: {migration_pct:.1f}%"
    print("  Minimal migration: OK")

    # Test remove_node
    ring.remove_node("server-B")
    assert "server-B" not in ring.nodes
    for i in range(100):
        node = ring.get_node(f"key:{i}")
        assert node in {"server-A", "server-C"}, f"unexpected node after remove: {node}"
    print("  remove_node: OK")

    print("\nTesting RendezvousHash...")
    rh = RendezvousHash()
    rh.add_node("server-A")
    rh.add_node("server-B")
    rh.add_node("server-C")

    for i in range(100):
        node = rh.get_node(f"key:{i}")
        assert node in {"server-A", "server-B", "server-C"}

    # Same key always → same node
    assert rh.get_node("stable_key") == rh.get_node("stable_key")
    print("  RendezvousHash: OK")

    print("\nAll consistent hashing tests passed!")


if __name__ == "__main__":
    _test()
