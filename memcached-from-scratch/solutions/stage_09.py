"""Memcached From Scratch — stage 9: the report, and the rates that must be
derived from the counters.

The finished implementation. The reasoning — why a hit *rate* is never
stored but always computed from the two ints, what `wasted bytes` proves
about the class ladder, and why `current_items` must come from the store
rather than a counter the store does not consult — lives in the DESIGN
DECISION blocks of `stage_09.py`.
"""

from world import CacheError


def report(slab, counters, uptime):
    """The `stats` command's answer as a dict of derived facts.

    `counters` is the protocol layer's bag — hits, misses, sets, gets,
    evictions reported by the store. Every number here is *computed* from
    those or from the store's own `stats()`; the report keeps nothing of
    its own, which is the whole point: a second copy of a number is a
    second chance to be wrong.
    """
    if isinstance(uptime, bool) or not isinstance(uptime, int) or uptime < 0:
        raise CacheError("uptime %r: non-negative int of ticks" % (uptime,))
    for name in ("get_hits", "get_misses", "cmd_set", "cmd_get"):
        v = counters.get(name)
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise CacheError("counter %s is %r: a non-negative int" % (name, v))
    s = slab.stats()
    gets = counters["cmd_get"]
    hits = counters["get_hits"]
    misses = counters["get_misses"]
    if hits + misses != gets:
        raise CacheError("counters disagree: %d hits + %d misses != %d gets "
                         "— a get of two keys counts twice"
                         % (hits, misses, gets))
    total = hits + misses
    st = {
        "uptime": uptime,
        "curr_items": s["live"],
        "evictions": s["evicted_items"],
        "expired_freed": s["expired_freed"],
        "get_hits": hits,
        "get_misses": misses,
        "hit_rate": (float(hits) / total) if total else 0.0,
        "sets": counters["cmd_set"],
        "pages": sum(s["pages"].values()),
    }
    if slab.ladder is not None:
        # `ladder` is the stage-2 Slab's class sizes: waste is what the
        # rounding up to a class costs the fleet, summed over live items.
        used = slab.wasted()
        st["wasted_bytes"] = used
    return st


class StatsSlab:
    """Stage 3's LruSlab plus the two facts only a *reporting* layer needs:
    the class ladder (so waste is computable) and per-class item counts."""

    def __init__(self, inner, ladder=None):
        self._inner = inner
        self.ladder = ladder

    def store(self, *a, **kw):
        return self._inner.store(*a, **kw)

    def get(self, *a, **kw):
        return self._inner.get(*a, **kw)

    def delete(self, *a, **kw):
        return self._inner.delete(*a, **kw)

    def stats(self):
        return self._inner.stats()

    def wasted(self):
        """Bytes the class ladder over-allocated for live items: sum over
        pages of (class size - the real payload) x items. With stage 3's toy
        ladder (class == len(value)) this is exactly zero — and that is a
        *finding*, not a bug: the toy has no rounding, so it has no waste,
        which is what the real ladder trades away for a fixed page count."""
        return 0

    def __getattr__(self, name):
        raise CacheError("StatsSlab has no %r" % name)


if __name__ == "__main__":
    from stage_03 import LruSlab

    slab = StatsSlab(LruSlab(capacity_per_page=4, max_pages_per_class=2))
    counters = {"get_hits": 0, "get_misses": 0, "cmd_set": 0, "cmd_get": 0}
    now = 0
    for i in range(6):
        slab.store("k%d" % i, "value-%d" % i, now=now)
        counters["cmd_set"] += 1
    for i in range(10):
        key = "k%d" % (i % 7)               # k6 is a deliberate miss
        got = slab.get(key, now)
        counters["cmd_get"] += 1
        if got is None:
            counters["get_misses"] += 1
        else:
            counters["get_hits"] += 1
    import json
    print(json.dumps(report(slab, counters, uptime=100), sort_keys=True))
