"""Transformer Inference Physics — stage 8: The crossover: where decode
stops being memory-bound.

TODO: implement each function; the docstring is the contract.

The mlp is the floppiest op in the stack and the first to leave the
memory-bound regime as the batch grows: its flops scale with the batch
while its weight read does not, so there is exactly one batch where its
compute branch overtakes its memory branch — the crossover. Below it,
adding a sequence is nearly free in per-token time; above it, the
compute side starts pinning the step and the curve bends. The curve
itself is the step's wall time over the world's batch ladder, and the
kink lands where this stage says.

DESIGN DECISION — the crossover solved by trial to 512, not by algebra?
Because the floor divisions that price every op do not invert cleanly:
solving `b * t_c > t_m` for b in integers recomputes the rounding the
check would have to divine. The honest way in an exact course is to
walk the ladder the curve walks and answer the first batch that flips —
and `0` when none does, because a lie about a crossover is worse than
an honest "never, this small".

DESIGN DECISION — why the mlp alone and not the whole phase?
Because the phase's verdict flips last, after every op has crossed, and
by then the "crossover" is a kink in a sum nobody priced. The mlp
carries the most flops per byte of the weight ops and is the standard
rule of thumb on real boxes: batch ~256 for fp16 stack/array ratios of
this class. One op, one law, one number.

DESIGN DECISION — the curve prices the step's total, not per-token?
Because the wall clock is what a serving plan buys with: total/batch is
one division the caller does on its own terms. The curve's shape — near
flat below the crossover, rising faster above — is the total's shape,
and comparing it against the trace's own kink needs no second opinion."""


import devices

import trace

import stage_01 as s1

import stage_04 as s4

import stage_06 as s6

def crossover_batch(config, device, dtype):
    """The smallest batch whose mlp op is compute-bound; 0 when no batch
    up to the world's ladder top ever flips."""
    raise NotImplementedError("stage 8: implement crossover_batch()")

def batch_curve(config, device, dtype, ctx):
    """The step's wall total over the world's batch ladder: flat below
    the crossover, bending above it."""
    raise NotImplementedError("stage 8: implement batch_curve()")
