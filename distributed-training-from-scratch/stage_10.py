"""Distributed Training From Scratch — stage 10: The configuration

The nine stages before this one each answer *one* axis: how to cut the gradient
across data-parallel ranks, how to shard the training state, how to split a
block across tensor-parallel ranks, how to stream micro-batches through pipeline
stages, how to route tokens to experts, how to rotate KV blocks around a ring.
This stage answers the question a practitioner actually starts with: **given
this model and this many devices, which split of `(dp, tp, pp, ep, cp)` should
run?**

The answer is not a rule of thumb. `configure(shape, world, *, gpus)` enumerates
every split of the devices across the five axes, composes each split's step out
of the plans the earlier stages built — the dp axis's bucketed gradient
all-reduce (stage 2) or the ZeRO/FSDP gather-scatter ladder (stages 3 and 4), the
tensor block's two all-reduces (stage 5), the pipeline's sends (the schedule
stage 6 defines), the expert dispatch and combine (stage 8) and the KV ring
(stage 9) — prices each one with **stage 1's** `step_ticks`, throws away the ones
that cannot be built and the ones that cannot fit the memory budget, and returns
the `(axes, plan)` of the cheapest survivor. An axis of one contributes nothing
at all: it emits no collective and shards no state, which is why `gpus=1` is
exactly the single-device reference. `report(shape, world, plan)` then reads one
plan back and derives `step_ticks`, `compute`, `comms`, `bytes_per_rank` and
`memory_by_rank` from the plan itself.

DESIGN DECISION — why choose by ticking every candidate instead of by a rule of
thumb?
    "Use tensor parallel for a small model, data parallel for a big one" is
    folklore that is wrong on most fabrics: the same split of the same axes costs
    different ticks on a ring, a tree, a two-level switch and a full mesh,
    because a group's price is the route its own links take. The only honest
    chooser is the argmin of the price over the candidates, computed from the
    plan the rank would actually run. So `configure` enumerates every
    factorization of `gpus` into the five axes (no axis privileged, the rest of
    the space included), builds each split's plan, prices it with stage 1
    (`max(compute, comms)`, never the sum) and keeps the least. A tie goes to the
    lexicographically first tuple, which is a stated rule and not a preference.

DESIGN DECISION — why is the dp axis sized on the *local* shard rather than the
whole model?
    A data-parallel collective reduces the gradient the rank holds, and after the
    other axes have sharded the weights that gradient is the model divided by
    `tp * pp * ep`. Pricing the all-reduce on the whole model would charge the
    step for bytes no rank ever holds, and would make data parallel look
    catastrophically worse than it is in every composed configuration. So the
    axis's buckets (stage 2's rule), its reduce-scatter and its all-gather (stage
    3's and stage 4's rules) all size on `ceil_div(params, tp * pp * ep)` — and
    when nothing else shards the model, the composed plan *is* stage 2's own
    plan, bucket for bucket, byte for byte.

DESIGN DECISION — why does a configuration that cannot fit refuse instead of
being returned?
    A split that does not fit is not a slow configuration, it is one that cannot
    run: the optimizer state is 8 bytes per parameter per rank and does not care
    how elegant the split is. Silently returning it would make the chooser a
    liar, so a split whose ledger exceeds `memory_budget` is refused with a
    `model.ModelError` naming the axis that shards the overflowing kind least,
    the bytes it wants and the budget it has. In the free search the same test
    drops the candidate instead of raising, and when *no* candidate fits the
    refusal names the smallest one, because "nothing fits" must say by how much.

DESIGN DECISION — why must the report recompute instead of read numbers the
configuration already knows?
    This is the defect class the stage exists to catch: a report that declares
    `step_ticks` or `bytes_per_rank` from the configuration's own arithmetic
    agrees with itself and disagrees with the plan the moment anything about the
    plan changes — a bucket boundary, a group, an algorithm. `report` takes only
    the plan and the fabric, and every number it returns is stage 1's own: the
    price of the plan's collectives, the sum of the collectives' ticks, the
    per-rank bytes of its `length`s, and the ledger its `memory` lines already
    are. Two calls return equal reports, and a plan that moves nothing reports
    that nothing moved.

DESIGN DECISION — why does an axis of one cost nothing, and why is that a check
rather than a comment?
    A group of one rank needs no collective (nothing crosses the fabric), no
    shard (the rank already holds everything). Every axis is therefore guarded
    by its own size, and the check asserts it: a plan whose axes hold an axis of
    one must not carry a single collective belonging to that axis. Without the
    guard a `tp=1` would charge the block for an all-reduce over one rank and
    `gpus=1` would stop being the reference the whole course is measured
    against.

TODO: implement `configure` and `report`.
"""

import fabric
import model
import plans

import stage_01
import stage_03
import stage_04
import stage_05
import stage_08
import stage_09

#: The five axes, in the order a configuration tuple writes them.
AXIS_ORDER = ("dp", "tp", "pp", "ep", "cp")

#: The default per-device memory budget, in bytes: eight gibibytes.
DEFAULT_MEMORY_BUDGET = 8 << 30

#: The default gradient bucket, in bytes: stage 2's own threshold.
DEFAULT_BUCKET_BYTES = 25_000_000

#: The ZeRO ladder the dp axis runs on: 0 plain data parallel, 1 ZeRO-1, 2
#: ZeRO-2, 3 FSDP.
ZERO_MODES = (0, 1, 2, 3)


def configure(shape, world, *, gpus, memory_budget=DEFAULT_MEMORY_BUDGET,
              axes=None, zero=0, batch=1, seq=1,
              bucket_bytes=DEFAULT_BUCKET_BYTES, wrap_bytes=None):
    """The configuration for `gpus` devices, as `(axes, plan)`.

    `axes` is the chosen `(dp, tp, pp, ep, cp)` and `plan` is that split's
    `StepPlan`: the axes' collectives — the dp axis's bucketed all-reduce (stage
    2), ZeRO-1/2's sharded state and collectives (stage 3) or FSDP's per-unit
    gather/scatter (stage 4), tensor parallel's two all-reduces (stage 5),
    pipeline parallel's sends (stage 6's schedule), expert parallel's dispatch
    and combine (stage 8), context parallel's KV ring (stage 9) — laid over the
    rank ids the world has and priced by stage 1. Each axis contributes only
    when it is larger than one, so `(1, 1, 1, 1, 1)` is the single-device
    reference with no collectives at all.

    With `axes` given, that split is built and priced. Otherwise every split of
    `gpus` is built, the ones whose axes refuse and the ones that cannot fit
    `memory_budget` are dropped, and the argmin of stage 1's `step_ticks` wins,
    ties going to the lexicographically first tuple. `gpus` must be the world's
    rank count; `zero` is the dp axis's rung of the ZeRO ladder; `batch` and
    `seq` size the step; `bucket_bytes` is stage 2's gradient bucket and
    `wrap_bytes` stage 4's wrap unit (one transformer layer by default). A split
    that cannot fit is refused with a `model.ModelError` naming the axis, the
    bytes it wants and the budget; so is an `axes` that does not multiply to
    `gpus`, a `gpus` that is not the world's rank count, a non-positive count and
    an unknown ZeRO rung.
    """
    raise NotImplementedError("stage 10: implement configure()")


def report(shape, world, plan):
    """Every number of one plan, derived from the plan and nothing else.

    Returns exactly `step_ticks`, `compute`, `comms`, `bytes_per_rank` and
    `memory_by_rank`: stage 1's own `step_ticks(world, plan)` and
    `plan_bytes(plan)`, the plan's own compute, the sum of its collectives'
    stage-1 ticks, and the plan's ledger folded one entry per kind of state.
    Nothing is declared: the plan is the only input, comms are never added to
    compute, and two calls return equal reports. A `plan` that is not a
    `StepPlan`, a `shape` that is not a `ModelShape` and a `world` that is not a
    fabric are refused, naming the offender.
    """
    raise NotImplementedError("stage 10: implement report()")
