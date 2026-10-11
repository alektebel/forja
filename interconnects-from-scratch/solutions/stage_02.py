"""Interconnects From Scratch — stage 2: Broadcast, ring and tree (implementation).

The reasoning behind the two broadcasts lives in the template's docstring
(`stage_02.py`); this file is only the body. Both functions answer a
`fabric.Plan`: the plan that rings the root's buffer once per step, and the plan
that doubles the set of informed ranks one level at a time. What a plan costs is
`stage_01.plan_ticks`; what it does is `fabric.run`.
"""

import fabric


def _require(topology, root, length):
    """Refuse the two arguments every broadcast shares.

    A root that is not a rank of the topology cannot start a broadcast, and a
    buffer with no elements has nothing to broadcast. Both are malformed
    requests, so both are `fabric.FabricError`.
    """
    if root not in topology.ranks:
        raise fabric.FabricError(
            "root %r is not a rank of %s; the ranks are %r"
            % (root, topology, topology.ranks))
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise fabric.FabricError(
            "length %r is not a positive number of elements" % (length,))


def broadcast_ring(topology, root, length):
    """The ring broadcast: the root's successor forwards to its successor, on.

    Every rank is visited once, in the topology's rank order, so the plan is
    `N-1` steps of one transfer each, every transfer a slice of the root's whole
    buffer. The root is the first rank of the order, the rank after it learns in
    step 0, and the last rank learns in step `N-2`.
    """
    _require(topology, root, length)
    order = tuple(topology.ranks)
    start = order.index(root)
    transfers = []
    for step in range(1, len(order)):
        src = order[(start + step - 1) % len(order)]
        dst = order[(start + step) % len(order)]
        transfers.append(fabric.send(src, dst, length, step - 1))
    return fabric.Plan(transfers=tuple(transfers),
                       name="broadcast_ring(%s, %s)" % (topology, root))


def _informed_order(topology, root):
    """The breadth-first order from `root`: `{rank: depth}` and `{rank: parent}`.

    The walk visits neighbours in rank order, so the parent of a rank is the
    same predecessor `fabric.Topology.path` uses, and the route from a parent to
    a child is exactly one hop.
    """
    depth = {root: 0}
    parent = {root: None}
    layer = [root]
    while layer:
        following = []
        for rank in sorted(layer):
            for neighbour in topology.neighbours(rank):
                if neighbour in depth:
                    continue
                depth[neighbour] = depth[rank] + 1
                parent[neighbour] = rank
                following.append(neighbour)
        layer = following
    return depth, parent


def broadcast_tree(topology, root, length):
    """The doubling broadcast: every informed rank forwards to its children.

    The plan is the topology's own breadth-first tree from `root`: a rank learns
    in the step of its depth, one step per level, and every rank of a level
    sends in the same step. On `fabric.tree(n)` the levels are the tree's own,
    so the step count is the height; on a fabric whose root has several children
    the children of the root share step 0.
    """
    _require(topology, root, length)
    depth, parent = _informed_order(topology, root)
    unreached = [rank for rank in topology.ranks if rank not in depth]
    if unreached:
        raise fabric.FabricError(
            "root %r cannot reach %r on %s, so the doubling cannot cover every "
            "rank" % (root, unreached[0], topology))
    transfers = []
    for rank in topology.ranks:
        if rank == root:
            continue
        transfers.append(
            fabric.send(parent[rank], rank, length, depth[rank] - 1))
    return fabric.Plan(transfers=tuple(transfers),
                       name="broadcast_tree(%s, %s)" % (topology, root))
