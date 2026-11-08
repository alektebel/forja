"""Memcached From Scratch — stage 6: statistical herding, spread over ticks.

The finished implementation. The reasoning — why a synchronized expiry on
many caches is a spike on the origin, why the probability of early expiry
ramps with the item's age instead of a random offset chosen once, why an
item that is expensive to recompute herds *less*, and why the coin is
`stable_hash(f"{cache}#{key}#{tick}")` — lives in the DESIGN DECISION
blocks of `stage_06.py`.
"""

from world import CacheError, stable_hash

#: Ticks to serve one fetch once the backend work is done — the network and
#: serialization the paper contrasts with recompute cost. Fixed, not hashed:
#: it is a property of the pipe, not of the item.
FETCH_COST = 4


class Herder:
    """Many frontend caches, one origin, requests arriving at counted ticks.

    Each cache holds `key -> (value, expire_at)`. A request that finds the
    item at or past `expire_at` rebuilds from the origin. Warm every cache
    at tick 0 and — with no window — every copy of every key dies on the
    same tick: the origin sees `caches x keys` queries in one column. That
    column is the herd the paper measured at Facebook scale.

    Inside the final `window` ticks, each request rolls the coin
    `stable_hash(f"{cache}#{key}#{tick}")` — one decision per cache per
    item per tick, because each frontend decides *for itself* — and expires
    the item early with probability `ramp * price`:

    - `ramp` = age past the window's edge / window: 0 at the edge, 1 at
      death. Deterministic jitter (offset chosen at store time) gives every
      copy of a key the same window and moves the spike, not its height; a
      ramp that *grows* is what thins the column.
    - `price` = min(1, FETCH_COST / recompute): an item cheap for the
      backend to rebuild goes early often; one that takes the backend a
      long time barely ever goes, because early expiry would just re-pay
      that expensive rebuild sooner.

    `rebuilds_at[tick]` is the origin's exposure: a flat profile is the
    win, one tall column is the herd. Herding does NOT reduce total work —
    the same rebuilds happen, spread apart. A check that counts only
    `sum(rebuilds_at.values())` cannot tell the difference; it must look at
    `peak()`.
    """

    def __init__(self, caches, clock, origin, window=0, recompute=None):
        if isinstance(window, bool) or not isinstance(window, int) or window < 0:
            raise CacheError("window %r: a non-negative int of ticks" % (window,))
        self._caches = {name: {} for name in caches}
        self._clock = clock
        self._origin = origin
        self._window = window
        self._recompute = dict(recompute or {})
        self.rebuilds_at = {}    # tick -> rebuilds issued at that tick
        self.early = 0           # rebuilds that fired before expire_at
        self.at_death = 0        # rebuilds at or after expire_at
        self.hits = 0            # replies served from a live cache entry

    def _coin(self, cache_name, key):
        h = stable_hash("%s#%s#%d" % (cache_name, key, self._clock.now))
        return (h & 0xFFFFFFFF) / float(0xFFFFFFFF)

    def request(self, cache_name, key, ttl):
        now = self._clock.now
        entry = self._caches[cache_name].get(key)
        if entry is not None:
            value, expire_at = entry
            if now >= expire_at:
                self.at_death += 1             # only a true death counts here
            elif self._window and now >= expire_at - self._window:
                ramp = (now - (expire_at - self._window)) / float(self._window)
                recompute = self._recompute.get(key, 1)
                if isinstance(recompute, bool) or recompute <= 0:
                    raise CacheError("recompute cost for '%s' is %r: a "
                                     "positive number of ticks" % (key, recompute))
                price = min(1.0, FETCH_COST / recompute)
                if self._coin(cache_name, key) < ramp * price:
                    self.early += 1            # expire early: rebuild below
                else:
                    self.hits += 1
                    return value
            else:
                self.hits += 1
                return value
        value = self._origin.fetch(key, self._clock)
        self.rebuilds_at[now] = self.rebuilds_at.get(now, 0) + 1
        self._caches[cache_name][key] = (value, now + ttl)
        return value

    def peak(self):
        return max(self.rebuilds_at.values()) if self.rebuilds_at else 0

    def spike(self, from_tick=1):
        """The tallest rebuild column at or after `from_tick` — for `wave`,
        the death neighbourhood. Tick 0 is the warm-up and lies."""
        cols = [v for t, v in self.rebuilds_at.items() if t >= from_tick]
        return max(cols) if cols else 0

    def stats(self, from_tick=1):
        return {"total": sum(self.rebuilds_at.values()),
                "spike": self.spike(from_tick),
                "early": self.early, "at_death": self.at_death,
                "hits": self.hits}


def wave(keys, caches, ttl=50, window=0, recompute=None, sweep_to=None):
    """Warm every cache with every key at tick 0 — the synchronized death
    the paper starts from — then have every cache request every key again
    each tick up to `sweep_to`, then report the spike.
    The origin rows cost zero rebuild ticks *on the clock* so that warming
    and herding decisions land on their scheduled tick and the profile
    columns are honest. The economic cost lives in `recompute`, which
    prices the early-expiry coin — the two numbers answer different
    questions and are kept apart on purpose.
    """
    from world import Clock, Origin
    if sweep_to is None:
        sweep_to = ttl
    rows = {k: (k + "-v", 0) for k in keys}
    clock = Clock()
    origin = Origin(rows)
    herder = Herder(caches, clock, origin, window=window, recompute=recompute)
    for c in caches:
        for k in keys:
            herder.request(c, k, ttl)
    for t in range(1, sweep_to + 1):
        clock.advance(t - clock.now)
        for c in caches:
            for k in keys:
                herder.request(c, k, ttl)
    s = herder.stats(from_tick=1)
    s["profile"] = dict(herder.rebuilds_at)
    return s


if __name__ == "__main__":
    keys = ["k%d" % i for i in range(25)]
    caches = ["fe-%02d" % i for i in range(40)]
    cheap = {k: 2 for k in keys}       # rebuild cheap: herd eagerly
    dear = {k: 100 for k in keys}      # rebuild expensive: herd barely
    no_w = wave(keys, caches, ttl=50, window=0)
    w_cheap = wave(keys, caches, ttl=50, window=20, recompute=cheap)
    w_dear = wave(keys, caches, ttl=50, window=20, recompute=dear)
    for name, s in (("no window", no_w), ("window, cheap rebuild", w_cheap),
                    ("window, expensive rebuild", w_dear)):
        print("%-26s total %4d  spike %4d  early %4d  at_death %4d"
              % (name, s["total"], s["spike"], s["early"], s["at_death"]))
