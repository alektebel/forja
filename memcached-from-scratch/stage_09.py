"""Memcached From Scratch — stage 9: the report, and the rates that must be
derived from the counters.

`stats` is the only thing an operator has of the daemon. This stage builds
that report as a pure function of two sources — the protocol's counters and
the store's own stats() — and refuses to let either of them be copied.

DESIGN DECISION — why is `hit_rate` computed and never stored?
    The tempting alternative is keeping a running rate updated on every
    miss. Its cost is two truths that drift: the stored rate is the rate at
    some past moment, and any code that touches the counters without
    touching the rate corrupts it silently. A rate is a FUNCTION of two
    ints; keeping both and deriving it at report time means there is
    exactly one place the division happens, and it is always current.

DESIGN DECISION — why is `hits + misses == cmd_get` enforced, not assumed?
    The tempting alternative is computing the rate from whatever the
    counters say. Its cost is a report that looks fine while the counters
    disagree — the daemon's own identity holds because a `get a b` counts
    TWO keys against cmd_get's ONE command, and any accounting bug that
    breaks the identity also breaks every rate. The refusal names the
    numbers and why they can differ: a multi-key get counts twice.

DESIGN DECISION — why does `evictions` come from the STORE, not a counter?
    The tempting alternative is counting evictions where they are noticed.
    Its cost is the number that is off by exactly the events nobody
    noticed: the whole-page recycle kills several items in one move. The
    store keeps the ledger (stage 3's `evicted_items`) and the report reads
    it, so the daemon cannot disagree with its own allocator.

DESIGN DECISION — why is `wasted_bytes` reported ONLY when the class ladder
is known?
    The tempting alternative is reporting 0 always — "no waste". Its cost
    is a false negative that matters for capacity planning: waste is what
    rounding a 100-byte value to a 128-byte class costs the fleet, summed
    over live items. With no ladder the number is not zero, it is
    UNKNOWN, and the honest report omits the field. With stage 3's toy
    ladder (class == len(value)) the answer is genuinely 0 — a finding,
    not a default.

DESIGN DECISION — why does `StatsSlab.__getattr__` REFUSE instead of
forwarding?
    The tempting alternative is forwarding every unknown attribute to the
    inner store. Its cost is the reporting layer quietly growing the
    store's surface: `slab.uptime` answering an int the store never kept
    is how a stat becomes true by accident. The wrapper owns exactly its
    own names and refuses the rest, so a missing fact is an error, not a
    guess.

TODO: implement `report` and `StatsSlab.__init__`, `store`, `get`,
`delete`, `stats`, `wasted`, `__getattr__`.
"""


def report(slab, counters, uptime):
    """The `stats` command's answer as a dict of derived facts.

    `counters` is the protocol layer's bag — `get_hits`, `get_misses`,
    `cmd_set`, `cmd_get`. Every number here is computed from those or from
    `slab.stats()`; the report keeps nothing of its own.

    Required keys: uptime, curr_items, evictions, expired_freed, get_hits,
    get_misses, hit_rate, sets, pages — and `wasted_bytes` only when
    `slab.ladder` is not None. Refusals: a non-int, bool, or negative
    `uptime` or counter (the message names which counter), and a counters
    bag where hits + misses != cmd_get."""
    raise NotImplementedError("stage 9: implement report()")


class StatsSlab:
    """Stage 3's LruSlab plus the two facts only a REPORTING layer needs:
    the class ladder (so waste is computable) and a refusal for every name
    it does not own. `ladder` is the stage-2 class sizes or None."""

    def __init__(self, inner, ladder=None):
        raise NotImplementedError("stage 9: implement StatsSlab.__init__()")

    def store(self, *a, **kw):
        raise NotImplementedError("stage 9: implement StatsSlab.store()")

    def get(self, *a, **kw):
        raise NotImplementedError("stage 9: implement StatsSlab.get()")

    def delete(self, *a, **kw):
        raise NotImplementedError("stage 9: implement StatsSlab.delete()")

    def stats(self):
        """The inner store's own stats dict — the report's source for
        live, evicted_items, expired_freed and the page counts."""
        raise NotImplementedError("stage 9: implement StatsSlab.stats()")

    def wasted(self):
        """Bytes the class ladder over-allocated for live items: sum over
        live items of (class size - payload). With the toy ladder this is
        exactly 0 — no rounding, so no waste."""
        raise NotImplementedError("stage 9: implement StatsSlab.wasted()")

    def __getattr__(self, name):
        """Refuse any name the wrapper does not define: a fact the wrapper
        does not keep is an error, not a forwarded guess."""
        raise NotImplementedError("stage 9: implement StatsSlab.__getattr__()")
