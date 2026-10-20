"""Failover From Scratch — stage 2: Quorum: serve inside three or refuse entirely.

Three nodes per region is the smallest fleet where a majority is not
the whole: two of three can decide, and one cannot. A6's availability
law then prices the read/write pair — `r + w > n` — so a read set and a
write set must intersect, which is what makes a replica that ACKED a
write show up in every later stage's quorum. This stage turns those two
facts into the region's two yes/no gates, and adds the law the health
signal is built from in stage 5: a node counts toward a quorum only if
it is alive AND servable — `applied_count` within `LAG_BOUND` of the
best the region has seen. Presence is not servability.

DESIGN DECISION — the quorum predicate is `n * 2 > total`, never a
division or a percentage?
Because every number in this course is an int count and a comparison of
products keeps it one: `n >= total / 2 + 1` would introduce a float and
its rounding for no information. The law is stated on ints, so the
refusal can name the ints that broke it.

DESIGN DECISION — `ackable` refuses a duplicate id instead of counting
it twice?
Because a majority is a statement about DISTINCT nodes: two acks from
one node mean one node answered. `("e1", "e1")` is not a majority of
three, and quietly accepting it would let a caller certify a write on
evidence one machine produced. The refusal names the id.

DESIGN DECISION — why is `healthy_count` a count and not a set?
Because the only question a quorum asks is "is there a majority?" and a
count is that answer with no ordering to argue about. Stage 5's health
signal counts the same number against `majority()`; keeping the
arithmetic in one place means the two stages cannot disagree about what
"healthy" costs.
"""

import topology

import stage_01 as s1

FailError = s1.FailError


def _members(region):
    """The region's nodes, or the stage's own refusal naming the region.
    `topology` answers a plain ValueError; the protocol's refusals are
    `FailError`, so the gate re-raises with the region named."""
    try:
        return topology.nodes_of(region)
    except ValueError as problem:
        raise FailError(str(problem)) from None


def ackable(region, ack_ids):
    """True iff `ack_ids` are DISTINCT ids of `region` and reach its
    majority (`n * 2 > total`, ints). A malformed region or an id that
    does not live in it raises `FailError` naming the offender; a
    repeated id is refused too — one node cannot ack twice."""
    members = _members(region)
    ids = tuple(ack_ids)
    seen = set()
    for node in ids:
        if node not in members:
            raise FailError(
                "ackable: %r is not in %s (%s)"
                % (node, region, ", ".join(members)))
        if node in seen:
            raise FailError(
                "ackable: %r acked twice — a majority counts distinct "
                "nodes, not messages" % (node,))
        seen.add(node)
    return len(ids) * 2 > len(members)


def readable(region, live_ids):
    """A read quorum over the live set: `ackable` on the ids the region
    can actually answer from."""
    return ackable(region, live_ids)


def writable(region, live_ids):
    """A write quorum over the live set — the same gate, because this
    fleet reads and writes the same three nodes."""
    return ackable(region, live_ids)


def r_w_law(n, r, w):
    """A6's availability law: True iff `r + w > n` on ints. A pair that
    cannot intersect answers False; a non-int or an empty fleet is a
    caller's mistake and raises `FailError` naming the field."""
    for name, value in (("n", n), ("r", r), ("w", w)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise FailError("r_w_law: %s must be an int, got %r"
                            % (name, value))
    if n < 1:
        raise FailError("r_w_law: n=%d is below 1 — a quorum needs a node"
                        % (n,))
    return r + w > n


def _check_observation(row):
    """One observation must be `(node, applied_count, alive)` — the
    fabric's watch shape. Anything else is a caller's mistake."""
    if (not isinstance(row, tuple) or len(row) != 3
            or not isinstance(row[0], str)
            or not isinstance(row[1], int) or isinstance(row[1], bool)
            or not isinstance(row[2], bool)):
        raise FailError(
            "healthy_count: an observation must be (node, applied_count, "
            "alive), got %r" % (row,))
    if row[1] < 0:
        raise FailError("healthy_count: %s observed applied_count=%d, "
                        "below 0" % (row[0], row[1]))
    return row


def healthy_count(observed):
    """How many observed nodes may count toward their region's quorum:
    alive AND within `LAG_BOUND` of the best alive applied_count. The
    dead never count, a lagger never counts, and an empty observation
    counts zero — nobody is home."""
    rows = tuple(observed)
    for row in rows:
        _check_observation(row)
    counts = [row[1] for row in rows if row[2]]
    if not counts:
        return 0
    best = max(counts)
    return sum(1 for node, applied, alive in rows
               if alive and best - applied <= topology.LAG_BOUND)
