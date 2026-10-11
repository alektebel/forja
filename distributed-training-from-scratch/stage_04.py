"""Distributed Training From Scratch — stage 4: ZeRO-3 / FSDP

Stage 3 shards everything the optimizer touches and leaves the parameters
replicated, so sixteen bytes per parameter still live on every rank and the
plan's `params` line is the whole set. This stage shards the parameters too:
each rank holds `1/N` of them, and the rest are *gathered on demand*, one wrap
unit at a time, exactly while the unit computes — then dropped. Nothing about
the arithmetic changes. The unit's parameters are the same parameters, the
gradient the reduce-scatter sums is the same gradient, and the state the shards
reassemble to is the state the single-device reference holds.

Three rules make the stage. The **wrap unit** is the granularity: a unit is a
whole module of the model — the embedding, one transformer layer, the trailing
norm — or a run of consecutive modules the budget holds together, and it is
never the whole model and never half a layer. The **budget** is `wrap_bytes`,
compared against the bf16 bytes of a layer's parameters: a budget below one
layer cannot hold a layer whole and is refused, and a module that cannot be cut
at all (the embedding, which is bigger than a layer here) is a unit of its own
however big it is. The **plan** is `2 x units` collectives: the all-gather of a
unit's parameters before its compute, the reduce-scatter of its gradients
after. A rank therefore keeps `16P/N` bytes of state resident and holds one
unit's parameters transiently — the peak — instead of the model's.

DESIGN DECISION — what is a wrap unit, and why is it never the whole model?
    The unit is the model's own module: the embedding, one transformer layer,
    the norm. FSDP gathers a unit's parameters when the unit computes and frees
    them when it is done, so the transient bytes are the unit's and the resident
    bytes are the shard — `16P/N` — for every unit. The rejected alternative is
    one unit for the whole model: it all-gathers the model's `2P` bytes before
    the first layer and keeps them, which is stage 2 with a sharded optimizer
    and no saving at all — the peak becomes the model, not the layer.

DESIGN DECISION — why does the budget refuse less than one layer, and why not
refuse the embedding?
    A unit is a whole module and a layer cannot be cut: a budget below a layer's
    bf16 bytes cannot hold a layer whole, and half a layer's parameters are not
    a unit anything can gather. The rejected alternative is to floor the budget
    and split the layer — that silently changes the model's module boundaries
    and pays two gathers where one was asked for. The embedding is different in
    kind: it is one tensor, it cannot be split at any budget, and it is a module
    of its own, so it is a unit however big it is — the budget governs what a
    unit may *contain*, not whether a single tensor exists.

DESIGN DECISION — why does every unit pay two collectives, and why not one
all-reduce per step?
    The unit's parameters are gathered (an all-gather, `2P(N-1)/N` bytes per
    rank) because the rank does not have them; the unit's gradients are summed
    and scattered (a reduce-scatter, the same bytes) because only the rank that
    owns a shard may update it. Each pass moves the unit's buffer once round the
    ring, so the two together move the model's bf16 parameter buffer twice —
    `4P(N-1)/N` bytes per rank per step, exactly ZeRO-2's traffic, because the
    same two collectives are what ZeRO-2 runs, only over the whole model at
    once. The rejected alternative is ZeRO-1's all-reduce: it also sums the
    gradients, but it leaves every gradient whole on every rank, which is the
    `2P` this stage exists to shard.

DESIGN DECISION — how is a rank's per-step figure arrived at, instead of
declared?
    Every number here is read back from the plan's own collectives: a
    collective's `length` is the elements it moves per rank in the direction
    that matters, and the buffer it is issued over is the farthest byte its own
    transfers reach (`max(offset + length)` over them, times `ELEMENT_BYTES`),
    cut one chunk per rank by the ring. So a unit's buffer is the unit's bf16
    parameters and its per-rank move is that buffer's `(N-1)/N`; the step is
    their sum, and `stage_01.plan_bytes` reads it off. The rejected alternative
    is a literal — `3P` or `4P` written into the function — which no plan can
    confirm and which stops being true the moment a unit is added, dropped or
    resized.

DESIGN DECISION — where is the peak, and why do the activations have to be in
it?
    The peak is the resident ledger plus the largest buffer in flight: the whole
    shard of every kind of state, the activations of the batch and sequence the
    rank is running, and one unit's parameters while they are gathered.
    `in_flight(plan)` takes the maximum over the step of the sum of the
    collectives' live buffers — a collective's buffer lives from the moment it
    is issued to the next collective's, so the units' buffers never overlap —
    and adds the ledger's own lines to it. The rejected alternative is the unit
    alone (or the ledger alone): the activations are resident across the whole
    step and are the term that grows with the batch, so a peak that leaves them
    out is the one a rank runs out of memory on.

TODO: implement `wrap_policy`, `fully_sharded` and `in_flight`.
"""

import fabric
import model
import plans
import stage_01


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
    raise NotImplementedError("stage 4: implement wrap_policy()")


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
    raise NotImplementedError("stage 4: implement fully_sharded()")


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
    raise NotImplementedError("stage 4: implement in_flight()")
