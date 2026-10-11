"""Interconnects From Scratch — stage 5: All-reduce, tree and doubling (implementation).

The reasoning behind the two shapes lives in the template's docstring
(`stage_05.py`); this file is only the body. Nothing here is measured: a plan is
built as data, the price of a plan is `stage_01.plan_ticks`, and every number is
an `int`.

The one idea: an all-reduce can go *up the topology's own tree* — reduce from the
leaves to the root, then broadcast the sum back down, `2 * levels` steps — or by
*recursive doubling* — `log2(N)` steps, each rank exchanging the whole buffer
with the rank `r XOR 2**k` in step `k`. The tree is latency-cheap and
bandwidth-dear (every level moves the payload again); doubling is flat but needs
`N` a power of two and every XOR partner a direct neighbour. `all_reduce_best`
is the arithmetic: it builds every shape whose preconditions hold and keeps the
one `stage_01.plan_ticks` says is cheapest.
"""

import fabric
import stage_01
import stage_04

#: The algorithms `all_reduce_best` may pick, in the order ties are broken.
_ALGORITHMS = ("ring", "tree", "doubling")


def _check_op(op):
    """Refuse an `op` that is neither a combining op nor the label `"reduce"`.

    A plan does not carry the combining operation — `fabric.run` applies it —
    so `op` selects nothing here; it is checked and named, exactly as in
    `stage_04.all_reduce_ring`.
    """
    if op not in fabric.OPS and op != "reduce":
        raise fabric.FabricError(
            "op %r is not one of the combining ops %r, nor 'reduce'"
            % (op, fabric.OPS))


def _tree_of(topology, root):
    """The topology's own tree as `(parent, level)`, rooted at `root`.

    `parent[rank]` is the first hop of `topology.path(rank, root)` — the
    neighbour one hop closer to the root — and `None` for the root itself;
    `level[rank]` is the hop distance to the root. The two together name the
    reduce tree: every rank hangs off the neighbour the fabric's own routing
    already chose, so the tree is a property of the topology and not of a rank
    numbering imposed on it.
    """
    parent = {}
    level = {}
    for rank in topology.ranks:
        route = topology.path(rank, root)
        if route is None:
            raise fabric.FabricError(
                "rank %r has no route to the root %r: a tree all-reduce needs "
                "a connected fabric" % (rank, root))
        level[rank] = len(route) - 1
        parent[rank] = route[1] if len(route) > 1 else None
    return parent, level


def all_reduce_tree(topology, length, *, op="reduce"):
    """Reduce to the root up the topology's own tree, then broadcast back down.

    The root is `topology.ranks[0]`. In the first `levels` steps the rank
    `levels - step` hops from the root combines its whole buffer into its
    parent (`op="reduce"`), so a rank sends only after its children have sent
    into it; after step `levels - 1` the root holds the sum. In the next
    `levels` steps the rank `step` hops from the root copies its whole buffer to
    each of its children (`op="send"`), so every rank ends holding the sum. The
    plan is `2 * levels` steps, where `levels` is the largest hop distance from
    any rank to the root: 4 steps on `tree(7)`, and `2 * log2(N)` on a balanced
    tree.
    """
    _check_op(op)
    root = topology.ranks[0]
    parent, level = _tree_of(topology, root)
    levels = max(level.values())
    transfers = []
    for step in range(levels):
        for rank in topology.ranks:
            if level[rank] == levels - step and parent[rank] is not None:
                transfers.append(fabric.send(rank, parent[rank], length, step,
                                             op="reduce"))
    for step in range(levels):
        for rank in topology.ranks:
            if level[rank] != step:
                continue
            for child in topology.ranks:
                if parent[child] == rank:
                    transfers.append(fabric.send(rank, child, length, levels + step))
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_reduce_tree (root=%s, levels=%d, op=%s)" % (root, levels, op))


def all_reduce_doubling(topology, length, *, op="reduce"):
    """Recursive doubling: `log2(N)` steps, each rank reducing with `r XOR 2**k`.

    Step `k` joins every rank with the rank `r XOR 2**k`; both ends send their
    whole buffer with `op="reduce"`, since both hold a partial sum. After
    `log2(N)` steps each rank has exchanged with every bit pattern and holds the
    sum of all `N` buffers. It needs `N` a power of two: the XOR partner of a
    rank must be a rank, and the `k` partners must be distinct for `k = 0 ..
    log2(N) - 1`. An `N` that is not a power of two is refused, naming `N`.

    It also needs every XOR partner to be a *direct neighbour*. A butterfly step
    is one exchange, one step; a partner several hops away has to share a
    directed link with another pair's route inside that step, so no link-legal
    one-step plan exists. A topology where that happens (`ring(8)`: rank `r0`
    and rank `r2` are two hops apart) is refused, naming the offending pair and
    its hop count.
    """
    _check_op(op)
    ranks = topology.ranks
    total = len(ranks)
    steps = 0
    while (1 << steps) < total:
        steps += 1
    if (1 << steps) != total:
        raise fabric.FabricError(
            "N is %d, not a power of two: recursive doubling needs one exchange "
            "per bit of the rank id, so N = 2**k" % (total,))
    transfers = []
    for step in range(steps):
        span = 1 << step
        for index, rank in enumerate(ranks):
            partner = ranks[index ^ span]
            hops = topology.distance(rank, partner)
            if hops != 1:
                raise fabric.FabricError(
                    "recursive doubling needs every XOR partner to be a direct "
                    "neighbour, but rank %s and rank %s are %r hops apart: a "
                    "butterfly step over them is not one legal exchange"
                    % (rank, partner, hops))
            transfers.append(fabric.send(rank, partner, length,
                                         step, op="reduce"))
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_reduce_doubling (N=%d, steps=%d, op=%s)" % (total, steps, op))


def _build(algorithm, topology, length, op):
    """Build the named algorithm's plan, or let its own refusal out."""
    if algorithm == "ring":
        return stage_04.all_reduce_ring(topology, length, op=op)
    if algorithm == "tree":
        return all_reduce_tree(topology, length, op=op)
    return all_reduce_doubling(topology, length, op=op)


def all_reduce_best(topology, length, *, op="reduce"):
    """The cheapest of `("ring", "tree", "doubling")`, and its plan.

    Every algorithm is built and priced with `stage_01.plan_ticks`; the smallest
    total wins, ties broken by the order `("ring", "tree", "doubling")`. A
    candidate whose own preconditions fail — doubling without a power-of-two
    `N`, a ring whose chunking does not divide `length` — is *not* an error
    here: it simply is not a candidate. The winner is a function of the two (or
    three) tick counts, not of the topology's name or of a hard-coded length.
    """
    _check_op(op)
    best = None
    for algorithm in _ALGORITHMS:
        try:
            plan = _build(algorithm, topology, length, op=op)
        except fabric.FabricError:
            continue
        ticks = stage_01.plan_ticks(topology, plan)
        if best is None or ticks < best[0]:
            best = (ticks, algorithm, plan)
    if best is None:
        raise fabric.FabricError(
            "no all-reduce fits %s: the ring needs a dividend chunking, "
            "doubling a power-of-two N, and the tree a route to the root"
            % (topology,))
    return best[1], best[2]
