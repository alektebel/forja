"""Transformer Inference Physics — stage 6: Decode: ITL's model.

One generated token per sequence per step: the weights are read once
however large the batch — the amortization every serving trade is built
on — and each sequence pays its own cache read, grown by the step
before. The verdict flips the stage 5's: a decode is memory-bound by a
hundred-fold at real sizes, the flops idle while the HBM streams, and
the step's total is the ITL the profiler's own number will meet.

DESIGN DECISION — why refuse a context below one?
Because decoding with an empty cache violates what decode is in this
world, and the op table's attention line prices the cache read plus the
token's own store `(ctx + 1)`, so `ctx = 0` would cost in bytes what it
cannot cost. The refusal saves the exactness of the row that named the
mistake instead of a plausible zero that poisoned it.

DESIGN DECISION — the step's ITL for a batch of one is the total?
Because the wall clock does not divide by nothing: one sequence, one
token, one step, and the step's time is the time between tokens. Larger
batches share the weights' read across more tokens; the per-token price
is `total / batch`, and the crossover of that — stage 8 — is where the
sharing stops paying.

DESIGN DECISION — the attention op's bytes grow by the cache read plus
the store, not the read alone?
Because the step is what writes the cache that stage 7 will bill the
next step's rent for: read `ctx` tokens' slices and append one token's
own. The op table and `bytes_decode` say the same thing two ways, and a
check asserts their sum is one number.
"""

import stage_01 as s1
import stage_04 as s4

DECODE_KEYS = ("compute_ns", "memory_ns", "launch_ns", "total", "bound")


def decode(config, device, dtype, ctx, batch):
    """The decode phase: every op of the stack for one token per
    sequence, both branch sums, the launch bill, one wall total and one
    verdict."""
    s1.validate(config)
    if ctx < 1 or batch < 1:
        raise s1.PhysError(
            "ctx=%d batch=%d: a decode step serves at least one sequence "
            "over at least one cached token" % (ctx, batch))
    ph = s4.phase_time(s4.ops_decode(config, batch, ctx, dtype),
                       device, dtype)
    return {"compute_ns": ph["compute_ns"],
            "memory_ns": ph["memory_ns"],
            "launch_ns": ph["launch_ns"],
            "total": ph["total"],
            "bound": s4.phase_bound(ph["compute_ns"], ph["memory_ns"])}
