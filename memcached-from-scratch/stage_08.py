"""Memcached From Scratch — stage 8: backup replication and the warm restart.

Everything so far has been a client protecting itself from the origin.
This stage moves the protection INTO the ring: every write lands on the
primary and its clockwise successors, so when a node dies the data is
already standing on the node that inherits its range — the crash costs
zero origin queries — and a restarting node re-warms from returning
traffic instead of the backend.

DESIGN DECISION — why does replication follow the RING (successors) instead
of random peers?
    The tempting alternative is "copy each write to two random nodes". Its
    cost is the crash: when n2 dies, the keys whose primary was n2
    re-route — by stage 1's own rule — to the node clockwise of n2's
    points. If the copies sit on random machines, the new primary holds
    nothing, the readers miss, and the origin pays for the dead node's
    whole range anyway. Replicating to the successor means the backup IS
    the failover target: already warm, zero queries. The check pins it:
    losing 1 of 3 nodes costs a plain cache 28 rebuilds and a factor-2
    replicated one 0.

DESIGN DECISION — why does a read answered OFF-holder refill every missing
holder?
    The tempting alternative is to serve the hit and move on. Its cost is
    that the restart never warms up: n2 comes back empty, its range
    re-routes to it on paper but every read finds nothing there and
    re-fetches forever. The get that finds the copy on holder i stores it
    into every OTHER holder that lacks it — `backfills` — so traffic that
    returns to a range fills the returning node. The origin never sees the
    difference: queries_after_restart == 0 while the restarted node ends
    the sweep holding 56 of 90 items.

DESIGN DECISION — why does a refill keep the ORIGINAL exptime instead of
restarting the ttl?
    The tempting alternative is `now + ttl` on the backfilled copy. Its
    cost is a resurrection: an item that was scheduled to die at tick 100
    now lives 100 ticks past every refill. A copy is a COPY — same value,
    same death date. The sweep to tick 100 proves it: one origin query,
    not a trickle of them.

DESIGN DECISION — why is `crash` emptiness + ring removal, not a flag?
    The tempting alternative is marking the node down and keeping its
    store readable. Its cost is the wrong lesson: a dead server's memory
    is GONE. crash() empties the store and drops the node from the ring;
    restart() puts it back EMPTY. Anything else measures a different
    failure than the one the fleet actually has.

TODO: implement `ReplicatedCache.__init__`, `_holders`, `set`, `get`,
`crash`, `restart`, `failure_report`, `restart_report`.
"""

from world import CacheError, Clock, Origin

#: Replica stores get a page budget stretched so eviction never intrudes:
#: a demo whose values died of LRU pressure would teach that instead.
NODE_SLOTS = 10000


class ReplicatedCache:
    """A ring in front of per-node slab stores, each write landing on the
    primary *and* its clockwise successors up to `factor`.

    `get` walks the holders clockwise: served by holder 0 is a plain hit;
    served by a later holder is a `fallback_hits` event — and the copy is
    refilled into every holder missing it (`backfills`). A key nobody
    holds rebuilds from the origin and is written through all holders,
    permanent. `factor` < 1 or bool is refused: at least the primary holds
    every write."""

    def __init__(self, ring, stores, origin, clock, factor=2):
        raise NotImplementedError("stage 8: implement ReplicatedCache.__init__()")

    def _holders(self, key):
        """The clockwise distinct nodes holding this key: successors up to
        min(factor, ring size)."""
        raise NotImplementedError("stage 8: implement ReplicatedCache._holders()")

    def set(self, key, value, ttl):
        """Write through every holder: exptime is the ABSOLUTE tick
        now + ttl (0 = never), identical on all copies."""
        raise NotImplementedError("stage 8: implement ReplicatedCache.set()")

    def get(self, key):
        """First live copy clockwise wins; an off-holder serve counts
        `fallback_hits` and refills every missing holder with the SAME
        exptime; a cold key fetches the origin once and writes through."""
        raise NotImplementedError("stage 8: implement ReplicatedCache.get()")

    def crash(self, name):
        """A node dies: its memory is gone and the ring forgets it. Refuse
        a name the ring does not have."""
        raise NotImplementedError("stage 8: implement ReplicatedCache.crash()")

    def restart(self, name):
        """The same node returns, EMPTY. Refuse a name already on the
        ring."""
        raise NotImplementedError("stage 8: implement ReplicatedCache.restart()")


def failure_report(rows, replicate, crash_at="n2", keys=None):
    """Warm every key, crash `crash_at`, read every key again.
    Returns (queries while warming, queries after the crash, fallback
    hits) — replicate=False is the plain cache (factor 1), the control the
    28-vs-0 comparison needs."""
    raise NotImplementedError("stage 8: implement failure_report()")


def restart_report(rows, keys=None, crash_at="n2"):
    """Warm, crash, serve, restart the node empty, serve every key again.
    Returns {"queries_during_crash", "queries_after_restart", "backfills",
    "fallback_hits", "items_on_restarted"} — the origin's silence across
    the restart is the thesis."""
    raise NotImplementedError("stage 8: implement restart_report()")
