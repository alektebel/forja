"""Failover From Scratch — stage 4: Anti-entropy: the union over ranges, never a choice.

A region that survived a cut must answer one question before it serves:
which of my ranges differ from yours? A6's answer is the Merkle tree:
a per-key fingerprint over the CLOCKS only, folded into a fixed
partition, and the repair is the UNION — stage 1's `coalesce` of both
sides' versions, never a pick and never a newest-wins shortcut. The
fingerprint law carries the whole lesson in one line: same siblings,
any order, same hash; a sibling against its reconciled version,
DIFFERENT hashes — the tree sees the conflict instead of smoothing it
over. And a value never enters a hash: two nodes that applied the same
writes in different orders must agree that they agree.

DESIGN DECISION — the partition is over sorted key POSITIONS, four
contiguous half-open ranges?
Because it must be recomputable from the key list alone, identically on
both sides: `lo = slot * n // 4` on ints, no hash function over keys,
no tuning. An empty range still gets a hash — a tree whose missing
range has no representation cannot tell "we both have nothing here"
from "we did not compare."

DESIGN DECISION — why do the hashes travel WITH their range?
Because `diff` gets two trees and must name WHAT to reconcile, not
just count mismatches. `tree_hashes` answers `((range, hex), ...)` and
`diff` answers the ranges whose pairs do not match exactly — including
a range one side does not carry at all. A flat tuple of hexes would
make diff a positional joke: different key sets split at different
positions, and "slot 2 differs" would not point anywhere.

DESIGN DECISION — why is `repair` exactly stage 1's coalesce of the
union, with no newest-wins?
Because newest-wins IS the lost update; stage 1's law is the whole
merge law, and this stage may not restate it weaker. The check pins
repair's result equal to `coalesce(a + b)` — if this stage ever grows
an opinion about which sibling to keep, that equality is its epitaph.
"""

import hashlib

import kv

import stage_01 as s1

FailError = s1.FailError

RANGE_COUNT = 4


def fingerprint(versions):
    """The sha256 hex over the SORTED clock reprs of `versions` — no
    value bytes. The same siblings in any order hash identically; a
    sibling set against its reconciled version DIFFERS, which is what
    makes the tree SEE the conflict. A malformed version raises
    `kv.KvError` naming it."""
    clocks = sorted(kv.clock_of(v) for v in tuple(versions))
    joined = "".join(repr(clock) for clock in clocks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def ranges(keys):
    """The four contiguous half-open ranges of `sorted(keys)` positions:
    slot i runs `[i * n // 4, (i + 1) * n // 4)`. Fixed, deterministic,
    recomputable from the key list alone; empty ranges appear as
    `(lo, lo)`. A key that is not a non-empty string is a caller's
    mistake and raises `FailError` naming it."""
    ordered = tuple(keys)
    for k in ordered:
        if not isinstance(k, str) or not k:
            raise FailError("ranges: a key must be a non-empty string, "
                            "got %r" % (k,))
    ordered = sorted(ordered)
    n = len(ordered)
    return tuple((i * n // RANGE_COUNT, (i + 1) * n // RANGE_COUNT)
                 for i in range(RANGE_COUNT))


def tree_hashes(store):
    """`((range, hex), ...)` — one fingerprint per range: the fold of
    the per-key fingerprints inside it (key-sorted), so an empty range
    still carries the empty fold. A malformed store raises `kv.KvError`
    or `FailError` naming the offender."""
    keys = sorted(store)
    parts = ranges(keys)
    out = []
    for lo, hi in parts:
        fold = "".join(fingerprint(tuple(store[k]))
                       for k in keys[lo:hi])
        out.append(((lo, hi),
                    hashlib.sha256(fold.encode("utf-8")).hexdigest()))
    return tuple(out)


def diff(h_a, h_b):
    """The ranges whose (range, hex) pairs do NOT match exactly between
    two trees — including a range one side does not carry at all. The
    answer is sorted by the range; an empty answer is `()`: the stores
    are reconciled and nothing needs to move."""
    a = tuple(h_a)
    b = tuple(h_b)
    for entry in a + b:
        if (not isinstance(entry, tuple) or len(entry) != 2
                or not isinstance(entry[0], tuple) or len(entry[0]) != 2):
            raise FailError("diff: a tree entry must be ((lo, hi), hex), "
                            "got %r" % (entry,))
    set_b = set(b)
    set_a = set(a)
    return tuple(sorted({e[0] for e in a if e not in set_b}
                        | {e[0] for e in b if e not in set_a}))


def repair(a_versions, b_versions):
    """The union reconciled: `coalesce(a + b)` — stage 1's maximal set,
    never a pick, never newest-wins. A version only one side holds
    survives; dominated siblings drop; concurrent siblings BOTH stay."""
    return s1.coalesce(tuple(a_versions) + tuple(b_versions))
