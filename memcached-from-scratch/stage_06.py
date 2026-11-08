"""Memcached From Scratch — stage 6: statistical herding, spread over ticks.

Warm 40 frontends with 25 keys at tick 0 with ttl 50 and watch the origin:
tick 50 arrives and every copy of every key dies on the same tick — 1,000
rebuilds in one column. The paper's fix is to make each copy decide to die
a little early, at a probability set by what the backend can afford.

DESIGN DECISION — why a per-request coin at read time, not a random offset
chosen at store time?
    The tempting alternative is `expire_at = now + ttl - jitter(key)`: each
    copy dies at its own tick, spread over the window. Its cost is that the
    column moves but does not thin — every copy still dies exactly once,
    and the tick the deaths land on is still tall in expectation for the
    batch that shares it. A ramp that GROWS with age and is tested on every
    request is what thins the column: most copies die early before the
    death tick even arrives.

DESIGN DECISION — why is the early-expiry probability `ramp * (FETCH_COST /
recompute)`?
    The tempting alternative is one uniform probability for everything. Its
    cost is the backend: a key that takes the origin 100 ticks to rebuild
    now gets rebuilt EARLY — sooner than it had to — for 100 ticks of work
    the fleet could have deferred. Priced against a fixed FETCH_COST of 4,
    a cheap rebuild goes early often (probability up to 1), an expensive
    one barely at all. Herding is an economic decision, and the check pins
    the direction: dear spikes HIGHER than cheap.

DESIGN DECISION — why does the total never change?
    The tempting alternative is a scheme whose `total` drops — looks like a
    20% capacity win! Its cost is a stale cache: a copy that skips a
    rebuild it owed is serving data past its ttl. Herding RELOCATES work
    over ticks; `sum(profile.values())` identical across waves is the
    proof the coin moved deaths, not correctness.

DESIGN DECISION — why is the coin salted with the CACHE NAME?
    The tempting alternative is `stable_hash(key + tick)`, one decision per
    key per tick shared by every frontend. Its cost is perfect
    correlation: every copy of a key flips the same coin and dies on the
    same early tick — the herd re-forms one tick sooner. Fourty frontends
    must make forty independent decisions, which is the whole word
    "statistical" in statistical herding.

TODO: implement `Herder.__init__`, `request`, `peak`, `spike`, `stats` and
`wave`.
"""

from world import CacheError, stable_hash

#: The price of one rebuild the coin is measured against: 4 ticks of origin
#: work, the course's fixed number.
FETCH_COST = 4


class Herder:
    """Many frontend caches, one origin, requests arriving at counted ticks.

    Each cache holds `key -> (value, expire_at)`. A request that finds the
    item at or past `expire_at` rebuilds from the origin. Inside the final
    `window` ticks the request rolls the coin — early expiry with
    probability `ramp * price` — and a death column that is a thousand tall
    with no window becomes a spread of small columns with one.
    """

    def __init__(self, caches, clock, origin, window=0, recompute=None):
        raise NotImplementedError("stage 6: implement Herder.__init__()")

    def request(self, cache_name, key, ttl):
        """Serve one get from `cache_name`'s copy of `key`.

        Live and outside the window (or window==0): a hit, return the
        entry's value. At or past expire_at: a true death — `at_death` and
        rebuild. Inside the final `window` ticks: roll
        `stable_hash("%s#%s#%d" % (cache, key, tick))` and compare against
        `ramp * min(1, FETCH_COST / recompute[key])`, ramp = age past the
        window's edge over the window. Below it: `early`, expire now and
        rebuild; else a hit. Every rebuild stores `(value, now + ttl)` and
        counts a column in `rebuilds_at[now]`. A bool or non-positive
        recompute cost INSIDE the window is refused by key."""
        raise NotImplementedError("stage 6: implement Herder.request()")

    def peak(self):
        """Tallest rebuild column over ALL ticks — the warm-up included."""
        raise NotImplementedError("stage 6: implement Herder.peak()")

    def spike(self, from_tick=1):
        """Tallest rebuild column at or after `from_tick`: tick 0 is the
        warm-up and lies; the death neighbourhood starts at 1."""
        raise NotImplementedError("stage 6: implement Herder.spike()")

    def stats(self, from_tick=1):
        """{"total", "spike", "early", "at_death", "hits"}."""
        raise NotImplementedError("stage 6: implement Herder.stats()")


def wave(keys, caches, ttl=50, window=0, recompute=None, sweep_to=None):
    """Warm every cache with every key at tick 0 — the synchronized death
    the paper starts from — then have every cache request every key again
    at every tick up to `sweep_to` (default `ttl`), and return `stats`
    plus `profile` (the per-tick rebuild columns, tick -> count).

    The origin rows cost ZERO ticks on the clock so deaths land on the
    scheduled tick and the columns are honest; the economic cost lives in
    `recompute`, which prices the coin. Two waves with the same arguments
    must produce the same `profile`, dict for dict."""
    raise NotImplementedError("stage 6: implement wave()")
