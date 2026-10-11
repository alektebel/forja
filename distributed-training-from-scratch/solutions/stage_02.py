"""Distributed Training From Scratch — stage 2: Data parallel (implementation).

The reasoning behind the plan lives in the template's docstring (`stage_02.py`);
this file is only the body. Nothing here is measured: the gradient is cut into
buckets by a byte threshold, each bucket is the pipelined ring all-reduce
`plans.py` builds, the step's compute is the whole step's, and every number is
an `int`.
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


def _fill_order(shape):
    """The flat gradient's layout, in the order the backward pass fills it.

    The backward pass reaches the last layer's tensors first and the embedding
    last, so the flat buffer is the trainable tensors in *reverse* `tensors()`
    order, offsets accumulating. Each row is `(name, offset, elements)`.
    """
    rows = []
    offset = 0
    for tensor in reversed(shape.tensors()):
        if not tensor.trainable:
            continue
        rows.append((tensor.name, offset, tensor.elements))
        offset += tensor.elements
    return tuple(rows)


def _tensors_in(rows, start, end):
    """The names of the tensors the element range `[start, end)` overlaps."""
    names = []
    for name, offset, elements in rows:
        if offset < end and start < offset + elements:
            names.append(name)
    return tuple(names)


def _per_rank(plan):
    """The elements the busiest rank moves: a Collective's per-rank figure.

    It is read off the plan the executor would run, not assumed: every rank
    sends what its own transfers say, and the direction that matters is the
    one that moves the most.
    """
    sent = {}
    for transfer in plan.transfers:
        sent[transfer.src] = sent.get(transfer.src, 0) + transfer.length
    if not sent:
        return 0
    return max(sent.values())


def _ledger(shape, world):
    """The state every data-parallel rank holds: the whole model, replicated.

    Stage 1's `plan_memory` divides a kind over the group its collective runs
    over — ZeRO's rule (stages 3 and 4). Data parallel shards nothing: the
    bucket's group is the world and every rank holds all sixteen bytes per
    parameter, which is the cost the sharding stages go on to attack.
    """
    total = shape.params()
    ranks = tuple(world.ranks)
    return tuple(stage_01.MemoryLine(what, ranks, rate * total)
                 for what, rate in _STATE_BYTES_PER_PARAM)


def bucket_schedule(shape, world, *, bucket_bytes):
    """The step's gradient all-reduce, bucketed, in the backward's order.

    The flat gradient (the trainable tensors in reverse `tensors()` order) is
    cut into consecutive buckets of `bucket_bytes // ELEMENT_BYTES` elements;
    the last bucket is the remainder, so the buckets tile the whole gradient and
    the count is `ceil(elements / capacity)`. Each bucket's all-reduce is the
    pipelined ring, one chunk per rank, over a buffer rounded up to the group's
    rank count (the equal chunks the ring demands). A group of one rank has
    nothing to reduce and gets no buckets at all.
    """
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    if isinstance(bucket_bytes, bool) or not isinstance(bucket_bytes, int) \
            or bucket_bytes < 1:
        raise model.ModelError(
            "bucket_bytes=%r is not a positive int" % (bucket_bytes,))
    capacity = bucket_bytes // fabric.ELEMENT_BYTES
    if capacity < 1:
        raise model.ModelError(
            "bucket_bytes=%d is under one %d-byte element"
            % (bucket_bytes, fabric.ELEMENT_BYTES))
    group = tuple(world.ranks)
    if len(group) < 2:
        return ()
    rows = _fill_order(shape)
    total = shape.params()
    buckets = []
    start = 0
    index = 0
    while start < total:
        length = min(capacity, total - start)
        padded = model.ceil_div(length, len(group)) * len(group)
        buckets.append(Bucket(
            index=index,
            tensors=_tensors_in(rows, start, start + length),
            offset=start,
            length=length,
            padded=padded,
            group=group,
            plan=plans.ring_allreduce(world, group, padded,
                                      chunk=len(group))))
        start += length
        index += 1
    return tuple(buckets)


def data_parallel(shape, world, *, batch, seq, bucket_bytes=25_000_000):
    """One data-parallel step: the bucketed gradient all-reduce, hidden.

    The collectives are the buckets in the order the backward pass fills them,
    each wrapped as a `Collective` whose `length` is the per-rank elements its
    own plan moves. The step's `compute` is the **whole** step's
    (`ComputeModel.compute_ticks` over the rank's micro-batch), because the
    buckets' communication happens *beside* it: stage 1's `step_ticks` takes the
    maximum, so the plan's price is `max(compute, comms)` and never their sum.
    """
    buckets = bucket_schedule(shape, world, bucket_bytes=bucket_bytes)
    compute = _COMPUTE.compute_ticks(shape, batch=batch, seq=seq)
    collectives = tuple(
        stage_01.Collective("dp", "grads", bucket.group, _per_rank(bucket.plan),
                            "ring", bucket.plan)
        for bucket in buckets)
    return stage_01.StepPlan(collectives=collectives, compute=compute,
                             memory=_ledger(shape, world))
