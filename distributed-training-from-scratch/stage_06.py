"""Distributed Training From Scratch — stage 6: Pipeline parallel

A pipeline splits a model by layers: stage `s` owns a slice of the layers, and
the micro-batches flow through the stages. Nothing here talks to the fabric —
what this stage writes is a **schedule as data**: for every step and every
stage, which micro-batch is being forwarded and which is being back-propagated.
Everything the rest of the course says about a pipeline (its bubble, its memory,
its exit steps) is read off that data, never off a formula.

The data is a tuple of `Slot(step, stage, micro_batch, phase)`, where `phase` is
`"f"` for a forward and `"b"` for a backward, and it is **canonical**: sorted by
`(step, stage, phase, micro_batch)`, so two schedules that say the same thing
are equal.

DESIGN DECISION — why is a step numbered from one, and why does the forward of
micro-batch mu at stage s always sit at step `mu + s + 1`?
    Because the first stage has nothing to wait for and no stage can start a
    micro-batch before the stage above it has finished with it: micro-batch 0
    enters stage 0 at step 1, and after `p - 1` steps it reaches the last stage.
    Numbering from one makes "the last micro-batch leaves the last stage at
    `m + p - 1`" a sentence instead of an off-by-one argument, and pinning the
    forward stream is what makes the two schedules differ *only* in their
    backwards — which is exactly what they differ in.

DESIGN DECISION — why does a stage run at most one forward and one backward in
a step, and never two of either?
    One stage is one device with one set of weights: it can run one task at a
    time, and the name of the second schedule says what it does with that
    budget — one forward, one backward, of different micro-batches, in the same
    step. Two forwards in a step would need the stage to double its compute,
    and two backwards would need two sets of gradients to be applied at once;
    both are different machines, not different schedules.

DESIGN DECISION — why must a backward not share a step with the forward of its
own micro-batch?
    The backward needs that forward's activations. Putting them in the same step
    is asking a device to consume an activation in the step that produces it —
    a schedule that only works if every layer is instantaneous. This is the
    constraint the checks probe first, because it is the one a hand-written
    schedule violates most often.

DESIGN DECISION — why does GPipe's bubble survive its own backward pass, and why
is 1F1B's half of it?
    GPipe does every forward and then every backward, so no stage has a backward
    to run while the pipeline is still filling (and none has a forward to run
    once it is draining): its stages idle through a whole fill and a whole
    drain, `2p - 2` idle pairs each. 1F1B streams the backwards against the
    forwards, so a stage that has finished its part of a micro-batch's backward
    can take the next micro-batch's forward in the very next step; the same fill
    and drain are paid once and half of the pairs are saved. The formula is not
    the point — the replay is: for `(p, m) = (4, 8)` GPipe idles 24 pairs of the
    88 its makespan spends and 1F1B 12 of 60.

DESIGN DECISION — why is the bubble counted by replaying the slots, and why is
its fraction an exact pair?
    Because a formula is a claim and the slot list is the thing: replaying gives
    the makespan, the pairs that carry a task and the pairs that do not, and it
    is the only version of the number that survives a schedule someone wrote by
    hand. The fraction is `idle pairs / (stages x makespan)`, an exact rational —
    `3/11` for GPipe at `(4, 8)`, not `0.2727...` — because a course whose whole
    subject is counting does not round.

TODO: implement `gpipe`, `one_f_one_b`, `bubble`, `bubble_fraction` and `replay`.
"""

from dataclasses import dataclass
from math import gcd

import model

#: The phases a slot can carry: a forward or a backward of one micro-batch.
PHASES = ("f", "b")


@dataclass(frozen=True)
class Slot:
    """One task of one stage: the forward or the backward of one micro-batch,
    at one step. A stage can carry one `"f"` and one `"b"` in the same step."""

    step: int
    stage: int
    micro_batch: int
    phase: str


def gpipe(p, m):
    """`p` stages, `m` micro-batches: every forward, then every backward in
    reverse order. A tuple of `Slot`s, canonical.

    Refuses (`model.ModelError`, naming the offender) a count that is not a
    positive int. The backward of micro-batch `mu` at stage `s` sits at step
    `m + p + (m - 1 - mu) + (p - 1 - s)`, and the schedule must satisfy every
    dependency the module docstring lists.
    """
    raise NotImplementedError("stage 6: implement gpipe()")


def one_f_one_b(p, m):
    """`p` stages, `m` micro-batches, warm-up then a forward and a backward per
    stage per step then the cool-down: the backward stream runs against the
    forward stream, the last stage back-propagating first. A canonical tuple of
    `Slot`s, with the same refusals as `gpipe`.

    The backward of micro-batch `mu` at stage `s` sits at step
    `2p - s + mu`, which is what makes a stage's forwards and backwards share
    steps without ever sharing a micro-batch.
    """
    raise NotImplementedError("stage 6: implement one_f_one_b()")


def bubble(schedule, p):
    """The idle `(stage, step)` pairs inside the schedule's makespan: pairs that
    carry no task at all. A pair with one task is busy; a pair with two is still
    one pair.

    Refuses (`model.ModelError`, naming the offender) a schedule that is not a
    canonical tuple of `Slot`s over `p` stages, one that misses an
    `(micro_batch, stage, phase)`, one whose backward comes at or before its own
    forward, one whose forward does not follow the previous stage's, one whose
    backward does not follow the next stage's, and one that puts two tasks of
    the same phase in one step of one stage.
    """
    raise NotImplementedError("stage 6: implement bubble()")


def bubble_fraction(p, m, *, schedule):
    """The bubble over the `(stage, step)` pairs the makespan spends, as an
    exact pair `(idle, stages x makespan)` reduced to lowest terms with a
    positive denominator. No floats: `3/11`, never `0.2727...`.

    Refuses the same schedules `bubble` refuses, and a `p` or `m` that is not a
    positive int.
    """
    raise NotImplementedError("stage 6: implement bubble_fraction()")


def replay(schedule, p, m):
    """Each micro-batch's exit step — the step it leaves the pipeline, that is
    the largest step any of its slots is at — as a tuple of `m` ints, in
    micro-batch order. With `gpipe` the exits descend; with `one_f_one_b` they
    ascend.

    Refuses the same schedules `bubble` refuses.
    """
    raise NotImplementedError("stage 6: implement replay()")
