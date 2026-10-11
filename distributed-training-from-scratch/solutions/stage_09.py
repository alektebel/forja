"""Distributed Training From Scratch — stage 9: Sequence / context parallel
(implementation).

The reasoning behind the surface — why the accumulator is a pair of exact
integers, why its running pivot only drops and both parts shift with it, why a
rank keeps its queries and streams the KV blocks, and why those blocks travel an
all-gather ring priced per hop — is in the template, `stage_09.py`.
"""

from math import gcd

import model
import plans
import stage_01


def _blocks_of(blocks):
    """`blocks` as a tuple of `(q, k, v)` int-tuple triples of equal length, or
    a `model.ModelError` naming the malformed block."""
    if not isinstance(blocks, tuple) or not blocks:
        raise model.ModelError("blocks=%r is not a non-empty tuple" % (blocks,))
    checked = []
    for index, block in enumerate(blocks):
        if not isinstance(block, tuple) or len(block) != 3:
            raise model.ModelError(
                "blocks[%d]=%r is not a (q, k, v) triple" % (index, block))
        sides = []
        for side, name in zip(block, ("q_block", "k_block", "v_block")):
            if not isinstance(side, tuple) or not side:
                raise model.ModelError(
                    "blocks[%d]'s %s=%r is not a non-empty tuple"
                    % (index, name, side))
            row = []
            for value in side:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise model.ModelError(
                        "blocks[%d]'s %s=%r holds a non-int %r"
                        % (index, name, side, value))
                row.append(value)
            sides.append(tuple(row))
        if not (len(sides[0]) == len(sides[1]) == len(sides[2])):
            raise model.ModelError(
                "blocks[%d]=%r has q, k and v of different lengths"
                % (index, block))
        checked.append(tuple(sides))
    return tuple(checked)


def online_attention(blocks):
    """The exact `(numerator, denominator)` pair the whole sequence's attention
    accumulates, from the blocks a rank has seen.

    See the template: the queries are fixed and the key/value blocks stream; the
    running pivot only drops and both parts of the accumulator shift with it.
    """
    checked = _blocks_of(blocks)
    queries = tuple(left for q_block, _, _ in checked for left in q_block)
    pivot = None
    num = 0
    den = 0
    for _, k_block, v_block in checked:
        block_low = min(left * right for left in queries for right in k_block)
        if pivot is None or block_low < pivot:
            if pivot is not None:
                num <<= pivot - block_low
                den <<= pivot - block_low
            pivot = block_low
        for left in queries:
            for spot, right in enumerate(k_block):
                weight = 1 << (left * right - pivot)
                num += v_block[spot] * weight
                den += weight
    common = gcd(abs(num), den)
    if common > 1:
        num //= common
        den //= common
    if den < 0:
        num, den = -num, -den
    return (num, den)


def context_parallel(shape, world, *, batch, seq, split):
    """The `StepPlan` of the KV blocks travelling the ring, priced by stage 1.

    See the template: `split` equal blocks over the first `split` ranks, walked
    by `plans.allgather` in `split - 1` steps.
    """
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    for value, name in ((batch, "batch"), (seq, "seq"), (split, "split")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise model.ModelError("%s=%r is not a positive int" % (name, value))
    if split > len(world.ranks):
        raise model.ModelError(
            "split=%d is more blocks than the %d ranks of %s"
            % (split, len(world.ranks), world))
    if seq % split:
        raise model.ModelError(
            "seq=%d is not a multiple of split=%d: the sequence must divide "
            "evenly over the ring's blocks" % (seq, split))
    members = tuple(world.ranks[:split])
    block = batch * (seq // split) * shape.heads * shape.head_dim() * 2
    memory = (stage_01.MemoryLine("kv", members, block * model.ELEMENT_BYTES),)
    if split == 1:
        return stage_01.StepPlan(collectives=(), compute=0, memory=memory)
    plan = plans.allgather(world, members, split * block)
    collective = stage_01.Collective(
        "cp", "kv", members, (split - 1) * block, "ring", plan)
    return stage_01.StepPlan(collectives=(collective,), compute=0, memory=memory)
