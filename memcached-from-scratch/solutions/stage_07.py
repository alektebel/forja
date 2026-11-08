"""Memcached From Scratch — stage 7: single-flight, and why the mutex alone
loses to the *wide* wave.

The finished implementation. The reasoning — why a per-key mutex protects
the *depth* of a stampede (same key, many clients) but not its *width*
(many keys, many frontends, one death tick), what a waiter must never do
(re-fetch), and why the two waves in this demo are the actual lesson —
lives in the DESIGN DECISION blocks of `stage_07.py`.
"""

from world import CacheError, Clock, Origin, stable_hash

#: Same economic constant as stage 6: fetch-vs-recompute prices the coin.
FETCH_COST = 4


class SingleFlight:
    """A read-through cache with two protections that fix different shapes.

    A rebuild takes the origin's cost ticks: the leader stores its value at
    the *reply* tick, not the arrival tick. So an arrival while a key is
    stale but the reply has not landed yet has a real choice:

    - `mutex=True` (single-flight): that arrival is a *waiter* — counted in
      `waits`, served the leader's value, and it issues **zero** origin
      queries. 10 simultaneous clients on one cold key cost 1 rebuild.
      Without the mutex, each of those 10 clients fetches the same row 10
      times: same answers, 10x the origin work, and — the part the checks
      on `clock.now` catch — 10x the wall time.
    - `window`/`recompute` (statistical herding, stage 6): a *fresh* entry
      in its final window may expire early on the ramp-priced coin, which
      spreads a synchronized death spike over ticks. It does nothing for a
      cold wave: there is no entry to expire early.

    The point this stage refuses to skip: herding cannot fix depth, and the
    mutex cannot fix width. Width is measured as the origin's per-tick
    column: `frontends x keys` entries all warm at tick 0 die on tick
    `ttl`, and a mutex is *per key, per cache* — with one flight per key
    there is nothing left to wait for, so the column at `ttl` is still
    `keys` tall per frontend. Only the coin, rolled independently by each
    frontend, thins the column before it lands. Production needs both; a
    course that shows one half sells a coin flip.

    The shared clock advances by exactly each fetch's rebuild cost, so
    `clock.now` at the end is the origin's busy time and `origin.queries`
    its load — waiters move neither.
    """

    def __init__(self, clock, origin, mutex=False, window=0, recompute=None,
                 name="cache"):
        self._clock = clock
        self._origin = origin
        self._mutex = mutex
        self._window = window
        self._recompute = dict(recompute or {})
        self._name = name       # the coin's salt: frontends decide apart
        self._entries = {}      # key -> (value, stored_at, expire_at)
        self.waits = 0
        self.early = 0
        self.queries_at = {}    # arrival tick -> origin queries issued then

    def _coin(self, key, now):
        h = stable_hash("%s#%s#%d" % (self._name, key, now))
        return (h & 0xFFFFFFFF) / float(0xFFFFFFFF)

    def request(self, key, now, ttl):
        entry = self._entries.get(key)
        if entry is not None:
            value, stored_at, expire_at = entry
            if now < stored_at:
                # A reply for this key is still in flight.
                if self._mutex:
                    self.waits += 1      # join the flight: no query, no ticks
                    return value
                # No mutex: the client cannot know a neighbour is already
                # fetching; it asks the origin itself. This is the stampede.
            elif now < expire_at:
                if self._window and now >= expire_at - self._window:
                    ramp = (now - (expire_at - self._window)) / float(self._window)
                    rc = self._recompute.get(key, 1)
                    if isinstance(rc, bool) or rc <= 0:
                        raise CacheError("recompute cost for '%s' is %r"
                                         % (key, rc))
                    price = min(1.0, FETCH_COST / rc)
                    if self._coin(key, now) < ramp * price:
                        self.early += 1          # expire early: rebuild below
                    else:
                        return value
                else:
                    return value
        cost = self._origin.cost(key)
        value = self._origin.fetch(key, self._clock)   # advances by cost
        self.queries_at[now] = self.queries_at.get(now, 0) + 1
        self._entries[key] = (value, now + cost, now + cost + ttl)
        return value

    def store_value(self, key, value, now, ttl):
        """A write-through placement for callers that already hold a fresh
        value — the capstone's `set` op. The reply lands on arrival: a
        synchronous write is not in flight."""
        self._entries[key] = (value, now, now + ttl)

    def peak(self, from_tick=0, to_tick=None):
        cols = [v for t, v in self.queries_at.items()
                if t >= from_tick and (to_tick is None or t <= to_tick)]
        return max(cols) if cols else 0


def cold_wave(cache, keys, clients, at_tick=0, ttl=50):
    """`clients` requests for every cold key at one tick — the stampede the
    mutex was written for (depth)."""
    for _ in range(clients):
        for k in keys:
            cache.request(k, at_tick, ttl)
    return cache


def frontend_wave(mutex, window, keys, frontends, rows, recompute,
                  ttl=50, sweep_to=None):
    """`frontends` *independent* caches, one origin: warm every key on every
    cache at tick 0, then every cache requests every key at every tick up to
    `sweep_to`. Entries land at tick 0 and die together at tick `ttl` — the
    width the per-cache mutex cannot thin, because each key's flight is
    alone in each cache. Returns (origin, aggregate per-tick columns)."""
    if sweep_to is None:
        sweep_to = ttl
    clock = Clock()
    origin = Origin(rows)
    caches = [SingleFlight(clock, origin, mutex=mutex, window=window,
                           recompute=recompute, name="fe-%02d" % i)
              for i in range(frontends)]
    for c in caches:
        for k in keys:
            c.request(k, 0, ttl)
    for t in range(1, sweep_to + 1):
        for c in caches:
            for k in keys:
                c.request(k, t, ttl)
    cols = {}
    for c in caches:
        for t, v in c.queries_at.items():
            cols[t] = cols.get(t, 0) + v
    return origin, cols


def line(label, origin, cache, from_tick=0, to_tick=None):
    return "%-14s origin %4d  busy %4d  waits %3d  early %3d  peak/tick %4d" % (
        label, origin.queries, cache._clock.now, cache.waits, cache.early,
        cache.peak(from_tick, to_tick))


if __name__ == "__main__":
    keys = ["k%d" % i for i in range(20)]
    cheap_re = {k: 2 for k in keys}               # herd eagerly: affordable
    cold_rows = {k: (k + "v", 30) for k in keys}   # depth hurts: slow rebuilds

    print("== cold wave (depth): 10 clients x 20 keys, one tick, 30-tick rebuilds ==")
    for label, mutex in (("none", False), ("mutex", True)):
        clock = Clock()
        origin = Origin(cold_rows)
        c = SingleFlight(clock, origin, mutex=mutex)
        cold_wave(c, keys, 10)
        print(line(label, origin, c))

    # The width lesson needs copies dying *together* in many caches;
    # zero-cost rows keep the clock still while warming, so every entry on
    # every frontend lands at tick 0 and dies at tick `ttl` together.
    expiry_rows = {k: (k + "v", 0) for k in keys}
    print("== expiry wave (width): 10 frontends x 20 keys, die at tick 50 ==")
    for label, mutex, window in (("none", False, 0), ("mutex", True, 0),
                                 ("herding", False, 10),
                                 ("mutex+herding", True, 10)):
        origin, cols = frontend_wave(mutex, window, keys, 10, expiry_rows,
                                     cheap_re)
        death = cols.get(50, 0)
        spread = max([v for t, v in cols.items() if t > 0] or [0])
        print("%-14s origin %4d  column@death %4d  peak other tick %4d"
              % (label, origin.queries, death, spread))
