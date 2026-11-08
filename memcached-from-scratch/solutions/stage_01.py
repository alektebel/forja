"""Memcached From Scratch — stage 1: the ring, and the hash that must not move.

The finished implementation. The reasoning — why virtual nodes, why md5
instead of `hash()`, why the next point clockwise owns the key, why a
successor list skips nodes it already named — lives in the DESIGN DECISION
blocks of `stage_01.py`.
"""

import bisect

from world import CacheError, stable_hash

#: One point per real node per entry. 150 is the number `system-design`'s
#: consistent-hash ring uses for the same reason: fewer lumps, one memory
#: cost; the demo prints what each choice actually does to the spread.
VNODES = 150

class HashRing:
    """Keys to nodes, with no server ever seeing the mapping."""

    def __init__(self, vnodes=VNODES):
        if isinstance(vnodes, bool) or not isinstance(vnodes, int) or vnodes <= 0:
            raise CacheError("HashRing(vnodes=%r): vnodes is a positive int"
                             % (vnodes,))
        self._vnodes = vnodes
        self._points = []            # sorted (position, node) tuples
        self._nodes = set()

    def add_node(self, name):
        if not isinstance(name, str) or not name:
            raise CacheError("add_node(%r): a node is a non-empty string"
                             % (name,))
        if name in self._nodes:
            raise CacheError("add_node('%s'): the node is already on the ring"
                             % name)
        for i in range(self._vnodes):
            pos = stable_hash("%s#%d" % (name, i))
            bisect.insort(self._points, (pos, name))
        self._nodes.add(name)

    def remove_node(self, name):
        if name not in self._nodes:
            raise CacheError("remove_node('%s'): no such node on the ring" % name)
        self._points = [p for p in self._points if p[1] != name]
        self._nodes.discard(name)

    def nodes(self):
        return frozenset(self._nodes)

    def positions(self):
        return tuple(self._points)

    def route(self, key):
        if not isinstance(key, str) or not key:
            raise CacheError("route(%r): a key is a non-empty string" % (key,))
        if not self._points:
            raise CacheError("ring has no nodes to route '%s'" % key)
        pos = stable_hash(key)
        i = bisect.bisect_right(self._points, (pos, "\uffff"))
        if i == len(self._points):
            i = 0
        return self._points[i][1]

    def successors(self, key, count):
        if count < 1:
            raise CacheError("successors('%s', %d): count is at least 1"
                             % (key, count))
        if not self._points:
            raise CacheError("ring has no nodes to route '%s'" % key)
        pos = stable_hash(key)
        n = len(self._points)
        i = bisect.bisect_right(self._points, (pos, "\uffff"))
        out = []
        seen = set()
        for step in range(n):
            node = self._points[(i + step) % n][1]
            if node in seen:
                continue
            seen.add(node)
            out.append(node)
            if len(out) == count:
                break
        return out



if __name__ == "__main__":
    ring = HashRing()
    for i in range(9):
        ring.add_node("node-%d" % i)
    keys = ["k%d" % i for i in range(90000)]
    counts = {}
    for k in keys:
        counts[ring.route(k)] = counts.get(ring.route(k), 0) + 1
    ideal = len(keys) // 9
    worst = max(abs(c - ideal) for c in counts.values())
    print("9 nodes, 90k keys: ideal %d/node, worst deviation %d (%.1f%%)"
          % (ideal, worst, 100.0 * worst / ideal))

    small = HashRing(vnodes=1)
    for i in range(9):
        small.add_node("node-%d" % i)
    counts = {}
    for k in keys:
        counts[small.route(k)] = counts.get(small.route(k), 0) + 1
    worst = max(abs(c - ideal) for c in counts.values())
    print("same ring with 1 vnode/node: worst deviation %d (%.1f%%)"
          % (worst, 100.0 * worst / ideal))

    before = [ring.route(k) for k in keys]
    ring.remove_node("node-3")
    after = [ring.route(k) for k in keys]
    moved = sum(1 for a, b in zip(before, after) if a != b)
    print("dropping 1 of 9 nodes moved %d keys (%.1f%%; mod-9 hashing moves ~%.0f%%)"
          % (moved, 100.0 * moved / len(keys), 100.0 * 8 / 9))

