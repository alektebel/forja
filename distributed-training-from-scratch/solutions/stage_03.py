"""Distributed Training From Scratch — stage 3: ZeRO-1 / ZeRO-2 (implementation).

The reasoning — the sharding ladder, the ledger's ceiling, the remainder rule
and the two plans — lives in the template's docstring (`stage_03.py`); this
file is only the body. Every figure is derived from the shape and the plan:
no byte count here is declared.
"""

import fabric
import model
import plans
import stage_01


#: The training state a rank holds, as a rate per parameter, in the frozen
#: ledger order: the bf16 parameters and their gradients (2 bytes each), the
#: fp32 master weights (4) and the two fp32 Adam moments (8) — sixteen bytes
#: per parameter held whole.
_STATE = (
    ("params", model.PARAM_BYTES),
    ("gradients", model.PARAM_BYTES),
    ("masters", model.MASTER_BYTES),
    ("optimizer", model.OPTIMIZER_BYTES),
)

#: `_SHARDED[stage]`: the kinds a ZeRO stage divides over its group. ZeRO-1
#: divides the 12 bytes of optimizer state (the master weights with the two
#: moments) and replicates the rest; ZeRO-2 divides the gradients as well. The
#: parameters are never divided here — that is ZeRO-3 (stage 4).
_SHARDED = (
    (),
    ("masters", "optimizer"),
    ("gradients", "masters", "optimizer"),
)

#: The two stages a ZeRO plan may be.
_STAGES = (1, 2)


def shard_partition(total_bytes, ranks):
    """The per-rank shards of a `total_bytes`-byte state, one entry per rank.

    Every rank takes `total_bytes // ranks`, and the `total_bytes % ranks`
    bytes left over are handed out one byte at a time to the first ranks, so
    the shares differ by at most one and their sum is the state, exactly. A
    rank count below one and a negative or non-int byte count are refused
    (`model.ModelError`), naming the offender.
    """
    if (isinstance(total_bytes, bool) or not isinstance(total_bytes, int)
            or total_bytes < 0):
        raise model.ModelError(
            "total_bytes=%r is not a non-negative int: a state has no negative "
            "bytes and no fractional ones" % (total_bytes,))
    if isinstance(ranks, bool) or not isinstance(ranks, int) or ranks < 1:
        raise model.ModelError("ranks=%r is not a positive int" % (ranks,))
    base, extra = divmod(total_bytes, ranks)
    return tuple(base + 1 if index < extra else base for index in range(ranks))


def assemble(shards):
    """The whole state a partition of per-rank shards adds up to.

    `shards` is what `shard_partition` answered — one byte count per rank, in
    rank order — and the state is their sum, however the state was cut. A
    shard that is negative or not an int, an empty partition, and anything
    that is not a tuple are refused (`model.ModelError`), naming the offender.
    """
    if not isinstance(shards, tuple):
        raise model.ModelError(
            "shards=%r is not a tuple of per-rank byte counts" % (shards,))
    if not shards:
        raise model.ModelError(
            "shards=%r is empty: a state is reassembled from at least one "
            "shard" % (shards,))
    total = 0
    for shard in shards:
        if isinstance(shard, bool) or not isinstance(shard, int) or shard < 0:
            raise model.ModelError(
                "shard=%r is not a non-negative int: a partition never holds a "
                "negative or fractional shard" % (shard,))
        total += shard
    return total


def _ledger(shape, group, stage):
    """The state each rank of `group` holds, one line per kind, largest share.

    A replicated kind is the whole rate times the parameter count; a sharded
    kind is the ceiling of the rate over the group, which is the first shard
    `shard_partition` hands out — the rank with the most of that kind.
    """
    total = shape.params()
    sharded = _SHARDED[stage]
    lines = []
    for what, rate in _STATE:
        if what in sharded:
            size = model.ceil_div(rate * total, len(group))
        else:
            size = rate * total
        lines.append(stage_01.MemoryLine(what, group, size))
    return tuple(lines)


def _require(shape, world, stage):
    """The stage's own arguments, or the refusal naming the offender."""
    if isinstance(stage, bool) or not isinstance(stage, int) or stage not in _STAGES:
        raise model.ModelError(
            "stage=%r is not one of %r: ZeRO-1 shards the optimizer state, "
            "ZeRO-2 the gradients as well, and ZeRO-3 (stage 4) the "
            "parameters" % (stage, _STAGES))
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    if not isinstance(world, fabric.Topology):
        raise fabric.FabricError("world=%r is not a fabric.Topology" % (world,))


def zero(shape, world, *, stage, group=None):
    """A ZeRO step as a `StepPlan`: its collectives, its compute and its ledger.

    `stage` is 1 (the optimizer state is sharded) or 2 (the gradients too), and
    `group` defaults to the whole world. The ledger has one line per kind —
    `params`, `gradients`, `masters`, `optimizer` — the sharded kinds divided
    over the group (the ceiling, the largest shard) and the replicated kinds
    whole. The collectives are the gradient all-reduce (stage 1), or the
    gradient reduce-scatter and the parameter all-gather (stage 2); a group of
    one issues none. A stage that is not 1 or 2, a shape that is not a
    `ModelShape` and a world that is not a fabric are refused, naming the
    offender, as are a group `plans.py` cannot serve and a length it cannot
    chunk.
    """
    _require(shape, world, stage)
    if group is None:
        group = world.ranks
    members = plans.group_ranks(world, group)
    memory = _ledger(shape, members, stage)
    if len(members) == 1:
        return stage_01.StepPlan(collectives=(), compute=0, memory=memory)
    # The buffer a collective moves, in whole ELEMENT_BYTES words: the bf16
    # gradient and the bf16 parameter are the same size, one per parameter.
    words = model.ceil_div(shape.params() * model.PARAM_BYTES, fabric.ELEMENT_BYTES)
    total = len(members)
    per_rank = words * (total - 1) // total
    if stage == 1:
        collectives = (stage_01.Collective(
            "dp", "grads", members, 2 * per_rank, "ring",
            plans.ring_allreduce(world, members, words, chunk=total)),)
    else:
        collectives = (
            stage_01.Collective(
                "dp", "grads", members, per_rank, "gather-scatter",
                plans.reduce_scatter(world, members, words)),
            stage_01.Collective(
                "dp", "params", members, per_rank, "gather-scatter",
                plans.allgather(world, members, words)),
        )
    return stage_01.StepPlan(collectives=collectives, compute=0, memory=memory)
