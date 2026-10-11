"""Distributed Training From Scratch — stage 5: Tensor parallel

Stage 1 froze the shapes and the counters; stages 2 to 4 shard the **state** (the
gradients, the optimizer, the parameters) over a group. This stage shards the
**computation**: one projection's weight and its activation are cut across the
group, every rank multiplies its own block, and the two halves of the block
combine what they must with one all-reduce each and nothing else.

The block is one MLP projection pair: a **column-parallel** half followed by a
**row-parallel** half. In the column half each rank owns a contiguous block of
the projection's *output neurons*, multiplies the full input by its own rows of
the weight, and holds a *disjoint* slice of the result — no rank needs anything
from another, so this half costs no fabric at all. In the row half each rank
owns a matching block of the second projection's *input features*: every rank
multiplies its shard of the intermediate by its own block, and what it holds is
a **partial** sum, not yet the projection's output. Only the all-reduce over the
group turns those partials into the answer.

`reference_layer` is the arithmetic all of this must reproduce, **exactly**:
`y[i][j] = b[j] + sum_k x[i][k] * w[j][k]`, one row of `w` per output neuron.
`column_parallel` and `row_parallel` are the two halves on one rank's own
blocks; `f` and `g` are those two halves under the names the fixture composes.
A check that slices a weight into blocks, applies the halves across a group and
sums what the collectives carry must land on `reference_layer`'s own `int`s —
not near them — and must land there for every split of the group. Every number
here is an `int`, on the fixture matrices and in the plan.

`tensor_parallel` turns the block into the `StepPlan` stage 1 froze: the
collectives the block issues, in the order it issues them. A block issues two —
the forward's all-reduce at the row-parallel boundary, where the partials
become the projection's output, and the backward's all-reduce where the
gradient enters the column-parallel half — and each moves the block's own
activation, `batch * seq * hidden` elements per rank.

DESIGN DECISION — why do the two halves split the weight differently?
    They must, because the two halves leave *different things* on a rank. The
    column half's ranks produce disjoint slices of the projection's output, so
    splitting the weight one row per output neuron leaves each rank holding a
    complete answer for its own columns and the group needs no fabric at all.
    The row half's ranks each contract a *different* block of the input
    features, so every rank's result is a partial sum over the whole output and
    the all-reduce is what makes it an answer. The rejected alternative — split
    both halves the same way — either ends with an all-reduce that combines
    nothing (a block that pays the fabric for arithmetic it did not do) or ends
    with a partial that nothing combines (a block that is simply wrong while
    looking cheaper). Which half owns the bias is the same question: the half
    whose output is complete.

DESIGN DECISION — why two all-reduces per block, and what does one get wrong?
    The forward all-reduce is the row half's combine; the backward all-reduce
    is the gradient of the column half's input, which is a row-parallel
    traversal of the same shape and arrives as partials too. A block with a
    single all-reduce leaves one of the two uncombined: the forward keeps the
    row half's partials and the model's output is wrong by everything the other
    ranks contributed, or the backward keeps the column half's gradient
    partials and every rank descends along a fraction of the true gradient. Both
    failures are silent — the numbers stay the right shape and the right
    magnitude — which is why the count is asserted, not the flops.

DESIGN DECISION — why is the all-reduce sized by the block's activation?
    The tensor that crosses the fabric is the one the row half is summing: the
    projection's output, `batch * seq * hidden` elements per rank — one entry
    per token per output feature the model has at that point, `hidden`. Sizing
    it by the FFN's intermediate (`ffn_hidden`) charges the wider tensor the
    column half keeps sharded and never moves; sizing it for the whole layer, or
    by the parameter count, charges the model's size for one block's boundary.
    Both stay plausible and both are wrong by a factor, which is the arithmetic
    a real tensor-parallel estimate gets wrong first.

DESIGN DECISION — why is the algorithm chosen by price rather than fixed?
    A ring is the safe answer and the expensive one on this course's fixtures:
    on `switch(8, width=4)` the tree's fifty ticks beat the ring's hundred and
    eight for the same block, while the recursive doubling that ties the tree on
    `full(4)` cannot run across the spine at all (its XOR partners are three hops
    apart). That is I9's own rule and its own candidates: build every all-reduce
    `plans.py` can build, price each with `stage_01.plan_ticks` on the group's
    own fabric, drop a candidate whose preconditions fail instead of raising,
    keep the cheapest and break a tie by the candidate order. A fixed algorithm
    is a size table by another name, right on the fabric it was measured on.

DESIGN DECISION — why is a group of one an empty plan, not a one-rank
all-reduce?
    `plans.py`'s rule: a collective over one rank has nothing to combine, so its
    plan is empty and costs nothing. A `tp` axis of one that still emitted its
    two collectives would charge a step for traffic between a rank and itself —
    the "axis of one still emitting that axis's collectives" mistake stage 10
    names — so the block's plan has no collectives, no compute and no ledger,
    and a group of one is what makes the axis vanish rather than shrink.

DESIGN DECISION — why does the block's plan carry no compute?
    The compute a step spends belongs to the step and to its device, and
    `ComputeModel.compute_ticks` is where this course turns flops into ticks; a
    block's `shape` carries no device to do that with. What the block's plan
    states is the **traffic it adds** — its two all-reduces — so that a caller
    that owns a `ComputeModel` can price the whole step with stage 1's
    `step_ticks` (the maximum of the two). Inventing a compute here would either
    double-count the step's own or hide the traffic behind it.

TODO: implement `column_parallel`, `row_parallel`, `f`, `g` and `tensor_parallel`.
"""

import fabric
import model
import plans
import stage_01


def column_parallel(x, w):
    """The block's first half: one rank's slice of the projection's output.

    `x` is the full, replicated input activation, one row per token
    (`rows x inner`). `w` is the rank's block of the projection's weight, laid
    out the way `reference_layer` lays a weight out — one row per output neuron
    the rank owns, `out_local x inner`. The answer is `rows x out_local` with
    `y[i][j] = sum_k x[i][k] * w[j][k]`: the rank's own columns of the
    projection's output. The ranks' answers are disjoint and already in rank
    order, so nothing about this half crosses the fabric.

    A matrix that is not a non-empty tuple of equal-length `int` rows, and a
    weight whose inner dimension does not match the input's, are refused with
    `model.ModelError` naming the offender.
    """

    raise NotImplementedError("stage 5: implement column_parallel()")


def row_parallel(partial, w):
    """The block's second half: one rank's **partial** output.

    `partial` is the rank's shard of the intermediate activation, `rows x
    inner_local`, and `w` is the rank's block of the second projection's weight
    stored **one row per input feature the rank owns**, `inner_local x out`,
    because that is the block of the weight this rank holds. The answer is
    `rows x out` with `y[i][j] = sum_k partial[i][k] * w[k][j]`: a partial sum
    over the whole output, which the group's all-reduce turns into the
    projection's output.

    A matrix that is not a non-empty tuple of equal-length `int` rows, and a
    weight whose row count does not match the shard's column count, are refused
    with `model.ModelError` naming the offender.
    """

    raise NotImplementedError("stage 5: implement row_parallel()")


def f(x, w):
    """The block's first half under the name the fixture composes:
    `column_parallel(x, w)`, the column-parallel projection."""

    raise NotImplementedError("stage 5: implement f()")


def g(x, w):
    """The block's second half under the name the fixture composes:
    `row_parallel(x, w)`, the row-parallel projection whose answer is a partial
    until the forward all-reduce combines it."""

    raise NotImplementedError("stage 5: implement g()")


def tensor_parallel(shape, world, *, group, batch=1, seq=1):
    """One MLP block's `StepPlan`: the collectives the block issues, in order.

    `group` is the ranks the block is split over, in any order (the plan comes
    back in the world's rank order); `batch` and `seq` are the tokens the step
    runs, because the tensor at the row-parallel boundary is
    `batch * seq * hidden` elements per rank. The block issues two collectives —
    the forward's all-reduce of the row half's partials (`"activations"`) and
    the backward's all-reduce of the column half's gradient partials
    (`"grads"`) — chosen over `plans.py`'s legal all-reduce candidates by
    `stage_01.plan_ticks` on the group's own fabric. A layer repeats the pair
    once per projection (attention's query-key-value and output projections, the
    MLP's up and down projections); this plan is one block's.

    A `shape` that is not a `ModelShape`, a `batch` or `seq` that is not a
    positive count, and a group with a rank the world does not have, a rank
    named twice or no ranks at all are refused, naming the offender — the last
    three with the fabric's own `fabric.FabricError`. A group of one rank issues
    no collective: the block's plan is empty and costs nothing.
    """

    raise NotImplementedError("stage 5: implement tensor_parallel()")
