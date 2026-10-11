"""Distributed Training From Scratch — stage 4: ZeRO-3 / FSDP (implementation).

The reasoning — the wrap unit, the layer-granular budget, the two collectives a
unit pays and the peak — lives in the template's docstring (`stage_04.py`);
this file is only the body. Every figure is derived from the shape and the plan:
the bytes are the plan's own collectives read back, the peak is the plan's own
lifetimes, and nothing here is measured.
"""

import fabric
import model
import plans
import stage_01


#: The resident state a rank of a fully sharded step holds, as a rate per
#: parameter, in the frozen ledger order: the bf16 parameters and their
#: gradients (2 bytes each), the fp32 master weights (4) and the two fp32 Adam
#: moments (8). ZeRO-3 divides every one of the sixteen bytes over the group, so
#: the ledger reports the shard and never the whole state.
_STATE = (
    ("params", model.PARAM_BYTES),
    ("gradients", model.PARAM_BYTES),
    ("masters", model.MASTER_BYTES),
    ("optimizer", model.OPTIMIZER_BYTES),
)


def _require_count(value, what):
    """A positive whole count, or the refusal naming it."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise model.ModelError("%s=%r is not a positive int" % (what, value))
    return value


def _require_shape(shape):
    """The model's shape, or the refusal naming it."""
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))


def _require_world(world):
    """The fabric, or the refusal naming it."""
    if not isinstance(world, fabric.Topology):
        raise fabric.FabricError("world=%r is not a fabric.Topology" % (world,))


def _module_of(name):
    """The module a tensor belongs to: `layer.7.ffn.w1` is the module `layer.7`.

    Every other tensor is its own module, named by the one prefix it has:
    `embed`, `norm`, `unembed`.
    """
    parts = name.split(".")
    if parts[0] == "layer" and len(parts) > 1:
        return "layer." + parts[1]
    return parts[0]


def _groups(shape):
    """`shape.tensors()` cut into the modules a wrap unit is made of.

    One group per module, in the frozen tensor order: the leading embedding, one
    per transformer layer (that layer's own tensors), and the trailing norm
    (with the head's own unembed, when the shape does not tie it). A group is
    never cut — half a layer is not a unit — so the groups are the atoms the
    budget only ever puts *together*.
    """
    groups = []
    current = None
    for index, tensor in enumerate(shape.tensors()):
        module = _module_of(tensor.name)
        if current is None or current[0] != module:
            current = (module, [])
            groups.append(current)
        current[1].append(index)
    return tuple((module, tuple(indices)) for module, indices in groups)


def _group_bytes(tensors, indices):
    """The bf16 bytes of a group's parameters: what a gather of it materializes."""
    return model.PARAM_BYTES * sum(tensors[index].elements for index in indices)


def wrap_policy(shape, world, *, wrap_bytes):
    """The wrap units of `shape`, as tuples of indices into `shape.tensors()`.

    The model's modules — the embedding, each transformer layer, the trailing
    norm — are the atoms, and the units are maximal runs of consecutive atoms
    whose parameters fit `wrap_bytes` together. A unit therefore never mixes two
    layers, and never splits one. The refusal is a `wrap_bytes` smaller than one
    layer; the units are one per module when the budget holds one layer and one
    for the whole model when it holds everything, and every figure of the
    neighbouring stages is a function of this answer.
    """
    _require_shape(shape)
    _require_world(world)
    _require_count(wrap_bytes, "wrap_bytes")
    tensors = shape.tensors()
    groups = _groups(shape)
    for module, indices in groups:
        if not module.startswith("layer."):
            continue
        size = _group_bytes(tensors, indices)
        if size > wrap_bytes:
            raise model.ModelError(
                "%s holds %d parameters, %d bytes at %d per parameter, more "
                "than wrap_bytes=%r: a wrap unit holds a whole layer and never "
                "splits one" % (module,
                                sum(tensors[index].elements for index in indices),
                                size, model.PARAM_BYTES, wrap_bytes))
    units = []
    current = []
    size = 0
    for module, indices in groups:
        group_size = _group_bytes(tensors, indices)
        if current and size + group_size > wrap_bytes:
            units.append(tuple(current))
            current = []
            size = 0
        current.extend(indices)
        size += group_size
    if current:
        units.append(tuple(current))
    return tuple(units)


def _ledger(shape, group, batch, seq):
    """The state each rank of `group` holds, one line per kind, largest share.

    Every kind of state is divided over the group — that is what "fully
    sharded" means — so a line is the ceiling of the rate over the group's size,
    which is the first shard `stage_03.shard_partition` hands out. The
    activations are not state the group divides: each rank holds the ones of the
    batch and sequence it was given, and they are resident across the whole step.
    """
    total = shape.params()
    lines = []
    for what, rate in _STATE:
        lines.append(stage_01.MemoryLine(
            what, group, model.ceil_div(rate * total, len(group))))
    lines.append(stage_01.MemoryLine(
        "activations", group, shape.activation_bytes(batch, seq)))
    return tuple(lines)


def fully_sharded(shape, world, *, wrap_bytes, batch=1, seq=1):
    """A ZeRO-3 (FSDP) step as a `StepPlan`: its collectives, compute and ledger.

    One wrap unit at a time: the unit's parameters are all-gathered before its
    compute and its gradients are reduce-scattered after, so the whole model is
    never resident on any rank — the plan is `2 x units` collectives, each
    moving its own unit's buffer and never the model's. The step owns no compute
    ticks (this stage prices the state and what crosses the fabric, not the
    arithmetic the gathered parameters enable), and its ledger is the shard of
    every kind of state plus the activations. A group of one issues no
    collective at all: it is already holding every shard.

    `batch` and `seq` price the activations the ledger reports and change no
    collective; they are one token each by default, the smallest batch the
    accounting can name.
    """
    _require_shape(shape)
    _require_world(world)
    _require_count(batch, "batch")
    _require_count(seq, "seq")
    units = wrap_policy(shape, world, wrap_bytes=wrap_bytes)
    members = plans.group_ranks(world, world.ranks)
    tensors = shape.tensors()
    memory = _ledger(shape, members, batch, seq)
    total = len(members)
    collectives = []
    if total > 1:
        for unit in units:
            elements = sum(tensors[index].elements for index in unit)
            words = model.ceil_div(elements * model.PARAM_BYTES,
                                   fabric.ELEMENT_BYTES)
            per_rank = words * (total - 1) // total
            collectives.append(stage_01.Collective(
                "dp", "params", members, per_rank, "gather-scatter",
                plans.allgather(world, members, words)))
            collectives.append(stage_01.Collective(
                "dp", "grads", members, per_rank, "gather-scatter",
                plans.reduce_scatter(world, members, words)))
    return stage_01.StepPlan(collectives=tuple(collectives), compute=0,
                             memory=memory)


def _buffer_bytes(collective):
    """The whole buffer a collective is issued over, in bytes.

    A ring collective cuts its buffer into one chunk per rank, so the buffer is
    the farthest byte any of the plan's own transfers reaches: the maximum of
    `offset + length` over them, times the element size. Read off the plan and
    never declared: a unit's gathered parameters are the whole unit, however
    many bytes per rank the collective happened to move.
    """
    transfers = collective.plan.transfers
    if not transfers:
        return 0
    elements = max(transfer.offset + transfer.length for transfer in transfers)
    return fabric.ELEMENT_BYTES * elements


def in_flight(plan):
    """The bytes resident at the peak of the step, from the plan's own lifetimes.

    The plan's ledger is resident for the whole step: every kind of state and
    the activations. Over it, the step issues its collectives one at a time —
    one wrap unit's buffer at a time, never the model's — and a collective's
    buffer is resident from the moment it is issued until the next collective
    is: the gathered parameters are freed when the unit's gradients are
    reduce-scattered, and that unit's gradients when the next unit's parameters
    are gathered. The peak is the largest sum of live buffers over the step,
    added to the resident ledger.
    """
    if not isinstance(plan, stage_01.StepPlan):
        raise model.ModelError(
            "plan=%r is not the StepPlan stage 1 froze" % (plan,))
    resident = 0
    for line in plan.memory:
        resident += line.bytes
    peak = resident
    live = []
    for index, collective in enumerate(plan.collectives):
        live = [entry for entry in live if entry[0] > index]
        live.append((index + 1, _buffer_bytes(collective)))
        peak = max(peak, resident + sum(entry[1] for entry in live))
    return peak
