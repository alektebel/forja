"""Distributed Training From Scratch — stage 9: Sequence / context parallel

When a sequence is too long for one device, context parallel splits it across a
group: rank `b` owns positions `b * seq / split .. (b + 1) * seq / split - 1`,
carries the query, key and value of those positions, and attends its queries
against *every* key in the sequence. A rank cannot hold every key, so the key
and value blocks — the KV blocks — travel the group's **ring**, one hop at a
time, and each rank folds the block it receives into an accumulator. `seq/split`
grows with the sequence, so the attention a rank computes grows with it, but the
KV a rank must keep at once is one block, not the whole sequence.

This stage is the two halves of that idea. `online_attention(blocks)` is the
accumulation: given the blocks a rank has seen, in the order it saw them, return
the exact `(numerator, denominator)` pair `model.reference_attention` returns for
the whole sequence — **for every split**, one block or four, equal blocks or
unequal. `context_parallel(shape, world, *, batch, seq, split)` is the price:
the KV blocks rotating the ring, wrapped as a `StepPlan` (stage 1) whose
collective is the `plans.py` all-gather that walks them hop by hop.

DESIGN DECISION — why is the accumulator an exact pair of integers, and why does
the reference reduce it to lowest terms?
    A normalized softmax would be a float, and a float is not the same number on
    two machines; the whole course is exact integers for exactly this reason.
    The pair `(sum of 2**s * v, sum of 2**s)` is the *unnormalized* attention,
    and because a common factor cancels in the ratio, its lowest-terms form is
    independent of how the sum was cut up. `reference_attention` reduces by
    `gcd`, so one block, two blocks or four blocks of the same sequence return
    the *identical* pair, and a student can compare ints with `==`.

DESIGN DECISION — why must the running pivot only *drop*, and why do both parts
shift with it?
    A weight is `2 ** (score - pivot)`, held as an integer, so the pivot must be
    no larger than every score seen or the weight is a fraction — which an `int`
    accumulator cannot hold. The pivot therefore starts at the first block's
    lowest score and only ever falls, and when a later block is lower, `num` and
    `den` are both shifted left by the difference of the pivots before the block
    is folded in (`num <<= old - new`, `den <<= old - new`). Shifting only the
    numerator multiplies the ratio by a power of two and silently changes the
    answer, which is the mistake this stage exists to catch. This is the
    flash-attention max-rescale written so the weights stay whole numbers.

DESIGN DECISION — why does a rank keep its query block and stream the KV blocks,
rather than recompute each block on its own?
    Context parallel fixes each rank's queries and moves the keys to them, so the
    accumulator must survive between blocks: block `b`'s contribution is added to
    what blocks `0 .. b-1` left behind, and the running pivot makes the addition
    exact. Recomputing a block in isolation — resetting the accumulator, or
    keeping only the block just seen — throws away every earlier block's
    contribution and returns a pair no split of the sequence agrees with.

DESIGN DECISION — why do the KV blocks travel an all-gather ring, and why does
the per-hop length count the heads and the head dimension?
    Every rank needs every block, and the ring does that in `split - 1` steps:
    each step every rank forwards one block to its successor, so after `split - 1`
    steps the blocks have visited every rank exactly once. That is `plans.py`'s
    `allgather`, and pricing it with stage 1 charges the real hop. The block a
    rank sends is the key and the value of its positions: `2 * (seq / split) *
    heads * head_dim` elements per batch sample. A length that ignores the heads
    or the head dimension prices one scalar per position and undercounts the
    traffic by the width of the model; a plan that charges nothing has pretended
    the blocks never moved.

DESIGN DECISION — why must the split divide the sequence, and why is the group
the first `split` ranks?
    The ring this stage prices is even: every rank owns the same `seq / split`
    positions, so its block is the same length and the exchange is symmetric. A
    `split` that does not divide `seq` would need a ragged ring with per-rank
    lengths, which is the uneven-exchange exercise of stage 8 and not this one —
    it is refused, naming `seq` and `split`. The group is the ranks that own
    blocks, so a `split` of one is the empty plan of one rank and costs no comms
    at all, exactly as an axis of one does everywhere in the course.

DESIGN DECISION — why does the step charge no compute?
    The step this stage returns is the KV exchange, and the quantity the course
    compares across axes is what crosses the fabric — the ring's hops and the
    bytes on them. The attention arithmetic a rank runs beside that exchange is
    a function of the sequence and the model, not of the ring's schedule, so it
    is added once when the axes are composed in stage 10's report and not
    double-charged here. `compute` is therefore 0 and `step_ticks` reads the
    comms alone, exactly as an axis of one with no collectives costs nothing.

TODO: implement `online_attention` and `context_parallel`.
"""

import model
import plans
import stage_01


def online_attention(blocks):
    """The exact `(numerator, denominator)` pair the whole sequence's attention
    accumulates, from the blocks a rank has seen.

    `blocks` is a non-empty tuple of blocks; a block is a `(q_block, k_block,
    v_block)` triple of equal-length non-empty tuples of ints, the key and value
    of that stretch of the sequence and the queries that attend them. Flattened
    in order the blocks give the whole sequences `q`, `k` and `v`, and the answer
    must be `model.reference_attention(q, k, v)` — the same ints — whatever the
    split is. The accumulation is block by block with a running pivot: the
    weights are `2 ** (score - pivot)` and both `num` and `den` shift by the
    difference when the pivot drops. A malformed block is refused with a
    `model.ModelError` naming the offender.
    """
    raise NotImplementedError("stage 9: implement online_attention()")


def context_parallel(shape, world, *, batch, seq, split):
    """The `StepPlan` of the KV blocks travelling the ring, priced by stage 1.

    The sequence is cut into `split` equal blocks over the first `split` ranks;
    `plans.allgather` walks the key and value blocks around the ring in `split -
    1` steps, one block per rank per step, and the collective's length is the
    elements a rank moves in all, `(split - 1) * block`. A `split` the sequence
    does not divide, a `split` larger than the world, a non-positive `batch`,
    `seq` or `split`, and a `shape` that is not a `ModelShape` are refused with a
    `model.ModelError` naming the offender; a `split` of one is the empty plan.
    """
    raise NotImplementedError("stage 9: implement context_parallel()")
