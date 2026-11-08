"""Memcached From Scratch — stage 8: backup replication and the warm restart.

The finished implementation. The reasoning — why the replica lives on the
ring's *successor* (so its range is exactly the one the primary's re-route
inherits), why three nodes with replication factor two makes a single-node
loss a zero-query event, and why the restart must refill what reads
survived, lives in the DESIGN DECISION blocks of `stage_08.py`.
"""

from world import CacheError, Clock, Origin

#: A node's store is stage 3's slab with its pages stretched far past the
#: demo's key count, so eviction never intrudes: stage 8's lesson is the
#: replica, and a demo whose values died of eviction would teach that
#: instead.
NODE_SLOTS = 10000


def _fresh_store():
    from stage_03 import LruSlab
    return LruSlab(capacity_per_page=NODE_SLOTS, max_pages_per_class=1)


class ReplicatedCache:
    """A ring in front of per-node slab stores, each write landing on the
    primary *and* its clockwise successors up to `factor`.

    Why replication follows the ring instead of a random peer: when a node
    disappears, every key whose primary died re-routes to exactly the node
    clockwise of it — which is precisely where the replica was written. The
    backup is not insurance; it is the new primary, already warm. With 3
    nodes and factor 2 every key lives on 2 of 3 nodes, so *any* single
    node's loss leaves every key served by a live copy: zero origin queries
    across the failure. A plain cache hands the dead node's whole range to
    the origin at once.

    `crash` empties a node's store and drops it from the ring; `restart`
    re-adds it empty. A read answered by holder `i` refills *every other*
    holder missing the copy — the restarted node re-warms from traffic that
    returns to its range, which is the shape of a real warm restart: the
    ring moves on instantly, the returning node fills back in, and the
    origin never sees the difference.
    """

    def __init__(self, ring, stores, origin, clock, factor=2):
        if isinstance(factor, bool) or not isinstance(factor, int) or factor < 1:
            raise CacheError("factor %r: at least the primary holds every "
                             "write" % (factor,))
        self._ring = ring
        self._stores = stores          # name -> LruSlab
        self._origin = origin
        self._clock = clock
        self._factor = factor
        self.backfills = 0             # reads that refilled a missing holder
        self.fallback_hits = 0         # served by a non-primary holder

    def _holders(self, key):
        return self._ring.successors(key, min(self._factor,
                                              len(self._ring.nodes())))

    def set(self, key, value, ttl):
        now = self._clock.now
        exp = now + ttl if ttl else 0
        for name in self._holders(key):
            self._stores[name].store(key, value, now, exptime=exp)

    def get(self, key):
        now = self._clock.now
        holders = self._holders(key)
        for i, name in enumerate(holders):
            item = self._stores[name].get(key, now)
            if item is None:
                continue
            if i:
                self.fallback_hits += 1
            for other in holders:
                if other == name:
                    continue
                if self._stores[other].get(key, now, mark=False) is None:
                    self._stores[other].store(key, item.value, now,
                                              exptime=item.exptime)
                    self.backfills += 1
            return item.value
        value = self._origin.fetch(key, self._clock)
        self.set(key, value, ttl=0)    # the rebuilt copy is permanent
        return value

    def crash(self, name):
        """A node dies: its memory is gone and the ring forgets it."""
        if name not in self._ring.nodes():
            raise CacheError("crash('%s'): the ring has no node '%s'"
                             % (name, name))
        self._stores[name] = _fresh_store()
        self._ring.remove_node(name)

    def restart(self, name):
        """The same node returns, empty — warm restart starts from here."""
        if name in self._ring.nodes():
            raise CacheError("restart('%s'): the ring already routes to '%s'"
                             % (name, name))
        self._stores[name] = _fresh_store()
        self._ring.add_node(name)


def _three_nodes(rows):
    """Fresh ring, stores, origin for the demos and checks."""
    from stage_01 import HashRing
    clock = Clock()
    origin = Origin(rows)
    ring = HashRing()
    names = ("n1", "n2", "n3")
    for n in names:
        ring.add_node(n)
    stores = {n: _fresh_store() for n in names}
    return clock, origin, ring, stores


def failure_report(rows, replicate, crash_at="n2", keys=None):
    """Warm every key, crash `crash_at`, read every key again. Returns
    (queries while warming, queries after the crash, fallback hits)."""
    if keys is None:
        keys = sorted(rows)
    clock, origin, ring, stores = _three_nodes(rows)
    cache = ReplicatedCache(ring, stores, origin, clock,
                            factor=2 if replicate else 1)
    for k in keys:
        cache.get(k)
    warm = origin.queries
    cache.crash(crash_at)
    for k in keys:
        cache.get(k)
    return warm, origin.queries - warm, cache.fallback_hits


def restart_report(rows, keys=None, crash_at="n2"):
    """Warm, crash, serve, restart the node empty, serve every key again.
    The origin's silence across the restart is the thesis; `backfills` is
    how much traffic re-warmed the returning node, and
    `items_on_restarted` counts what it holds by the end."""
    if keys is None:
        keys = sorted(rows)
    clock, origin, ring, stores = _three_nodes(rows)
    cache = ReplicatedCache(ring, stores, origin, clock, factor=2)
    for k in keys:
        cache.get(k)
    cache.crash(crash_at)
    q_before = origin.queries
    for k in keys:
        cache.get(k)
    crash_queries = origin.queries - q_before
    cache.restart(crash_at)
    q_before = origin.queries
    for k in keys:
        cache.get(k)
    return {"queries_during_crash": crash_queries,
            "queries_after_restart": origin.queries - q_before,
            "backfills": cache.backfills,
            "fallback_hits": cache.fallback_hits,
            "items_on_restarted": stores[crash_at].live()}


if __name__ == "__main__":
    rows = {"k%d" % i: ("v%d" % i, 5) for i in range(90)}
    for replicate in (False, True):
        warm, after, fallbacks = failure_report(rows, replicate)
        print("%-14s warm %3d | crash of 1 of 3 nodes: %3d origin queries"
              % ("replicated" if replicate else "plain cache", warm, after))
    r = restart_report(rows)
    print("restart:  %3d origin queries across the returning node | %3d "
          "reads rescued by a backup | %3d copies refilled | %3d items live "
          "on it" % (r["queries_after_restart"], r["fallback_hits"],
                     r["backfills"], r["items_on_restarted"]))
