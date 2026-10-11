"""Interconnects From Scratch — stage 10: One step, end to end

The last stage is the composition. A training step of a shape
`(dp, tp, pp, moe)` over `length` elements is four collectives at once, one per
parallelism axis, and `step_plan` answers them as a dict of four plans whose
keys are fixed: `"grads"` (the data-parallel gradient all-reduce), `"params"`
(the tensor-parallel pair of all-reduces), `"activations"` (the pipeline's
sends across the stage boundaries) and `"experts"` (the expert dispatch and
combine). Nothing new is built here: the two all-reduces come from
`stage_09.choose`, the pipeline boundary from `stage_08.sendrecv`, and the two
expert exchanges from `stage_07.all_to_all`. Nothing is timed either:
`step_ticks` prices the step's communication with `stage_01.plan_ticks`, and
`overlap` puts that price beside the step's compute.

The world is the topology's own rank ids, one per rank of the shape. The four
axes are laid out over them in one frozen order and frozen once, here, so that
a plan can be read rank by rank:

    width = max(moe, 1)                     # an expert axis of zero is dense
    rank index of (dp_i, tp_i, pp_i, moe_i) =
        ((pp_i * dp + dp_i) * width + moe_i) * tp + tp_i

so the topology's rank `ri` is the coordinate above read back in that order,
the pipeline coordinate outermost and the tensor coordinate innermost. A shape
of `dp=2, tp=2, pp=2, moe=2` is therefore sixteen ranks, and, for example, the
tensor pair of the first stage's first replica is `r0` and `r1` while its
data-parallel group is `r0` and `r4` — a group is a set of rank ids, and the
four design decisions below say why they are these ids, what a step's
communication costs, and which collectives a step holds.

DESIGN DECISION — how are the four parallelism axes laid out on the topology's
rank ids, and why? The tensor axis is innermost, so its group is a run of
consecutive rank ids: tensor parallelism all-reduces twice per layer over the
whole step, so it earns the fabric's shortest and cheapest links, exactly as a
node's NVLink domain is numbered. The expert axis is next, one all-to-all per
MoE layer; then the data axis, whose gradient all-reduce runs once per step and
may span the widest tier; and the pipeline axis is outermost, so each stage
owns one contiguous block of ranks and the handoff to the next stage crosses
one adjacent pair. The rejected alternative is a flat `range(dp * tp * pp)` read
of the rank ids, with each axis a plain contiguous block and the data axis
fastest: its cost is that the tensor all-reduce ends up crossing the slow tier
while the gradient all-reduce rides the cheap one — `choose`'s prices invert —
and a shape with `moe > 1` is not representable at all, because the world would
be counted as `dp * tp * pp` ranks and a shape that fits the fabric would be
refused as too wide.

DESIGN DECISION — why is an axis's plan the plan of its first group, and not of
every group at once? The groups of one axis partition the ranks into as many
disjoint sets as the axis has coordinates, and every group runs the same
collective on the same shape of fabric, so one group's plan says what the axis
does and its price is the axis's price. A group of a single rank has nothing to
collect (a collective needs two ranks) and gets the empty plan, which costs
zero. The rejected alternative is concatenating every group's plan into one:
its cost is that the groups' phases then have to be interleaved step by step (a
group whose `choose` picks a longer algorithm shifts the phases of the others),
and on a ring two groups' routes cross each other's ranks, so the concatenation
can carry two transfers on one directed link in a step and be illegal — for a
price that comes out the same, since the step is as slow as its slowest transfer
anyway. A group is also a fabric in its own right: its links are the fabric's
links between its own ranks, and a group whose members cannot reach each other
over those links is refused, naming the axis, rather than quietly routed over
another axis's ranks.

DESIGN DECISION — why is a step's communication the slowest axis instead of the
sum of the axes? The four axes partition the same ranks into four disjoint sets,
so the four collectives run at once and the step's communication is as slow as
the slowest of them: `step_ticks` is the maximum of the axes' prices, zero when
all four plans are empty. The rejected alternative is adding the axes' prices:
its cost is billing a step for four collectives in a row when its ranks pay for
one at a time — the main fixture's step, 21 ticks of gradients, 42 of tensor
pair, 21 of pipeline and 26 of experts, would be priced 110 instead of 42 — and
the overstatement grows with the number of axes, which is not a property of the
fabric at all.

DESIGN DECISION — why does `overlap` return the maximum of compute and
communication, and what does adding them overstate? A step is one wall clock: a
rank computes while the network moves bytes, and the step is over when the
slower of the two is over, so `overlap(compute_ticks, comms_ticks)` is their
maximum. The rejected alternative is their sum, and its cost is that it bills
compute and communication as if one waited for the other, so the entire fraction
of the communication hidden behind compute — the whole point of overlapping —
is charged twice: a step of 120 compute ticks and 90 communication ticks takes
120 ticks, not 210, and the sum would make overlap a pessimist's model in which
overlapping is never worth doing.

DESIGN DECISION — why is the gradient all-reduce once per step and not once per
micro-batch? Micro-batches accumulate their gradients into one buffer on each
rank, and the collective runs when the accumulation window closes. A collective
is linear, so the all-reduce of the accumulated partials is exactly the sum of
the all-reduced per-micro-batch partials: one all-reduce carries the same
answer for one collective's price. The rejected alternative is an all-reduce per
micro-batch: its cost is the accumulation factor — with four micro-batches the
same bytes are sent four times, the step's communication is inflated fourfold
(and `step_ticks` doubles under it in the main fixture), while the buffers the
caller ends up with are identical.

DESIGN DECISION — why is the tensor axis's plan a pair of all-reduces? A
tensor-parallel layer touches the world twice: the row-parallel forward
all-reduce and the column-parallel backward one, the two halves that keep the
sharded activations and gradients consistent, so the axis's plan holds two
all-reduces over the tensor group, the second in the steps after the first.
The rejected alternative is a single all-reduce: its cost is pricing half of
the tensor communication, and the half it drops is the backward one — the same
number of bytes as the forward, paid once per layer, so a one-all-reduce tensor
axis understates the axis the fabric is laid out around in the first place.

TODO: implement `step_plan`, `step_ticks` and `overlap`.
"""


def step_plan(topology, *, dp, tp, pp, moe, length):
    """The four collectives one training step of this shape needs, as plans.

    Answers a `dict` with the fixed keys `"grads"`, `"params"`, `"activations"`
    and `"experts"`, each a `fabric.Plan` for that axis's collectives: the
    data-parallel all-reduce over the `dp` group, the tensor-parallel pair of
    all-reduces over the `tp` group, the pipeline's sends across the `pp - 1`
    stage boundaries as one launch, and the expert dispatch and combine as two
    exchanges over the `moe` group. An axis of one rank has no collective and
    gets the empty plan, and so does an expert axis of zero (a dense step).
    Refuses, with `FabricError` naming the offender, a shape whose rank count is
    not the fabric's, a length that is not a positive whole count, and a
    negative axis.
    """
    raise NotImplementedError("stage 10: implement step_plan()")


def step_ticks(topology, plan):
    """What the step's communication costs: the slowest of its four axes.

    `plan` is the dict `step_plan` answered. The four axis groups are disjoint
    sets of ranks, so their collectives run at once: the price is the largest of
    the axes' `stage_01.plan_ticks`, and zero when all four plans are empty.
    """
    raise NotImplementedError("stage 10: implement step_ticks()")


def overlap(compute_ticks, comms_ticks):
    """The step's wall clock: the slower of its compute and its communication.

    Compute and the network proceed at once, so this is their maximum, never
    their sum. Both arguments are whole tick counts.
    """
    raise NotImplementedError("stage 10: implement overlap()")
