"""Interconnects From Scratch — stage 10: One step, end to end (implementation).

The reasoning behind the step lives in the template's docstring (`stage_10.py`);
this file is only the body. Nothing here is measured: every axis's collective is
a plan built by an earlier stage, the step's price is a maximum over the axes of
`stage_01.plan_ticks`, and every number is an `int`.

The one idea: a step is four collectives at once over four partitions of the
same ranks. The gradients all-reduce over the data-parallel group (once, when
the accumulation window closes), the tensor-parallel pair all-reduces over the
tensor group, the pipeline hands its activations across the block boundaries,
and the experts exchange tokens out and back. Each axis's plan is the plan of
its first group: every group of an axis runs the same collective on the same
shape of fabric, so one plan prices the axis. A step's communication is the
slowest of the four, because the four partitions are disjoint sets of ranks and
their collectives run at once; and the step itself is the slower of the step's
compute and that communication, because compute and the network are overlapped.
"""

import fabric

import stage_01
import stage_07
import stage_08
import stage_09

#: The step's four axes, in the order a step's communication is laid out.
_AXES = ("grads", "params", "activations", "experts")


def _is_count(value):
    """Whether `value` is a whole count. A `bool` is an `int`, and not one."""
    return isinstance(value, int) and not isinstance(value, bool)


def _empty():
    """The plan of an axis with nothing to move: no transfers, no steps."""
    return fabric.Plan(transfers=())


def _check_shape(topology, dp, tp, pp, moe, length):
    """The world's rank count for this shape, or a refusal naming the offender.

    The axes are laid out over every rank id of the topology, so the shape has
    to be the fabric's size: `dp * tp * pp * moe` ranks, with an expert axis of
    zero (a dense step with no experts at all) counting as one for the layout.
    """
    for name, value in (("dp", dp), ("tp", tp), ("pp", pp)):
        if not _is_count(value) or value < 1:
            raise fabric.FabricError(
                "%s is %r: a parallel axis is one rank or more, never fewer"
                % (name, value))
    if not _is_count(moe) or moe < 0:
        raise fabric.FabricError(
            "moe is %r: an expert axis is zero (a dense step, no experts) or "
            "more, never fewer" % (moe,))
    if not _is_count(length) or length <= 0:
        raise fabric.FabricError(
            "length is %r: a step moves a positive whole count of elements"
            % (length,))
    width = max(moe, 1)
    world = len(topology.ranks)
    shape = dp * tp * pp * width
    if shape != world:
        raise fabric.FabricError(
            "the shape dp=%d, tp=%d, pp=%d, moe=%d is %d ranks, one per rank id, "
            "but %s has %d" % (dp, tp, pp, moe, shape, topology, world))
    return width


def _index(dp, tp, width, dp_i, tp_i, pp_i, moe_i):
    """The rank index of one coordinate, in the frozen layout.

    The axes nest `pp` (outermost), then `dp`, then `moe`, then `tp`
    (innermost): `index = ((pp_i * dp + dp_i) * width + moe_i) * tp + tp_i`.
    """
    return ((pp_i * dp + dp_i) * width + moe_i) * tp + tp_i


def _dp_group(dp, tp, width):
    """The data-parallel group's rank indices: `dp` ranks, one per replica."""
    return tuple(_index(dp, tp, width, dp_i, 0, 0, 0) for dp_i in range(dp))


def _tp_group(dp, tp, width):
    """The tensor group's rank indices: `tp` consecutive ranks."""
    return tuple(_index(dp, tp, width, 0, tp_i, 0, 0) for tp_i in range(tp))


def _moe_group(dp, tp, width, moe):
    """The expert group's rank indices: `moe` ranks, one per expert shard."""
    return tuple(_index(dp, tp, width, 0, 0, 0, moe_i) for moe_i in range(moe))


def _require_connected(group, axis, topology):
    """Refuse a group whose own links cannot reach every other member."""
    reached = [group.ranks[0]]
    seen = {group.ranks[0]}
    while reached:
        rank = reached.pop(0)
        for neighbour in group.neighbours(rank):
            if neighbour not in seen:
                seen.add(neighbour)
                reached.append(neighbour)
    for rank in group.ranks:
        if rank not in seen:
            raise fabric.FabricError(
                "the %s axis of %s puts %s and %s in one group, and %s has no "
                "route between them: a group is a fabric the collective can run "
                "inside" % (axis, topology, group.ranks[0], rank, group))


def _group_fabric(topology, indices, axis):
    """The sub-fabric one group of one axis runs on.

    The group's ranks are exactly the ones the frozen layout gave it, and its
    links are the fabric's own links between those ranks — the group sees the
    links it owns, not the ones it would have to borrow from another axis.
    """
    if len(indices) < 2:
        raise fabric.FabricError(
            "the %s axis names %d rank(s), and a collective needs at least two"
            % (axis, len(indices)))
    members = tuple(topology.ranks[index] for index in indices)
    links = tuple(link for link in topology.links
                  if link.a in members and link.b in members)
    group = fabric.Topology(ranks=members, links=links,
                            name="%s group of %s" % (axis, topology))
    _require_connected(group, axis, topology)
    return group


def _after(plan, addition):
    """`plan`, then `addition` in the steps after `plan`'s own."""
    if not plan.transfers:
        return addition
    if not addition.transfers:
        return plan
    offset = plan.steps()[-1] + 1
    shifted = tuple(fabric.send(transfer.src, transfer.dst, transfer.length,
                                transfer.step + offset, offset=transfer.offset,
                                op=transfer.op)
                    for transfer in addition.transfers)
    return fabric.Plan(transfers=plan.transfers + shifted)


def _all_reduce(group, length):
    """The cheapest all-reduce of `stage_09.choose`, on the group's fabric."""
    return stage_09.choose(group, length, op="sum")[1]


def _splits(moe, length):
    """The expert exchange's table: `length // moe` to every peer, the rest kept.

    Every rank dispatches its whole `length`-element buffer — an equal `per` to
    each of the other `moe - 1` shards, and what a whole split leaves over stays
    with the rank that owns it — so the running offsets stay inside the buffer.
    """
    per = length // moe
    if per < 1:
        raise fabric.FabricError(
            "length is %r and the expert group is %d ranks: there is not one "
            "element per shard to dispatch" % (length, moe))
    keep = length - per * (moe - 1)
    return tuple(tuple(keep if i == j else per for j in range(moe))
                 for i in range(moe))


def _transpose(splits):
    """The same table the other way round: what came back, goes back."""
    return tuple(tuple(row) for row in zip(*splits))


def _experts(group, moe, length):
    """The two exchanges: dispatch out, then combine back (a later step)."""
    table = _splits(moe, length)
    dispatch = stage_07.all_to_all(group, table)
    return _after(dispatch, stage_07.all_to_all(group, _transpose(table)))


def step_plan(topology, *, dp, tp, pp, moe, length):
    """The four collectives one training step of this shape needs, as plans.

    The keys are fixed and always present: `"grads"` (a data-parallel
    all-reduce over the `dp` group, once per step), `"params"` (the
    tensor-parallel pair of all-reduces over the `tp` group), `"activations"`
    (the pipeline's sends across the `pp - 1` stage boundaries, one launch) and
    `"experts"` (the dispatch and the combine of the `moe` expert shards, two
    exchanges). An axis of one rank has no collective and gets the empty plan;
    so does an expert axis of zero, which is a dense step.
    """
    width = _check_shape(topology, dp, tp, pp, moe, length)
    bound = dp * width * tp
    step = {}
    if dp > 1:
        group = _group_fabric(topology, _dp_group(dp, tp, width), "dp")
        step["grads"] = _all_reduce(group, length)
    else:
        step["grads"] = _empty()
    if tp > 1:
        group = _group_fabric(topology, _tp_group(dp, tp, width), "tp")
        step["params"] = _after(_all_reduce(group, length),
                                _all_reduce(group, length))
    else:
        step["params"] = _empty()
    activations = []
    for stage in range(pp - 1):
        tail = (stage + 1) * bound - 1
        activations.append((topology.ranks[tail], topology.ranks[tail + 1],
                            0, length))
    step["activations"] = stage_08.sendrecv(topology, tuple(activations))
    if moe > 1:
        group = _group_fabric(topology, _moe_group(dp, tp, width, moe), "moe")
        step["experts"] = _experts(group, moe, length)
    else:
        step["experts"] = _empty()
    return step


def step_ticks(topology, plan):
    """What the step's communication costs: the slowest of its four axes.

    The four axis groups are disjoint sets of ranks, so their collectives run at
    once and the step's communication is as slow as the slowest of them: the
    largest of the axes' `stage_01.plan_ticks`, and zero for a step whose four
    plans are all empty.
    """
    ticks = 0
    for axis in _AXES:
        if axis not in plan:
            raise fabric.FabricError(
                "the step plan has no %r axis, and a step's four axes are %r"
                % (axis, list(_AXES)))
        cost = stage_01.plan_ticks(topology, plan[axis])
        if cost > ticks:
            ticks = cost
    return ticks


def overlap(compute_ticks, comms_ticks):
    """The step's wall clock: the slower of its compute and its communication.

    Compute and the network proceed at once, so the step takes the larger of the
    two and never their sum. Both are whole tick counts.
    """
    for name, value in (("compute_ticks", compute_ticks), ("comms_ticks", comms_ticks)):
        if not _is_count(value):
            raise fabric.FabricError(
                "%s is %r, not a whole count of ticks" % (name, value))
        if value < 0:
            raise fabric.FabricError(
                "%s is %r: a step takes no negative time" % (name, value))
    return max(compute_ticks, comms_ticks)
