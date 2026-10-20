"""Failover From Scratch — stage 1: The clock: ordering the versions, not the values.

A version is a value plus the clock that caused it: a sorted tuple of
`(node, counter)` pairs, every counter one write that node owes. Two
versions of a key are ordered ONLY by that clock, never by what a node
stamped last: `before`, `after`, `equal` or `concurrent` — and
`concurrent` is not a tie to break, it is two writes that both
survived. This stage owns the four-way law derived from the world's
single primitive `kv.dominates`, the survivor set every later stage
reads, and the pair table that carries the check's evidence.

DESIGN DECISION — equal is its own answer?
Because `dominates` holds BOTH ways for equal clocks, and a one-way
derivation would call a clock concurrent with itself: a version never
competes with its own causal history. `equal` is checked before any
single-direction verdict, so the naive derivation cannot be smuggled
back in.

DESIGN DECISION — survivors are the maximal set, not the newest one?
Because a concurrent sibling is a real write some client was acked.
`coalesce` drops every version another STRICTLY dominates and keeps
the rest even when two are incomparable — four versions, two siblings.
Narrowing to one is the lost update stage 9 prices, so this stage
never offers the shortcut.

DESIGN DECISION — why does `coalesce` also absorb exact duplicates?
Because the fabric re-delivers a hint and a caller may hand the same
version twice: `("v", "x", c)` twice is one version, not two siblings,
and an answer set that repeats a value lies about how many writes
survived. The survivor order is the sorted clock, so input order never
matters — that is what makes the dedupe testable.

DESIGN DECISION — why does `dominance_table` refuse below two clocks
with `FailError` instead of answering an empty table?
Because zero clocks is an argument mistake, not a verdict: a caller
that passed one clock and got `()` cannot tell "nothing to compare"
from "the stage forgot to compare". The refusal names the count.
"""

import kv


class FailError(ValueError):
    """The protocol's refusal: named, never guessed around."""


VERDICTS = ("before", "after", "equal", "concurrent")


def _clock_verdict(a, b):
    """The four-way law on RAW clocks, oriented so `a` speaks first."""
    ab = kv.dominates(a, b)
    ba = kv.dominates(b, a)
    if ab and ba:
        return "equal"
    if ab:
        return "after"
    if ba:
        return "before"
    return "concurrent"


def compare(a, b):
    """`("before"|"after"|"equal"|"concurrent",)` of version `a` against
    version `b`: `after` means `a` carries everything `b` does and more.
    A malformed version raises `kv.KvError` naming it."""
    return _clock_verdict(kv.clock_of(a), kv.clock_of(b))


def coalesce(versions):
    """The survivors: every version another version STRICTLY dominates
    is dropped, exact duplicates are absorbed, and the order left is the
    sorted clock — never the input order. `coalesce(())` is `()`."""
    items = tuple(versions)
    for v in items:
        kv.clock_of(v)
    ordered = sorted(set(items), key=lambda v: (v[2], v[1]))
    survivors = []
    for a in ordered:
        strictly_dominated = any(_clock_verdict(a[2], b[2]) == "before"
                                 for b in ordered if b is not a)
        if not strictly_dominated:
            survivors.append(a)
    return tuple(survivors)


def dominance_table(clocks):
    """Every unordered pair of the clocks, `(a, b, verdict)` rows sorted
    by the pair itself, `a <= b`. Below two clocks the table cannot
    exist and `FailError` names the count; a malformed clock raises
    `kv.KvError`."""
    items = tuple(clocks)
    if len(items) < 2:
        raise FailError("dominance_table: %d clocks cannot make a pair"
                        % (len(items),))
    for clock in items:
        kv.dominates(clock, clock)
    ordered = sorted(items)
    rows = []
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            a, b = ordered[i], ordered[j]
            rows.append((a, b, _clock_verdict(a, b)))
    return tuple(rows)
