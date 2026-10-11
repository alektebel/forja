"""Distributed Training From Scratch — stage 1: The shapes and the ledger

Below this stage are the provided world and its calculus: `fabric.py` (ranks
joined by links with a bandwidth in bytes per tick and a latency in ticks, a
plan as transfers placed in steps, and an executor that applies it), `model.py`
(the deterministic shape calculus — the constants, `ModelShape`, the reference
arithmetic) and `plans.py` (I9's ten collectives lifted into one module). None
of that prices anything or remembers anything. This stage is the two things
every later stage composes: the **frozen shapes** a plan is written in, and the
two counters that read a plan — the bytes it moves and the ledger of the state
each rank holds.

A `StepPlan` is data: its collectives (each a `Collective`, wrapping a
`plans.py` `fabric.Plan`), the ticks of compute the step owns, and its
`memory`. The counters are pure functions of that data and of the shape: the
bytes a step moves per rank (`plan_bytes`), the bytes the fabric carries in
all (`network_bytes`), the memory each rank holds (`plan_memory`), the ticks a
fabric plan costs (`plan_ticks`), the ticks a step costs once compute and comms
overlap (`step_ticks`), and the parameters each rank of a world holds
(`params_by_rank`). Nothing is timed, so "cost" is a count; and every count is
an `int`, because a fraction of a tick — or of a parameter — is not a thing
this course can represent.

DESIGN DECISION — why sixteen bytes per parameter, and not the four an element
is worth?
    A training step does not only hold the parameter. It holds the bf16
    parameter and its bf16 gradient (2 bytes each), the fp32 master weight the
    optimizer updates (4), and the two fp32 Adam moments (8). Sixteen bytes per
    parameter, and the ledger must report every one of them. Counting only the
    parameter — or charging the buffer element size, four — is the mistake that
    makes a 7B model look like it fits in a quarter of the memory it needs, and
    it is exactly the arithmetic a real estimate gets wrong first.

DESIGN DECISION — why is the ledger separate from the bytes a step moves?
    They answer different questions and disagree on purpose. `plan_bytes` and
    `network_bytes` count what *crosses the fabric*: a number that is the same
    however the state is held. `plan_memory` counts what *stays on a rank*: one
    line per (what, group) and the bytes per rank for each. A data-parallel step
    and a ZeRO step can move the same bytes and hold different state; a tree
    moves the same bytes with a different network figure. Collapsing the two
    would hide the sharding, which is what stages 3 and 4 are about.

DESIGN DECISION — why is a step's cost a maximum, and a plan's a sum?
    A step is what the fabric lets run at once: a step's transfers are placed
    so no link carries two of them the same way, so they overlap in time and the
    step ends when the slowest one ends — the maximum, not the sum. A plan's
    steps run one after the other, so the plan ends when the last step ends —
    the sum, not the maximum. Summing a step or maximising a plan is the cost of
    a different schedule, and reading only the plan's last step throws away
    every step before it. An empty plan has no steps and costs nothing.

DESIGN DECISION — why does a transfer cost per hop as well as per byte?
    Every byte crosses every link on the route, so the price is per byte over
    each hop's bandwidth (`ceil(bytes / bandwidth)`), and each hop charges its
    latency once for the transfer. A flat per-message price would make a
    three-hop transfer cost a one-hop one, and a 400-element transfer cost a
    4-element one — erasing the size and distance dependence the rest of the
    course compares. The byte time is ceiled, never floored or rounded: a link
    still busy at the end of a tick has not finished, and a fraction of a tick
    cannot be represented.

DESIGN DECISION — why does the plan's rule shard the remainder rather than drop
it, where the model's rule refuses uneven division?
    The model's `params_per_world` refuses a world the parameter set does not
    divide, because the *reference* puts whole equal parts on every rank — a
    mismatch is a bug it must name. A *plan* may shard on purpose: the remainder
    is spread one parameter at a time over the first ranks, so the shares differ
    by at most one and their sum is the whole parameter set. Dropping the
    remainder loses parameters; spreading it over every rank invents them. The
    two rules disagree exactly where a ledger bug hides, which is why the plan
    owns its own answer.

TODO: implement `plan_bytes`, `network_bytes`, `plan_memory`, `plan_ticks`, `step_ticks` and `params_by_rank`.
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


def plan_bytes(plan):
    """The bytes moved per rank, summed over the plan's collectives.

    A collective's `length` is already the elements it moves per rank, in the
    direction that matters, so a collective costs `ELEMENT_BYTES * length`
    bytes per rank and the plan is their sum. The network figure is
    `network_bytes`, not this one.
    """
    raise NotImplementedError("stage 1: implement plan_bytes()")


def network_bytes(plan):
    """The bytes on the network in total: per rank times the group size.

    The same collective that costs one rank `ELEMENT_BYTES * length` costs the
    fabric `ELEMENT_BYTES * length * len(group)`, because every member of the
    group handles its own copy. A tree's per-rank figure and its network figure
    differ by the group size; that gap is the point of counting both.
    """
    raise NotImplementedError("stage 1: implement network_bytes()")


def plan_memory(shape, plan):
    """The ledger: one line per (what, group), bytes per rank.

    For every group the plan's collectives run over, the state is divided over
    that group, so each rank holds `ceil(rate * params / len(group))` bytes of
    every kind. Lines are one per (what, group) in the order the groups first
    appear, so a plan that names one group twice still gets one ledger for it.
    """
    raise NotImplementedError("stage 1: implement plan_memory()")


def plan_ticks(world, fabric_plan):
    """What a fabric plan costs: the sum of its steps' costs.

    A step is its slowest transfer (they overlap); a plan is the sum of its
    steps (they do not). An empty plan has no steps and costs nothing.
    """
    raise NotImplementedError("stage 1: implement plan_ticks()")


def step_ticks(world, plan):
    """What a `StepPlan` costs: the maximum of its compute and its comms.

    Every plan in this course overlaps communication with compute, so a step
    ends at whichever runs longer; adding the two instead charges the fabric
    for time that the compute spent waiting and the comms spent running.
    """
    raise NotImplementedError("stage 1: implement step_ticks()")


def params_by_rank(shape, *, ranks):
    """The parameters each rank of a `ranks`-rank plan holds.

    The plan's rule is not the model's (`ModelShape.params_per_world`): the
    reference puts whole equal parts on every rank and refuses a world the
    parameter set does not divide, while a plan may shard the remainder on
    purpose. The remainder is spread one parameter at a time over the first
    ranks, so the shares differ by at most one and their sum is the whole
    parameter set. A rank count below one is refused, naming it.
    """
    raise NotImplementedError("stage 1: implement params_by_rank()")
