"""Distributed Training From Scratch — stage 2: Data parallel

Stage 1 froze the shapes a plan is written in and the two counters that read
it. This stage writes the first plan on top of them: the *data-parallel step*.
Replicate the model on every rank, split the batch across them, and every rank
ends up with a partial gradient that is only its own micro-batch's; the step's
communication is the element-wise sum of those partials, on every rank — an
all-reduce of the gradient over the data-parallel group. That is the whole
mechanism, and the whole exercise is what it costs once it is done the way a
framework does it: not one all-reduce of one buffer, but a **schedule** of
buckets, filled by the backward pass, each reduced as soon as it is full, all
of it hidden behind the step's compute.

Everything this stage builds composes what is already there: `plans.py`'s
`ring_allreduce` is the bucket's all-reduce (its pipeline, its chunking, its
refusals), `model.py`'s `ComputeModel` is the step's compute, and stage 1's
`Collective`/`StepPlan`/`MemoryLine` are the shapes and `step_ticks` is the
price. Nothing here re-derives a tick or a byte.

DESIGN DECISION — why is the step's `compute` the whole step's, instead of the
part of the compute that is left over after the comms?
    Because they overlap, and the whole point of a bucket schedule is that they
    do. The gradients of a layer are ready the moment that layer's backward
    finishes, so the bucket's reduce-scatter runs *beside* the backward of the
    layers before it — the step is not compute then communication, it is both
    at once, and it ends when the slower one does. Stage 1's `step_ticks` owns
    that rule (`max(compute, comms)`), and this stage must not re-declare an
    `overlap` of its own: it hands `StepPlan` the step's full compute and lets
    `step_ticks` take the maximum. Adding the two — or handing over `compute -
    comms`, which is the same mistake with a sign — charges the fabric for time
    the compute spent waiting, and is the failure this stage exists to show.

DESIGN DECISION — why bucket the gradient at all, when one all-reduce of the
whole thing moves the fewest steps?
    Because the steps of a whole-gradient ring are all *full*: one chunk means
    two `N-1`-step walks, each step carrying the entire gradient, and the walk
    cannot start until the last gradient exists. Cut into buckets, the ring is
    pipelined — one chunk per rank, every step carrying one rank's share — and
    each bucket's reduction starts the moment the backward fills it, so the
    last buckets' comms overlap the first buckets' all-gather and the step's
    own tail. The bucket is the classic 25 MB staging buffer, and its size is
    the trade: bigger buckets mean fewer launches and a later start, smaller
    ones mean more launches and less overlap. The step still all-reduces the
    gradient exactly once — one schedule per step, never one all-reduce per
    micro-batch, which would multiply the bytes by the micro-batch count.

DESIGN DECISION — why does the bucket's order come from the backward pass, and
not from the model's own tensor order?
    The backward pass reaches the *last* layer's tensors first and the
    embedding last, so the flat gradient buffer is the trainable tensors in
    *reverse* `tensors()` order, and a bucket filled first holds the last
    layer's gradients. The bucket schedule is a schedule: the reduction of a
    bucket can only start once that bucket is full, so a bucket order taken
    from the forward pass (or from the model's definition order) would start
    the embedding's all-reduce first, when the last thing the backward produces
    is what is ready — the plan would be one long stall dressed as a pipeline.

DESIGN DECISION — why one chunk per rank, and why is the last bucket rounded up
to the group's size?
    A chunk count below the rank count leaves the ring half idle: with `c`
    chunks only `c` of `N` ranks send in any step, so the walk is
    latency-bound — the whole buffer per step, `2(N-1)` times — exactly what
    the bucket exists to avoid. One chunk per rank is the pipelined form, and
    it is what makes the per-rank figure `2S(N-1)/N` rather than `2S`. The ring
    needs *equal* chunks, though, and the last bucket is a remainder that need
    not divide the group, so it is padded up to the group's rank count: a few
    elements of dead weight in one bucket, against a whole ring that would
    otherwise fall back to a chunk count that cannot pipeline.

DESIGN DECISION — why is the bucket's `length` the per-rank elements, and why
is it read off the plan instead of computed from the buffer?
    A collective's `length` is what one rank *moves*, not the size of the
    buffer it moves — that is stage 1's definition and the reason `plan_bytes`
    is per rank. A ring all-reduce moves `2S(N-1)/N` elements per rank (S here
    is the bucket's buffer), so declaring `2S` would price the tree's
    reduce-to-root-then-broadcast instead of the ring, and declaring `S` would
    price one of the two phases. Reading the figure off the plan the executor
    would run — the busiest rank's own transfers — keeps the declaration and
    the plan from drifting apart, which is the only way a byte count can be
    believed.

DESIGN DECISION — why is the ledger the whole state on every rank, when stage 1
has a `plan_memory` that divides it over the group?
    Because data parallel shards *nothing*. Stage 1's `plan_memory` divides
    every kind over the group its collective runs over, which is ZeRO's rule
    (stages 3 and 4); a data-parallel rank holds the parameters, the
    gradients, the fp32 masters and the Adam moments in full — sixteen bytes
    per parameter, replicated `N` times across the world, plus its buckets in
    flight. That replication is the entire reason ZeRO exists, so the stage
    that shows it must not borrow the sharded ledger: the two plans move the
    same bytes and hold different state, which is what the ledger is for.

TODO: implement `bucket_schedule` and `data_parallel`.
"""

from dataclasses import dataclass

import fabric
import model
import plans
import stage_01

#: The device a step's compute is priced on: a teraflop per tick. The fabric is
#: deliberately slow beside it, so the byte fixtures below are comms-bound and
#: the rule under test — `max(compute, comms)`, never their sum — is visible.
_COMPUTE = model.ComputeModel(flops_per_tick=1_000_000_000_000)

#: What a data-parallel rank holds, at each kind's own dtype: the bf16
#: parameter and its bf16 gradient (2 bytes each), the fp32 masters (4) and the
#: two fp32 Adam moments (8). Data parallel **replicates** every kind — no shard
#: anywhere — which is why the ledger is the full state on every rank.
_STATE_BYTES_PER_PARAM = (
    ("params", model.PARAM_BYTES),
    ("gradients", model.PARAM_BYTES),
    ("masters", model.MASTER_BYTES),
    ("optimizer", model.OPTIMIZER_BYTES),
)


@dataclass(frozen=True)
class Bucket:
    """One gradient bucket: a slice of the flat gradient, and its all-reduce.

    `index` is the bucket's position in the backward's fill order (0 is filled
    first); `tensors` are the tensor names the bucket overlaps, in that same
    order; `offset` and `length` are the slice's element range in the flat
    gradient buffer; `padded` is the length rounded up to the group's rank
    count, which is the buffer the ring's equal chunks actually carry; `group`
    is the ranks it all-reduces over; and `plan` is `plans.ring_allreduce`'s
    plan for `padded` elements, one chunk per rank.
    """

    index: int
    tensors: tuple
    offset: int
    length: int
    padded: int
    group: tuple
    plan: fabric.Plan


def bucket_schedule(shape, world, *, bucket_bytes):
    """The step's gradient all-reduce, bucketed, in the backward's order.

    The flat gradient (the trainable tensors in reverse `tensors()` order) is
    cut into consecutive buckets of `bucket_bytes // ELEMENT_BYTES` elements;
    the last bucket is the remainder, so the buckets tile the whole gradient and
    the count is `ceil(elements / capacity)`. Each bucket's all-reduce is the
    pipelined ring, one chunk per rank, over a buffer rounded up to the group's
    rank count, and the bucket's `length` is the elements one rank moves. A
    group of one rank has nothing to reduce: the schedule is empty, not a plan
    of empty transfers. A `shape` that is not a `ModelShape` and a
    `bucket_bytes` that is not a positive whole count of bytes are refused.
    """
    raise NotImplementedError("stage 2: implement bucket_schedule()")


def data_parallel(shape, world, *, batch, seq, bucket_bytes=25_000_000):
    """One data-parallel step: the bucketed gradient all-reduce, hidden.

    The collectives are the buckets in the order the backward pass fills them,
    each wrapped as a `Collective` whose `length` is the per-rank elements its
    own plan moves. The step's `compute` is the **whole** step's
    (`ComputeModel.compute_ticks` over the rank's own micro-batch of `batch`
    sequences of `seq`), because the buckets' communication happens *beside*
    it: stage 1's `step_ticks` takes the maximum, so the plan's price is
    `max(compute, comms)` and never their sum. The ledger is the replicated
    state, sixteen bytes per parameter on every rank.
    """
    raise NotImplementedError("stage 2: implement data_parallel()")
