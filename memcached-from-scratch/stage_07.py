"""Memcached From Scratch — stage 7: single-flight, and why the mutex alone
loses to the wide wave.

Stage 6 spread a synchronized expiry over ticks. This stage adds the other
defence — a per-key flight that folds ten clients asking the same cold key
into one rebuild — and then shows, on the shared clock, that the two
protections do NOT protect each other's shape: the mutex fixes depth and
leaves width untouched; the coin fixes width and does nothing for a cold
wave.

DESIGN DECISION — why does the leader store its value at the REPLY tick,
not the arrival tick?
    The tempting alternative is to stamp `stored_at` when the request
    arrives. Its cost is that the in-flight window disappears — nothing
    ever "lands later", so no arrival can find a reply still on its way,
    and the mutex has nothing to wait for. Storing at now + cost is what
    makes "an arrival while the rebuild is in flight" a real state,
    checkable with integers: stored_at > arrival.

DESIGN DECISION — why does the waiting client get served with ZERO queries
while the non-mutex client re-fetches?
    The tempting alternative is to always serve the in-flight key from the
    stale-but-not-yet-replaced copy. Its cost is the stampede the mutex
    exists for: without it, ten clients on one cold key issue ten origin
    reads AND advance the clock ten costs deep — the check pins
    origin.queries 200 -> 20 and busy 6000 -> 600, both. With the mutex a
    waiter joins the leader's flight: `waits` counts it, no query, no
    ticks.

DESIGN DECISION — why does the mutex leave a synchronized DEATH column
completely intact?
    The tempting alternative is to claim the flight "also" fixes thundering
    herds. It does not: a flight is per key, per cache, and at the death
    tick every entry has already been replaced — the wave's frontends each
    rebuild their own copy at tick `ttl`, one flight per key, nothing to
    join. `frontend_wave` measures exactly this: the tick-50 column is 200
    deep with the mutex ON or OFF; only the coin (window=10) thins it to a
    spread of <= 45 while the total stays 400. Production needs both
    because they answer different shapes — depth vs width.

DESIGN DECISION — why does the flight's coin carry the cache's own NAME as
salt?
    Same reason as stage 6: frontends must decide apart. Two frontends
    sharing one coin re-join their deaths on the same early tick and the
    column survives.

TODO: implement `SingleFlight.__init__`, `request`, `store_value`, `peak`,
`cold_wave`, `frontend_wave`, `line`.
"""

from world import CacheError, Clock, Origin, stable_hash

#: Same price as stage 6: one rebuild the coin is measured against.
FETCH_COST = 4


class SingleFlight:
    """A read-through cache with two protections that fix different shapes.

    A rebuild takes the origin's cost ticks: the leader stores its value at
    the *reply* tick, not the arrival tick. `mutex=True` makes an arrival
    during that flight a waiter — served the leader's value, zero queries.
    `window`/`recompute` herd a synchronized death over ticks. Neither
    helps the other's case: that is the invariant this stage's check
    measures.
    """

    def __init__(self, clock, origin, mutex=False, window=0, recompute=None,
                 name="cache"):
        raise NotImplementedError("stage 7: implement SingleFlight.__init__()")

    def request(self, key, now, ttl):
        """Serve a get arriving at tick `now`.

        Entry with stored_at > now: a flight is in progress — join it
        (`waits += 1`, return the value, no query) if mutex, else fall
        through and fetch (the stampede). Entry live and past the window
        edge: the same ramp-priced, name-salted coin as stage 6
        (`early` on a flip). Past expire_at or missing: fetch from the
        origin — `queries_at[now] += 1` — and store
        `(value, now + cost, now + cost + ttl)`: the reply lands cost
        ticks after arrival. A bool or non-positive recompute cost inside
        the window is refused."""
        raise NotImplementedError("stage 7: implement SingleFlight.request()")

    def store_value(self, key, value, now, ttl):
        """A write-through placement for callers that already hold a fresh
        value — the capstone's `set` op. stored_at is `now`: a synchronous
        write is not in flight, so the next arrival hits."""
        raise NotImplementedError("stage 7: implement SingleFlight.store_value()")

    def peak(self, from_tick=0, to_tick=None):
        """Tallest origin-query column over arrival ticks in the range."""
        raise NotImplementedError("stage 7: implement SingleFlight.peak()")


def cold_wave(cache, keys, clients, at_tick=0, ttl=50):
    """`clients` requests for every cold key at one tick — the stampede the
    mutex was written for (depth)."""
    raise NotImplementedError("stage 7: implement cold_wave()")


def frontend_wave(mutex, window, keys, frontends, rows, recompute,
                  ttl=50, sweep_to=None):
    """`frontends` INDEPENDENT caches (names fe-00... fe-N), one shared
    clock and origin: warm every key on every cache at tick 0, then every
    cache requests every key at every tick up to `sweep_to` (default ttl).
    Returns (origin, aggregate per-tick query columns) — the width
    measurement: entries land at tick 0 and die together at tick `ttl`."""
    raise NotImplementedError("stage 7: implement frontend_wave()")


def line(label, origin, cache, from_tick=0, to_tick=None):
    """One summary row: label, origin queries, busy ticks, waits, early,
    peak column — what the demo prints."""
    raise NotImplementedError("stage 7: implement line()")
