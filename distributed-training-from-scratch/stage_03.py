"""Distributed Training From Scratch — stage 3: ZeRO-1 / ZeRO-2

Stage 2's data-parallel step replicates the whole training state on every rank
and pays sixteen bytes per parameter for it. This stage shards that state
instead — the optimizer state first, then the gradients — without touching the
arithmetic: the gradient a step reduces still sums to
`model.reference_gradients`, and the shards a step cuts still reassemble to the
exact state the single-device reference holds.

The mechanism is one ladder and one rule. The ladder is the per-parameter rate
table: bf16 `params` (2 bytes), bf16 `gradients` (2), and the 12 bytes of
optimizer state — the fp32 master weights (4) and the two Adam moments (8).
ZeRO-1 divides the twelve over the group and replicates the rest (`4 + 12/N`
bytes per parameter per rank); ZeRO-2 divides the gradients as well
(`2 + 2/N + 12/N`); ZeRO-3 (stage 4) divides the parameters, and so on down to
`16/N`. The rule is `shard_partition`: the state is cut into one shard per
rank, every rank takes `total // ranks` and the remainder is handed out one
byte at a time to the *first* ranks, so the shards differ by at most one and
their sum is the state. The state divides the world far less often than the
world divides itself, and that is where a ledger's bugs live.

`zero(shape, world, *, stage, group=None)` returns the step as the `StepPlan`
stage 1 froze: the collectives a ZeRO step issues, the ticks of compute it owns
(no batch, no sequence, so none — this stage prices the state) and the ledger.
The ledger reports the largest share per rank: the replicated kinds whole, the
sharded kinds as the ceiling of the rate over the group, which is exactly the
first shard `shard_partition` hands out. ZeRO-1 all-reduces the gradients, so
every rank ends with the whole gradient and can update its own shard of the
optimizer state; ZeRO-2 reduce-scatters them, so each rank holds only its own
shard — and therefore only its own slice of the parameters it just updated, so
the updated parameters must be gathered back. That all-gather is the extra
collective a `stage=2` plan issues that a `stage=1` plan does not.

DESIGN DECISION — which bytes does each ZeRO stage actually divide, and why
does the ladder have to run downward?
    The 12 bytes of optimizer state are the master weights (4) and the two Adam
    moments (8) — the state the optimizer step touches and nothing else needs.
    ZeRO-1 divides those twelve and leaves the parameters and their gradients
    replicated (`4 + 12/N`); ZeRO-2 divides the gradients too (`2 + 2/N +
    12/N`); ZeRO-3 divides the parameters as well. The rejected alternative is
    any other ordering, and its cost is a ladder that does not run downward:
    sharding the gradients at ZeRO-1 (that is ZeRO-2's saving, spent early)
    or the parameter buffers instead of the optimizer state (a half ZeRO-3)
    leaves the ledger reporting a *larger* per-rank state than the stage below
    it — and sharding can only ever move bytes down.

DESIGN DECISION — why is a rank's share the ceiling of the state over the
group, and what is the ledger hiding?
    A sharded line reports the largest share a rank holds, `ceil(rate *
    params / group)`, because the ledger answers "does this fit?" about the
    rank that holds the most — the one the run stalls on. Flooring instead
    under-reports that rank by a byte, and for a 7B model that is the
    difference between fitting and not. `shard_partition` answers the finer
    question — every rank's own count, first rank first — so the ledger's line
    is the partition's first shard, never its average: a state that divides the
    world evenly hides the difference, and a state that does not (an embedding
    of 48 parameters over five ranks) is where the ceiling shows.

DESIGN DECISION — where does the remainder of a state that the world does not
divide go, and what about the buffer the collective moves?
    The remainder is spread one byte at a time over the first ranks, so the
    shards differ by at most one and reassemble to the state exactly. Dropping
    it loses state the reassembly cannot recover; spreading it over every rank
    invents state; giving it to the last ranks sums the same but leaves the
    first rank — the one the ledger reports — a byte short. The *collective*
    is a different question: a ring moves whole `ELEMENT_BYTES` words and cuts
    the buffer one chunk per rank, so a buffer the group does not divide is
    refused by `plans.py`, naming the length; the state's bytes need not divide
    the world, and that is the whole point of `shard_partition`.

DESIGN DECISION — why does ZeRO-2 gather the parameters back when ZeRO-1 does
not have to?
    ZeRO-1's all-reduce leaves every rank holding the whole gradient, so the
    rank can form the whole update for the shard of the optimizer state it
    owns and the parameters it had whole stay whole. ZeRO-2's reduce-scatter
    leaves each rank only its own shard of the gradient, which is the 2/N it
    was bought for, and each rank therefore updates only its own shard of the
    parameter — the next forward needs all of them, so the parameters are
    all-gathered back (`2P(N-1)/N` bytes per rank, transient, which is why the
    ledger still reports the parameters whole). The rejected alternative — a
    `stage=2` plan that only swaps the ledger — saves the gradient's memory and
    leaves the rank holding 1/N of the parameters with nothing that moves the
    rest back: the model would train a different model on every rank.

DESIGN DECISION — why does a group of one issue no collective at all?
    Every collective over a single rank is the empty plan — nothing has to
    move — and `plans.py` says so. Charging the axis anyway would price a
    transfer the fabric cannot need, and would make a "one GPU" configuration
    cost something; the stage's answer must be the single-device reference
    instead: sixteen bytes per parameter, no comms, no ticks. It is also the
    only group size where both stages' ledgers agree, which is the sanity check
    every later stage's `dp=1`/`tp=1` axis is built on.

TODO: implement `shard_partition`, `assemble` and `zero`.
"""

import fabric
import model
import plans
import stage_01


def shard_partition(total_bytes, ranks):
    """The per-rank shards of a `total_bytes`-byte state, one entry per rank.

    Every rank takes `total_bytes // ranks`, and the `total_bytes % ranks`
    bytes left over are handed out one byte at a time to the first ranks, so
    the shares differ by at most one and their sum is the state, exactly. A
    rank count below one and a negative or non-int byte count are refused
    (`model.ModelError`), naming the offender.
    """
    raise NotImplementedError("stage 3: implement shard_partition()")


def assemble(shards):
    """The whole state a partition of per-rank shards adds up to.

    `shards` is what `shard_partition` answered — one byte count per rank, in
    rank order — and the state is their sum, however the state was cut. A
    shard that is negative or not an int, an empty partition, and anything
    that is not a tuple are refused (`model.ModelError`), naming the offender.
    """
    raise NotImplementedError("stage 3: implement assemble()")


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
    raise NotImplementedError("stage 3: implement zero()")
