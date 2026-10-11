"""Interconnects From Scratch — stage 3: Reduce, and where the accumulator lives (implementation).

The reasoning behind the two plans lives in the template's docstring
(`stage_03.py`); this file is only the body. A plan is data — which rank sends
which slice to which rank, in which step, and whether that transfer combines
into the destination (`op="reduce"`) or copies over it (`op="send"`) — so this
file folds nothing: `fabric.run` folds, under the `op` the caller hands it, and
`fabric.reference` is the answer the checks compare against.
"""

import fabric


def _refuse(topology, root, length):
    """The three ways a reduce-to-root is not a plan at all.

    A `length` below one has no slice to move, a `root` that is not a rank has
    no buffer to land the accumulator on, and a rank with no route to the root
    can never join the chain. Each one left unchecked produces a plan that
    quietly reduces *fewer* ranks than the topology has — a wrong answer that
    looks like a right one.
    """
    if length < 1:
        raise fabric.FabricError(
            "length %r is not at least one element" % (length,))
    if root not in topology.ranks:
        raise fabric.FabricError(
            "root %r is not a rank of %s" % (root, topology))
    for rank in topology.ranks:
        if rank == root:
            continue
        if topology.path(rank, root) is None:
            raise fabric.FabricError(
                "rank %r has no route to root %r on %s" % (rank, root, topology))


def _ring_chain(topology, root):
    """The chain the accumulator walks: one `(src, dst)` per step, per hop.

    Step `k` moves the buffer held `k + 1` places before the root in the ring's
    order one more place back, so the accumulator passes through
    `root-1, root-2, …` and its last hop lands on the root. `fabric.ring` lists
    its ranks around the ring in order, so the rank tuple *is* the ring order
    and one step of index arithmetic around it is one hop of the ring.
    """
    ranks = list(topology.ranks)
    start = ranks.index(root)
    count = len(ranks)
    return [(ranks[(start - 1 - step) % count], ranks[(start - 2 - step) % count])
            for step in range(count - 1)]


def _tree(topology, root):
    """The breadth-first tree `root` hangs from, as `(parent, depth)` per rank.

    A rank's parent is a neighbour — the one it was reached through — so every
    hop of the tree plan is one hop, and two ranks at the same depth always send
    along different links: one step per level is legal by construction.
    """
    parent = {root: None}
    depth = {root: 0}
    layer = [root]
    while layer:
        following = []
        for rank in sorted(layer):
            for neighbour in topology.neighbours(rank):
                if neighbour not in parent:
                    parent[neighbour] = rank
                    depth[neighbour] = depth[rank] + 1
                    following.append(neighbour)
        layer = following
    return parent, depth


def reduce_ring(topology, root, length):
    """The ring reduce: every hop of the ring combines into the next buffer.

    `N-1` steps, each carrying one rank's buffer one place back around the
    ring's order, so the accumulator travels through the buffers of
    `root-1, root-2, …` — each of which ends up holding its own contribution
    plus everything the chain has collected — and its last hop lands the
    combination on the root. Every transfer combines (`op="reduce"`).
    """
    _refuse(topology, root, length)
    transfers = tuple(
        fabric.send(src, dst, length, step, op="reduce")
        for step, (src, dst) in enumerate(_ring_chain(topology, root)))
    return fabric.Plan(transfers=transfers,
                       name="reduce_ring(root=%s, length=%d)" % (root, length))


def reduce_tree(topology, root, length):
    """The tree reduce: level by level, deepest first, each rank into its parent.

    Every rank whose children have all sent sends its own buffer — which by
    then holds its subtree's contribution — to its parent with `op="reduce"`.
    The deepest level is placed first, so a parent's message never shares a step
    with the combines its children send it, and each level's sends are one hop
    each along their own links.
    """
    _refuse(topology, root, length)
    parent, depth = _tree(topology, root)
    leaves = max(depth[rank] for rank in topology.ranks)
    ranks = [rank for rank in topology.ranks if rank != root]
    order = sorted(ranks, key=lambda rank: (-depth[rank], rank))
    transfers = tuple(
        fabric.send(rank, parent[rank], length, leaves - depth[rank], op="reduce")
        for rank in order)
    return fabric.Plan(transfers=transfers,
                       name="reduce_tree(root=%s, length=%d)" % (root, length))
