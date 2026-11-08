"""Memcached From Scratch — stage 10: the capstone, two runs, one byte string.

Every stage so far is a component; this one wires them into a machine:
frontends with a flight and a coin (stage 7), a ring of slab stores
(stages 1 and 3) that the frontends' rebuilds fall through to, one origin,
one script of 744 requests, and a canonical report that two identical runs
must produce BYTE-BY-BYTE.

DESIGN DECISION — why is the report's sha256 pinned by the check?
    The tempting alternative is checking the report's fields and trusting
    the encoding. Its cost is the leak this course has refused everywhere:
    `hash()` seeds, float timestamps, an RNG — any one of them makes two
    runs differ somewhere invisible, and the field-by-field check passes
    while the bytes do not. The digest is the whole course's determinism
    claim in one hex string: if it moves, a non-deterministic choice
    entered the machine.

DESIGN DECISION — why does NodeTier.cost() return the ORIGIN's cost even
when the node holds the copy?
    The tempting alternative is pricing a node hit at ~0 ticks, "honest"
    to what this request actually paid. Its cost is the coin: stage 6/7's
    herding probability is FETCH_COST / recompute — a decision made BEFORE
    the rebuild, by a frontend that cannot see which tier will answer.
    The price the coin uses is the worst case the frontend is hedging
    against. Pricing with hindsight is pricing with information the system
    does not have.

DESIGN DECISION — why does a `set` fetch through the tier but the follow-up
`get` issue no query at all?
    The write-through lands on ARRIVAL (store_value at tick now — a
    synchronous write is not in flight, stage 7), so the get one tick
    later hits the entry directly. The check pins it: set-then-get costs
    exactly one origin read and zero node hits. A design where the set
    stored asynchronously would make the get wait or re-fetch — the cap-
    stone's two-timeline trap in one row.

DESIGN DECISION — why are arrival ticks and clock ticks kept apart?
    The script says a request ARRIVES at tick t; the shared clock is the
    origin's busy time, advancing by each rebuild's cost. The tempting
    alternative is one timeline for both. Its cost is a clock that runs
    backwards against the script the moment any rebuild costs ticks —
    requests landing "before" they were scheduled. Two timelines, named,
    is the only honest model of a cache whose work is deferred.

TODO: implement `request_script`, `NodeTier.__init__`, `cost`, `fetch`,
`run`, `canonical`, `run_bytes`, `digest`.
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
    """Validate the run's script: rows of (tick, cache, op, key), op
    get|set. Refuse a non-list or empty script, a row of the wrong shape,
    a bool/negative/non-int tick, a script that goes BACKWARDS (the refusal
    names the row number and both ticks), a non-text cache or key, an
    unknown op — all BEFORE anything runs, so a badly-sorted script fails
    with its row number instead of mid-run."""
    raise NotImplementedError("stage 10: implement request_script()")


class NodeTier:
    """The ring of memcached nodes a frontend's rebuild falls through to:
    route by the stage-1 ring, read the stage-3 slab, and only then the
    origin.

    It quacks like the Origin the stage-7 cache was built against —
    `cost(key)` and `fetch(key, clock)` — which is the whole point: the
    frontends do not know, and must not care, how far down the tier their
    rebuild was answered. `node_hits` is the per-node served ledger."""

    def __init__(self, ring, stores, origin):
        raise NotImplementedError("stage 10: implement NodeTier.__init__()")

    def cost(self, key):
        """The ORIGIN's cost — the worst case the coin prices against,
        identical whether or not a node holds the copy."""
        raise NotImplementedError("stage 10: implement NodeTier.cost()")

    def fetch(self, key, clock):
        """Served by the routed node's slab if it holds `key` live (count
        it in `node_hits`); else read the origin and STORE the value on
        the routed node."""
        raise NotImplementedError("stage 10: implement NodeTier.fetch()")


def run(rows, script, caches, nodes=("n1", "n2", "n3"), ttl=10, window=4,
        recompute=None):
    """One deterministic pass of the whole machine — frontends as
    SingleFlight(mutex=True, window, recompute, name=cache), a ring of
    LruSlab stores, one origin — returning `canonical(report)`.

    Script rows: `get` calls the named cache's `request(key, tick, ttl)`;
    `set` fetches the value through the tier and `store_value`s it on
    arrival. A cache or key the run does not have is refused with the
    script's own words. The report is exactly:
      origin_queries : origin.queries
      busy           : clock.now
      node_hits      : [[node, count] for node in sorted(nodes)]
      caches         : [[name, waits, early, sum(queries_at.values())]
                        for name in sorted(caches)]
    `recompute` defaults to 2 ticks for every row."""
    raise NotImplementedError("stage 10: implement run()")


def canonical(report):
    """The one encoding: json.dumps(report, sort_keys=True,
    separators=(",", ":")). A float anywhere in the top-level fields is a
    refusal naming the field — a canonical report is ints and strings, and
    a float means someone divided without deciding to."""
    raise NotImplementedError("stage 10: implement canonical()")


def run_bytes(*args, **kw):
    """`run(...).encode("utf-8")` — the byte string the digest is taken
    of."""
    raise NotImplementedError("stage 10: implement run_bytes()")


def digest(data):
    """hashlib.sha256(data).hexdigest() — the run's fingerprint."""
    raise NotImplementedError("stage 10: implement digest()")
