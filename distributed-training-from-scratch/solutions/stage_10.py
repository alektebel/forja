"""Distributed Training From Scratch — stage 10: The configuration (implementation).

The reasoning lives in the template's docstring (`stage_10.py`); this file is
only the body. `configure` enumerates every split of the devices across the five
axes, composes each split's step out of the earlier stages' plans plus the
pipeline's own sends, prices it with stage 1 and keeps the cheapest one that
fits the memory budget;
`report` reads one plan back and derives every number from it. Nothing here is
measured and nothing is declared: two calls return equal values, every number is
an `int`, and the numbers a report prints are the plan's own.
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

#: The default per-device memory budget, in bytes: eight gibibytes. A dense
#: model's sixteen bytes per parameter do not fit in it beyond ~500M parameters,
#: which is exactly when the axes that shard the state stop being optional.
DEFAULT_MEMORY_BUDGET = 8 << 30

#: The default gradient bucket, in bytes: stage 2's own threshold.
DEFAULT_BUCKET_BYTES = 25_000_000

#: The ZeRO ladder the dp axis runs on: 0 is plain data parallel (no state
#: sharded, stage 2's bucketed all-reduce), 1 shards the optimizer state
#: (ZeRO-1), 2 the gradients as well (ZeRO-2, stage 3's reduce-scatter and
#: parameter all-gather), and 3 the parameters too, one wrap unit at a time
#: (FSDP, stage 4's per-unit gather/scatter).
ZERO_MODES = (0, 1, 2, 3)

#: The state a rank holds, as a rate per parameter, in the frozen ledger order.
_STATE = (
    ("params", model.PARAM_BYTES),
    ("gradients", model.PARAM_BYTES),
    ("masters", model.MASTER_BYTES),
    ("optimizer", model.OPTIMIZER_BYTES),
)

#: The device a step's compute is priced on (stage 2's): a teraflop per tick, so
#: the byte figures are the ones that bite and every axis is compared on comms.
_COMPUTE = model.ComputeModel(flops_per_tick=1_000_000_000_000)


def _positive(value, what):
    """A positive whole count, or the refusal naming it."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise model.ModelError("%s=%r is not a positive int" % (what, value))
    return value


def _non_negative(value, what):
    """A whole count that may be zero, or the refusal naming it."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise model.ModelError("%s=%r is not a non-negative int" % (what, value))
    return value


def _require_shape(shape):
    """The model's shape, or the refusal naming it."""
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))


def _require_world(world):
    """The fabric, or the refusal naming it."""
    if not isinstance(world, fabric.Topology):
        raise fabric.FabricError("world=%r is not a fabric.Topology" % (world,))


def _divisors(number):
    """Every positive divisor of `number`, ascending."""
    return tuple(value for value in range(1, number + 1) if number % value == 0)


def _factorizations(gpus):
    """Every `(dp, tp, pp, ep, cp)` of positive ints whose product is `gpus`,
    in lexicographic order — the candidate space, with no axis privileged."""
    out = []
    for dp in _divisors(gpus):
        rest = gpus // dp
        for tp in _divisors(rest):
            rest2 = rest // tp
            for pp in _divisors(rest2):
                rest3 = rest2 // pp
                for ep in _divisors(rest3):
                    out.append((dp, tp, pp, ep, rest3 // ep))
    return tuple(sorted(out))


def _groups(world, axes):
    """The ranks each axis runs over, as `{axis: tuple[rank, ...]}`.

    The world's rank order lays the axes out with `dp` slowest-varying and `tp`
    fastest-varying, so a tensor-parallel group is a run of neighbouring ranks
    (which is where a cluster puts the bandwidth-hungry axis) and a
    data-parallel group is strided across the world. For an axis the group is
    the ranks that differ only in that axis.
    """
    dp, tp, pp, ep, cp = axes
    sizes = dict(zip(AXIS_ORDER, axes))
    stride = {"dp": tp * pp * ep * cp, "tp": 1, "pp": tp, "ep": tp * pp,
              "cp": tp * pp * ep}
    ranks = tuple(world.ranks)
    return {name: tuple(ranks[index * stride[name]] for index in range(sizes[name]))
            for name in AXIS_ORDER}


def _weight_shard(axes):
    """The axes that shard a parameter: `tp`, `pp` and `ep`, in one factor."""
    dp, tp, pp, ep, cp = axes
    return tp * pp * ep


def _local_params(shape, axes):
    """The parameters one rank owns before the dp axis shards anything."""
    return model.ceil_div(shape.params(), _weight_shard(axes))


def _shard(axes, zero, what):
    """The ranks a kind of state is divided over, for this configuration.

    The weight axes (`tp`, `pp`, `ep`) shard every kind they touch; the dp axis
    adds itself to a kind exactly where the ZeRO ladder says it does — nothing
    at 0, the optimizer state at 1, the gradients too at 2, everything at 3 —
    and the sequence axis splits the activations and the KV blocks.
    """
    dp, tp, pp, ep, cp = axes
    if what == "activations":
        return pp * cp
    if what == "kv":
        return cp
    weights = _weight_shard(axes)
    if what == "params":
        return weights * (dp if zero == 3 else 1)
    if what == "gradients":
        return weights * (dp if zero >= 2 else 1)
    return weights * (dp if zero >= 1 else 1)


def _ledger(shape, world, axes, *, zero, batch, seq):
    """The state each rank holds, one line per kind.

    Stage 3's rule, applied to the composed configuration: a kind is divided
    over the ranks that hold it and the line is the largest shard
    `shard_partition` hands out. The activations are what the rank's own batch
    and sequence positions cost, divided over the layers the pipeline owns and
    the positions the sequence axis owns, and a sequence axis larger than one
    adds the KV block that rank is streaming.
    """
    ranks = tuple(world.ranks)
    total = shape.params()
    lines = []
    for what, rate in _STATE:
        lines.append(stage_01.MemoryLine(
            what, ranks,
            stage_03.shard_partition(rate * total, _shard(axes, zero, what))[0]))
    lines.append(stage_01.MemoryLine(
        "activations", ranks,
        model.ceil_div(shape.activation_bytes(batch, seq),
                       _shard(axes, zero, "activations"))))
    if axes[4] > 1:
        block = batch * (seq // axes[4]) * shape.heads * shape.head_dim() * 2
        lines.append(stage_01.MemoryLine("kv", _groups(world, axes)["cp"],
                                        block * fabric.ELEMENT_BYTES))
    return tuple(lines)


def _memory_of(plan):
    """The bytes one rank holds: the plan's own ledger, summed."""
    total = 0
    for line in plan.memory:
        total += line.bytes
    return total


def _default_wrap_bytes(shape):
    """One transformer layer's parameters, in bytes: the largest unit FSDP may
    wrap without splitting a layer, and therefore the default wrap budget."""
    per_module = {}
    for tensor in shape.tensors():
        parts = tensor.name.split(".")
        module = parts[0] if parts[0] != "layer" else "layer." + parts[1]
        per_module[module] = per_module.get(module, 0) + tensor.elements
    widest = 0
    for module, elements in per_module.items():
        if module.startswith("layer.") and elements > widest:
            widest = elements
    return model.PARAM_BYTES * widest


def _words(elements, shard):
    """An `elements`-long bf16 buffer sharded by `shard`, whole words."""
    return model.ceil_div(model.ceil_div(elements, shard) * model.PARAM_BYTES,
                          fabric.ELEMENT_BYTES)


def _bucketed_allreduce(world, group, local, bucket_bytes):
    """Stage 2's bucketed gradient all-reduce, sized on the local gradient.

    The local gradient is cut into consecutive buckets of
    `bucket_bytes // ELEMENT_BYTES` elements, each an equal-chunk ring
    all-reduce over a buffer rounded up to the group's rank count, and the
    collective's `length` is what the busiest rank sends: `2 * (padded // N) *
    (N - 1)` elements. When nothing else shards the model this is stage 2's own
    plan, bucket for bucket.
    """
    total = len(group)
    capacity = bucket_bytes // fabric.ELEMENT_BYTES
    if capacity < 1:
        raise model.ModelError(
            "bucket_bytes=%d is under one %d-byte element"
            % (bucket_bytes, fabric.ELEMENT_BYTES))
    out = []
    start = 0
    while start < local:
        length = min(capacity, local - start)
        padded = model.ceil_div(length, total) * total
        per = 2 * (padded // total) * (total - 1)
        out.append(stage_01.Collective(
            "dp", "grads", group, per, "ring",
            plans.ring_allreduce(world, group, padded, chunk=total)))
        start += length
    return tuple(out)


def _data_parallel_axis(shape, world, axes, group, *, zero, bucket_bytes,
                        wrap_bytes):
    """The dp axis's collectives, one ladder rung per ZeRO mode.

    0 is stage 2's bucketed gradient all-reduce; 1 is stage 3's single ring
    all-reduce of the whole gradient; 2 is stage 3's reduce-scatter of the
    gradients plus the parameter all-gather those shards force; 3 is stage 4's
    per-wrap-unit gather and scatter. Every one of them is sized on the gradient
    the rank actually owns — the model divided by the axes that shard its
    weights — because a data-parallel collective reduces the local gradient and
    not the model's, and pricing it on the whole model would charge the step for
    bytes no rank holds.
    """
    total = len(group)
    local = _local_params(shape, axes)
    if zero == 0:
        return _bucketed_allreduce(world, group, local, bucket_bytes)
    words = model.ceil_div(local * model.PARAM_BYTES, fabric.ELEMENT_BYTES)
    padded = model.ceil_div(words, total) * total
    per = padded * (total - 1) // total
    if zero == 1:
        return (stage_01.Collective(
            "dp", "grads", group, 2 * per, "ring",
            plans.ring_allreduce(world, group, padded, chunk=total)),)
    if zero == 2:
        return (
            stage_01.Collective("dp", "grads", group, per, "gather-scatter",
                                plans.reduce_scatter(world, group, padded)),
            stage_01.Collective("dp", "params", group, per, "gather-scatter",
                                plans.allgather(world, group, padded)),
        )
    sub = plans.group_fabric(world, group)
    units = stage_04.wrap_policy(shape, sub, wrap_bytes=wrap_bytes)
    tensors = shape.tensors()
    weights = _weight_shard(axes)
    out = []
    for unit in units:
        elements = sum(tensors[index].elements for index in unit)
        unit_words = _words(elements, weights)
        unit_padded = model.ceil_div(unit_words, total) * total
        unit_per = unit_padded * (total - 1) // total
        out.append(stage_01.Collective(
            "dp", "params", group, unit_per, "gather-scatter",
            plans.allgather(world, group, unit_padded)))
        out.append(stage_01.Collective(
            "dp", "grads", group, unit_per, "gather-scatter",
            plans.reduce_scatter(world, group, unit_padded)))
    return tuple(out)


def _pipeline_axis(shape, world, group, batch, seq):
    """The pp axis's collectives: the activations and their gradients crossing
    every stage boundary, one sendrecv per micro-batch per boundary.

    A micro-batch's activation is the rank's `seq * hidden` elements (one
    sample's residual stream) and its gradient is the same buffer coming back,
    so a boundary costs `2 * batch * (pp - 1)` sendrecvs of that length, which is
    the exchange stage 6's schedule shows: every micro-batch's forward crosses
    the boundary once and its backward crosses back once.
    """
    tokens = seq * shape.hidden
    out = []
    for _ in range(batch):
        for stage in range(len(group) - 1):
            upstream, downstream = group[stage], group[stage + 1]
            out.append(stage_01.Collective(
                "pp", "activations", (upstream, downstream), tokens, "p2p",
                plans.sendrecv(world, upstream, downstream, tokens)))
            out.append(stage_01.Collective(
                "pp", "grads", (upstream, downstream), tokens, "p2p",
                plans.sendrecv(world, downstream, upstream, tokens)))
    return tuple(out)


def _compute_ticks(shape, *, batch, seq):
    """The step's compute: the whole step's arithmetic, on every rank.

    Stage 2 owns this number — `ComputeModel.compute_ticks` over the step — and
    it does not move with the split: the axes' collectives run *beside* the
    arithmetic, which is exactly why the step's price is stage 1's
    `max(compute, comms)` and never their sum. A configuration therefore buys
    what a split is for — the ledger's bytes per rank — and pays for it in
    communication; `(1, 1, 1, 1, 1)` costs the single-device reference's ticks,
    with no collective at all.
    """
    return _COMPUTE.compute_ticks(shape, batch=batch, seq=seq)


def _plan(shape, world, axes, *, zero, batch, seq, bucket_bytes, wrap_bytes):
    """One configuration's `StepPlan`: the axes' collectives in the tuple's own
    order, each axis larger than one contributing its own, plus the step's
    compute and the ledger.

    An axis of one contributes nothing at all — no collective and no ledger
    shard — which is why `(1, 1, 1, 1, 1)` is the single-device reference.
    """
    dp, tp, pp, ep, cp = axes
    groups = _groups(world, axes)
    collectives = []
    if dp > 1:
        collectives.extend(_data_parallel_axis(
            shape, world, axes, groups["dp"], zero=zero,
            bucket_bytes=bucket_bytes, wrap_bytes=wrap_bytes))
    if tp > 1:
        sub = plans.group_fabric(world, groups["tp"])
        collectives.extend(stage_05.tensor_parallel(
            shape, sub, group=sub.ranks, batch=batch, seq=seq).collectives)
    if pp > 1:
        collectives.extend(_pipeline_axis(shape, world, groups["pp"], batch, seq))
    if ep > 1:
        sub = plans.group_fabric(world, groups["ep"])
        collectives.extend(stage_08.expert_parallel(
            shape, sub, batch=batch, seq=seq).collectives)
    if cp > 1:
        sub = plans.group_fabric(world, groups["cp"])
        collectives.extend(stage_09.context_parallel(
            shape, sub, batch=batch, seq=seq, split=cp).collectives)
    return stage_01.StepPlan(
        collectives=tuple(collectives),
        compute=_compute_ticks(shape, batch=batch, seq=seq),
        memory=_ledger(shape, world, axes, zero=zero, batch=batch, seq=seq))


def _offender(axes, zero, what):
    """The axis that shards least of the kind that overflowed: the one to grow.

    For the overflowed kind, the axes that divide it are subtracted from the
    axes larger than one and the largest of what is left is named; when every
    axis shards it, the largest axis of all is named, because that is the one to
    shrink.
    """
    sizes = dict(zip(AXIS_ORDER, axes))
    if what == "activations":
        sharders = {"pp", "cp"}
    elif what == "kv":
        sharders = {"cp"}
    else:
        sharders = {"tp", "pp", "ep"}
        if what == "params":
            sharders = sharders | ({"dp"} if zero == 3 else set())
        elif what == "gradients":
            sharders = sharders | ({"dp"} if zero >= 2 else set())
        else:
            sharders = sharders | ({"dp"} if zero >= 1 else set())
    candidates = [name for name in AXIS_ORDER
                  if sizes[name] > 1 and name not in sharders]
    if not candidates:
        candidates = [name for name in AXIS_ORDER if sizes[name] > 1]
    if not candidates:
        candidates = ["dp"]
    return max(candidates, key=lambda name: (sizes[name], AXIS_ORDER.index(name)))


def _refusal(world, axes, plan, memory_budget, zero):
    """The message of a configuration that cannot fit, naming the axis, the
    bytes it wants and the budget it has."""
    largest = plan.memory[0]
    for line in plan.memory:
        if line.bytes > largest.bytes:
            largest = line
    used = _memory_of(plan)
    offender = _offender(axes, zero, largest.what)
    return ("the configuration %r on %s holds %d bytes per rank, more than "
            "memory_budget=%d: the %s line alone wants %d bytes and the %s axis "
            "(%d) shards least of it"
            % (axes, world, used, memory_budget, largest.what, largest.bytes,
               offender, dict(zip(AXIS_ORDER, axes))[offender]))


def _checked_axes(axes, gpus):
    """A requested split, as a tuple of five positive ints multiplying to
    `gpus`, or the refusal naming what is wrong with it."""
    if not isinstance(axes, tuple) or len(axes) != len(AXIS_ORDER):
        raise model.ModelError(
            "axes=%r is not a %d-tuple of axis sizes (dp, tp, pp, ep, cp)"
            % (axes, len(AXIS_ORDER)))
    for name, value in zip(AXIS_ORDER, axes):
        _positive(value, name)
    product = 1
    for value in axes:
        product *= value
    if product != gpus:
        raise model.ModelError(
            "axes=%r multiplies to %d, not the %d devices asked for: the axes "
            "partition the devices" % (axes, product, gpus))
    return axes


def configure(shape, world, *, gpus, memory_budget=DEFAULT_MEMORY_BUDGET,
              axes=None, zero=0, batch=1, seq=1,
              bucket_bytes=DEFAULT_BUCKET_BYTES, wrap_bytes=None):
    """The configuration for `gpus` devices, as `(axes, plan)`.

    `axes` is the chosen `(dp, tp, pp, ep, cp)` and `plan` is that split's
    `StepPlan`: the axes' collectives (stage 2 or 3 or 4 for the dp axis, 5 for
    tp, 6's schedule's sends for pp, 8 for ep, 9 for cp), laid over the
    rank ids the world has, priced by stage 1. When `axes` is given it is the
    split that is built and priced; otherwise every split of `gpus` is built,
    the ones whose axes refuse (a ring that cannot hold the group, an ep that is
    not the expert count, a cp the sequence does not divide) and the ones that
    cannot fit `memory_budget` are dropped, and the cheapest remaining split —
    the argmin of stage 1's `step_ticks`, ties going to the lexicographically
    first tuple — is the answer.

    `gpus` must be the number of ranks the world has: the axes partition the
    devices they are given. `zero` is the dp axis's rung of the ZeRO ladder (0
    plain data parallel, 1 ZeRO-1, 2 ZeRO-2, 3 FSDP), `batch` and `seq` size the
    step, `bucket_bytes` is stage 2's gradient bucket and `wrap_bytes` stage 4's
    wrap unit (one transformer layer by default). A split that cannot fit is
    refused with a `model.ModelError` naming the axis, the bytes it wants and
    the budget; when no split fits, the same refusal names the smallest one.
    """
    _require_shape(shape)
    _require_world(world)
    _positive(gpus, "gpus")
    _non_negative(memory_budget, "memory_budget")
    _positive(batch, "batch")
    _positive(seq, "seq")
    if zero not in ZERO_MODES:
        raise model.ModelError(
            "zero=%r is not one of %r: the dp axis shards the optimizer state "
            "(1), the gradients too (2), or the parameters too (3)"
            % (zero, ZERO_MODES))
    _positive(bucket_bytes, "bucket_bytes")
    if wrap_bytes is None:
        wrap_bytes = _default_wrap_bytes(shape)
    _positive(wrap_bytes, "wrap_bytes")
    if len(world.ranks) != gpus:
        raise model.ModelError(
            "gpus=%d names %d devices, but %s has %d ranks: the axes partition "
            "the devices they are given"
            % (gpus, gpus, world, len(world.ranks)))
    if axes is not None:
        chosen = _checked_axes(axes, gpus)
        plan = _plan(shape, world, chosen, zero=zero, batch=batch, seq=seq,
                     bucket_bytes=bucket_bytes, wrap_bytes=wrap_bytes)
        if _memory_of(plan) > memory_budget:
            raise model.ModelError(
                _refusal(world, chosen, plan, memory_budget, zero))
        return (chosen, plan)
    best = None
    smallest = None
    for candidate in _factorizations(gpus):
        try:
            plan = _plan(shape, world, candidate, zero=zero, batch=batch,
                         seq=seq, bucket_bytes=bucket_bytes,
                         wrap_bytes=wrap_bytes)
        except fabric.FabricError:
            continue
        except model.ModelError:
            continue
        if smallest is None or _memory_of(plan) < smallest[0]:
            smallest = (_memory_of(plan), candidate, plan)
        if _memory_of(plan) > memory_budget:
            continue
        ticks = stage_01.step_ticks(world, plan)
        if best is None or ticks < best[0]:
            best = (ticks, candidate, plan)
    if best is None:
        if smallest is None:
            raise model.ModelError(
                "no split of %d devices can be built on %s: every axis refuses "
                "its own group" % (gpus, world))
        raise model.ModelError(
            "no split of %d devices fits memory_budget=%d on %s: the smallest "
            "is %r at %d bytes per rank"
            % (gpus, memory_budget, world, smallest[1], smallest[0]))
    return (best[1], best[2])


def report(shape, world, plan):
    """Every number of one plan, derived from the plan and nothing else.

    `step_ticks` is stage 1's own answer for the plan; `compute` is the plan's
    own compute; `comms` is the sum of the plan's collectives' ticks;
    `bytes_per_rank` is stage 1's own per-rank byte count; and `memory_by_rank`
    maps each kind of state to the bytes per rank the plan's ledger gives it. A
    configuration never declares a number here: `plan` is the only input, so the
    report of a plan that moves nothing says nothing was moved, and the report
    of a plan built twice is the same report.
    """
    _require_shape(shape)
    _require_world(world)
    if not isinstance(plan, stage_01.StepPlan):
        raise model.ModelError(
            "plan=%r is not the StepPlan stage 1 froze" % (plan,))
    comms = 0
    for collective in plan.collectives:
        comms += stage_01.plan_ticks(world, collective.plan)
    memory_by_rank = {}
    for line in plan.memory:
        memory_by_rank[line.what] = memory_by_rank.get(line.what, 0) + line.bytes
    return {
        "step_ticks": stage_01.step_ticks(world, plan),
        "compute": plan.compute,
        "comms": comms,
        "bytes_per_rank": stage_01.plan_bytes(plan),
        "memory_by_rank": memory_by_rank,
    }
