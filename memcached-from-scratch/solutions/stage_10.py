"""Memcached From Scratch — stage 10: the capstone, two runs, one byte string.

The finished implementation. The reasoning — why every number in the report
must be an int or a string and never a float of wall time, what the
canonical encoding is, and why the run's inputs (the script of requests and
the clock plan) are the ONLY randomness the machine is allowed — lives in
the DESIGN DECISION blocks of `stage_10.py`.
"""

import hashlib
import json

from world import CacheError, Clock, Origin, stable_hash
from stage_01 import HashRing
from stage_03 import LruSlab
from stage_07 import SingleFlight

#: Server-tier page budget, stretched so eviction never intrudes on a demo
#: whose lesson is the byte-for-byte replay, not the LRU.
NODE_SLOTS = 4096


def request_script(events):
    """Validate the run's script: (tick, cache, op, key) rows, op get|set.
    Ticks must be non-decreasing — the clock rule checked *before* anything
    runs, so a badly-sorted script fails with its row number instead of
    mid-run."""
    if not isinstance(events, list) or not events:
        raise CacheError("script is a non-empty list")
    last = -1
    for n, ev in enumerate(events):
        if not isinstance(ev, tuple) or len(ev) != 4:
            raise CacheError("script row %d: %r, expected (tick, cache, op, key)"
                             % (n, ev))
        tick, cache, op, key = ev
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise CacheError("script row %d: tick %r is a non-negative int"
                             % (n, tick))
        if tick < last:
            raise CacheError("script row %d goes backwards: %d after %d"
                             % (n, tick, last))
        if not isinstance(cache, str) or not isinstance(key, str):
            raise CacheError("script row %d: cache and key are strings" % n)
        if op not in ("get", "set"):
            raise CacheError("script row %d: op %r is get or set" % (n, op))
        last = tick
    return events


class NodeTier:
    """The ring of memcached nodes a frontend's rebuild falls through to:
    route by the stage-1 ring, read the stage-3 slab, and only then the
    origin. It quacks like the Origin the stage-7 cache was built against —
    `cost(key)` and `fetch(key, clock)` — which is the whole point: the
    frontends do not know, and must not care, how far down the tier their
    rebuild was answered. `cost` is the origin's cost even when the node
    holds the copy, because the coin prices the *worst* case: the paper
    herded for the backend it could not see into."""

    def __init__(self, ring, stores, origin):
        self._ring = ring
        self._stores = stores
        self._origin = origin
        self.node_hits = {}       # node -> gets answered from its slab

    def cost(self, key):
        return self._origin.cost(key)

    def fetch(self, key, clock):
        name = self._ring.route(key)
        now = clock.now
        item = self._stores[name].get(key, now)
        if item is not None:
            self.node_hits[name] = self.node_hits.get(name, 0) + 1
            return item.value
        value = self._origin.fetch(key, clock)
        self._stores[name].store(key, value, now)
        return value


def run(rows, script, caches, nodes=("n1", "n2", "n3"), ttl=10, window=4,
        recompute=None):
    """One deterministic pass of the whole machine — frontends with mutex +
    herding (stage 7), a ring of slab stores (stages 1 and 3), one origin —
    and the canonical report it leaves behind.

    Two runs of the same script over fresh structures must produce byte-
    identical reports, which is only possible because every choice in the
    machine is a function of (key, node, tick): the ring is md5 of the key,
    the clock moves by integer costs, the LRU order is stamps, and the
    herding coin is `stable_hash` of names and ticks. `hash()` seeds, float
    timestamps and RNG would each make this file a story about a system
    instead of the system; the digest below is the proof that it is one."""
    clock = Clock()
    origin = Origin(rows)
    ring = HashRing()
    for n in nodes:
        ring.add_node(n)
    stores = {n: LruSlab(capacity_per_page=NODE_SLOTS,
                         max_pages_per_class=1) for n in nodes}
    tier = NodeTier(ring, stores, origin)
    if recompute is None:
        recompute = {k: 2 for k in rows}
    flights = {c: SingleFlight(clock, tier, mutex=True, window=window,
                               recompute=recompute, name=c) for c in caches}
    for tick, cache, op, key in script:
        if cache not in flights:
            raise CacheError("script names cache %r that the run does not have"
                             % cache)
        if key not in rows:
            raise CacheError("script asks for '%s' the origin has no row for"
                             % key)
        # Two timelines, by design: `tick` is when the request ARRIVES, and
        # `clock` is the origin's busy time each rebuild advances.
        # Conflating them is the capstone trap — arrivals would "run
        # backwards" the moment a rebuild costed ticks.
        if op == "set":
            value = tier.fetch(key, clock)       # write-through to the tier
            flights[cache].store_value(key, value, tick, ttl)
        else:
            flights[cache].request(key, tick, ttl)
    per_cache = []
    for c in sorted(flights):
        f = flights[c]
        per_cache.append([c, f.waits, f.early, sum(f.queries_at.values())])
    report = {
        "origin_queries": origin.queries,
        "busy": clock.now,
        "node_hits": [ [n, tier.node_hits.get(n, 0)] for n in sorted(nodes)],
        "caches": per_cache,
    }
    return canonical(report)


def canonical(report):
    """The one encoding: sorted keys, no spaces, integers only. A float in
    this dict is a bug — it means someone divided without deciding to."""
    for key, value in report.items():
        if isinstance(value, float):
            raise CacheError("report field %r is a float: a canonical report "
                             "is ints and strings" % key)
    return json.dumps(report, sort_keys=True, separators=(",", ":"))


def run_bytes(*args, **kw):
    return run(*args, **kw).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    rows = {"k%d" % i: ("v%d" % i, 3) for i in range(20)}
    keys = sorted(rows)
    caches = ["fe-%02d" % i for i in range(4)]
    script = []
    # Phase 1, tick 0: every frontend warms every key — 20 rebuilds each,
    # the origin paying once per (frontend, key) and the tier once per key.
    for c in caches:
        for k in keys:
            script.append((0, c, "get", k))
    # Phase 2, ticks 1-6: every frontend hammers k0 — the depth the mutex
    # answers: the first arrivals land while the tick-0 rebuild is in flight.
    for t in range(1, 7):
        for c in caches:
            script.append((t, c, "get", "k0"))
    # Phase 3, ticks 7-8: everyone asks everything inside the death window —
    # the width the coin answers, decided apart per frontend by its salt.
    for t in (7, 8):
        for c in caches:
            for k in keys:
                script.append((t, c, "get", k))
    # Phase 4, ticks 10-15: the steady walk with short ttl: rebuilds asked
    # again while in flight, herded deaths, and the slab's own expiry all
    # interact on one clock.
    for t in range(10, 16):
        for c in caches:
            for k in keys:
                script.append((t, c, "get", k))
    request_script(script)
    a = run(rows, script, caches, ttl=6, window=2)
    b = run(rows, script, caches, ttl=6, window=2)
    print("rows:", len(script), "| two runs identical:", a == b)
    print("digest:", digest(a.encode("utf-8"))[:16])
    print(a)
