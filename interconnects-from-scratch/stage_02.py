"""Interconnects From Scratch — stage 2: Broadcast, ring and tree

Below this stage is stage 1's cost model and the provided `fabric.py`. A
broadcast is the first collective: one rank holds a buffer, and by the end every
rank holds it. This stage builds the two canonical plans for that — the ring,
whose informed edge creeps one rank per step, and the tree, whose informed set
doubles per step — and it leaves their price to `stage_01.plan_ticks`. A plan is
data; what it costs is counted, and what it does is run. The two are
independent: the ring and the tree answer the same buffers and cost very
different numbers of ticks, and that gap is the rest of the course.

DESIGN DECISION — why does the ring broadcast run one way round, instead of
having every informed rank send to both of its neighbours?
    A bidirectional ring looks natural and is worse. Both fronts carry the same
    buffer, so on a ring of four the counter-clockwise step reaches a rank that
    the clockwise front already reached, and the transfer moves bytes that are
    already known. It also puts two transfers on the ring per step, and where
    the two fronts meet the second one writes a rank a value it already holds.
    One direction is the minimal ring plan: `N-1` transfers, one per step, each
    a single hop carrying the root's whole buffer.

DESIGN DECISION — why does the tree broadcast put a whole level's sends in one
step, instead of having each node send to its children in turn?
    A walk — every informed rank sends to its children one after another — turns
    a level of `k` sends into `k` steps, so a binary tree of `N` ranks takes
    `N-1` steps: the same count as the ring, and no reason for the tree to
    exist. Putting a level's sends in one step is free here, because siblings
    share no directed link, so the fabric carries them at once and the step
    costs its most expensive send rather than the sum. That is the same maximum
    a step has been since stage 1.

DESIGN DECISION — why does the doubling follow the topology's own routes,
instead of a fixed binomial order over the rank ids?
    A binomial broadcast is usually written over the rank ids: at step `d`,
    rank `i` sends to rank `i + 2**d`. That assumes the ranks are wired as a
    hypercube and that `N` is a power of two; on `fabric.tree(n)` the rank
    `i + 1` is a parent, not a sibling, and the plan would name routes the
    fabric does not have. Asking the topology for its breadth-first tree from
    the root keeps the plan legal on every fixture and makes the tree's own
    levels the steps: the children of a node all send in the step after the
    node received.

DESIGN DECISION — why refuse a topology the doubling cannot cover, instead of
returning the plan for the component the root reaches?
    If a rank has no route from the root, the tempting answer is to broadcast to
    the reachable component and return that plan. The plan would be *legal* —
    every transfer it names is routable — and it would still be wrong: the ranks
    it never reaches keep their own buffers, so `fabric.run` would report a
    broadcast that informed fewer than every rank. A plan that silently covers
    part of the fabric is the failure this course exists to make visible, so the
    unreachable rank is a `fabric.FabricError` naming it, not a short plan.

DESIGN DECISION — why is a broadcast priced by `stage_01.plan_ticks` and not by
a `broadcast_cost` helper of its own?
    A `broadcast_cost(topology, root, length)` that recomputed the ticks from
    the shape of the broadcast would be a second cost model: it would re-derive
    the per-hop latency, the byte time and the ceiling, and it could disagree
    with the one stage 1 already proves. A broadcast is a plan; a plan's price is
    fixed by the plan and the topology alone, which is exactly what
    `plan_ticks` computes. The checks compare the ring and the tree by that one
    number, so the two broadcasts must answer plans the same model prices.

The two functions share one shape: refuse the malformed request, build the
transfers, and hand them to `fabric.Plan`. The root is a rank id, not an index,
because a topology's ranks need not be `r0..r{n-1}` in every later stage.

TODO: implement `broadcast_ring` and `broadcast_tree`.
"""


def broadcast_ring(topology, root, length):
    """The ring broadcast: the root's successor forwards to its successor, on.

    Every rank is visited once, in the topology's rank order, so the plan is
    `N-1` steps of one transfer each, every transfer a slice of the root's whole
    buffer: the rank after the root learns in step 0, and the last rank learns in
    step `N-2`. The root forwards its own buffer; every other sender forwards
    what it received, which is the same slice.

    Raises `fabric.FabricError` for a `root` that is not a rank of the topology
    and for a `length` below one.
    """
    raise NotImplementedError("stage 2: implement broadcast_ring()")


def broadcast_tree(topology, root, length):
    """The doubling broadcast: every informed rank forwards to its children.

    The plan is the topology's own breadth-first tree from `root`: a rank learns
    in the step of its depth, one step per level, and every rank of a level
    sends in the same step. On `fabric.tree(n)` the levels are the tree's own,
    so the step count is the height; on a fabric whose root has several children
    the children of the root share step 0.

    Raises `fabric.FabricError` for a `root` that is not a rank of the topology,
    for a `length` below one, and for a topology the doubling cannot cover — a
    rank with no route from the root.
    """
    raise NotImplementedError("stage 2: implement broadcast_tree()")
