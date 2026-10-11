"""Distributed Training From Scratch — stage 1: The shapes and the ledger (implementation).

The reasoning behind the plan shapes and the two counters lives in the
template's docstring (`stage_01.py`); this file is only the body. Nothing here
is measured: a tick count is computed from a plan and the fabric's own costs,
every number is an `int`, and two calls return equal values.
"""

from dataclasses import dataclass

import fabric
import model


@dataclass(frozen=True)
class Collective:
    """One collective a step issues: which axis runs it, the framework's name
    for what it moves, the ranks it happens over (in the world's rank order),
    the elements it moves per rank, a short algorithm label, and the I9
    `fabric.Plan` the executor would run.
    """

    axis: str
    name: str
    group: tuple
    length: int
    algo: str
    plan: fabric.Plan


@dataclass(frozen=True)
class MemoryLine:
    """One line of a plan's ledger: a kind of state, the ranks it lives over,
    and the bytes each of those ranks holds."""

    what: str
    group: tuple
    bytes: int


@dataclass(frozen=True)
class StepPlan:
    """One step as data: the collectives it issues, in order; the ticks of
    compute the step owns; and the ledger of the state each rank holds."""

    collectives: tuple
    compute: int
    memory: tuple


#: The training state a rank holds, as a rate per parameter: the bf16
#: parameters and their gradients (2 bytes each), the fp32 master weights (4)
#: and the two fp32 Adam moments (8). Sixteen bytes per parameter in all, and
#: the ledger reports every kind — counting only the parameters is four.
_STATE_BYTES_PER_PARAM = (
    ("params", model.PARAM_BYTES),
    ("gradients", model.PARAM_BYTES),
    ("masters", model.MASTER_BYTES),
    ("optimizer", model.OPTIMIZER_BYTES),
)


def plan_bytes(plan):
    """The bytes moved per rank, summed over the plan's collectives.

    A collective's `length` is already the elements it moves per rank, in the
    direction that matters, so a collective costs `ELEMENT_BYTES * length`
    bytes per rank and the plan is their sum. The network figure is
    `network_bytes`, not this one.
    """
    total = 0
    for collective in plan.collectives:
        total += fabric.ELEMENT_BYTES * collective.length
    return total


def network_bytes(plan):
    """The bytes on the network in total: per rank times the group size.

    The same collective that costs one rank `ELEMENT_BYTES * length` costs the
    fabric `ELEMENT_BYTES * length * len(group)`, because every member of the
    group handles its own copy. A tree's per-rank figure and its network figure
    differ by the group size; that gap is the point of counting both.
    """
    total = 0
    for collective in plan.collectives:
        total += fabric.ELEMENT_BYTES * collective.length * len(collective.group)
    return total


def plan_memory(shape, plan):
    """The ledger: one line per (what, group), bytes per rank.

    For every group the plan's collectives run over, the state is divided over
    that group, so each rank holds `ceil(rate * params / len(group))` bytes of
    every kind. Lines are one per (what, group) in the order the groups first
    appear, so a plan that names one group twice still gets one ledger for it.
    """
    total = shape.params()
    seen = []
    lines = []
    for collective in plan.collectives:
        group = collective.group
        if group in seen:
            continue
        seen.append(group)
        for what, rate in _STATE_BYTES_PER_PARAM:
            lines.append(MemoryLine(
                what, group, model.ceil_div(rate * total, len(group))))
    return tuple(lines)


def _transfer_ticks(world, transfer):
    """What one transfer costs: every hop's latency, every hop's byte time."""
    hops = world.hops_of(transfer)
    if hops is None:
        raise fabric.FabricError(
            "transfer %r cannot be routed on %s" % (transfer, world))
    size = fabric.ELEMENT_BYTES * transfer.length
    ticks = 0
    for link in hops:
        ticks += link.latency + fabric.ceil_div(size, link.bandwidth)
    return ticks


def _step_cost(world, fabric_plan, step):
    """What one step of a fabric plan costs: its slowest transfer, or nothing
    if the step is empty."""
    transfers = fabric_plan.at(step)
    if not transfers:
        return 0
    return max(_transfer_ticks(world, transfer) for transfer in transfers)


def plan_ticks(world, fabric_plan):
    """What a fabric plan costs: the sum of its steps' costs.

    A step is its slowest transfer (they overlap); a plan is the sum of its
    steps (they do not). An empty plan has no steps and costs nothing.
    """
    total = 0
    for step in fabric_plan.steps():
        total += _step_cost(world, fabric_plan, step)
    return total


def step_ticks(world, plan):
    """What a `StepPlan` costs: the maximum of its compute and its comms.

    Every plan in this course overlaps communication with compute, so a step
    ends at whichever runs longer; adding the two instead charges the fabric
    for time that the compute spent waiting and the comms spent running.
    """
    comms = 0
    for collective in plan.collectives:
        comms += plan_ticks(world, collective.plan)
    return max(plan.compute, comms)


def params_by_rank(shape, *, ranks):
    """The parameters each rank of a `ranks`-rank plan holds.

    The plan's rule is not the model's (`ModelShape.params_per_world`): the
    reference puts whole equal parts on every rank and refuses a world the
    parameter set does not divide, while a plan may shard the remainder on
    purpose. The remainder is spread one parameter at a time over the first
    ranks, so the shares differ by at most one and their sum is the whole
    parameter set. A rank count below one is refused, naming it.
    """
    if isinstance(ranks, bool) or not isinstance(ranks, int) or ranks < 1:
        raise model.ModelError("ranks=%r is not a positive int" % (ranks,))
    total = shape.params()
    base, extra = divmod(total, ranks)
    shares = []
    for index in range(ranks):
        share = base
        if index < extra:
            share += 1
        shares.append(share)
    return tuple(shares)
