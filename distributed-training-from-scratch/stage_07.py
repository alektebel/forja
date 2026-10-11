"""Distributed Training From Scratch — stage 7: Pipeline schedules

Stage 6 wrote the two schedules as data; this stage adds the two things that
make a schedule a *scheduling* decision: **virtual stages** — a rank that owns
`v` chunks of the model instead of one — and **the memory the schedule holds
while it runs**. Nothing here talks to the fabric either: a schedule is still a
tuple of slots, read off the data and never off a formula.

Where stage 6's `Slot` carried `(step, stage, micro_batch, phase)`, this stage's
carries one more field, `chunk`: which of a rank's `v` chunks a task runs on. A
**unit** is one micro-batch's chunk — micro-batch `mu` and chunk `c` make the
unit `w = mu * v + c`, and there are `m * v` of them, with the `v` chunks of one
micro-batch consecutive in the unit order. The schedule is **stage 6's GPipe
over those `m * v` units**: unit `w` runs its forward at stage `s` at step
`w + s + 1`, and its backward there at step `2 * M + 2 * p - 2 - w - s` with
`M = m * v`. That one sentence is the whole of the interleaving, and it is why
`v = 1` must reproduce stage 6's `gpipe` exactly.

DESIGN DECISION — why is a chunk a virtual stage a rank owns, and not a second
micro-batch?
    Because the model is one model: splitting a micro-batch into `v` chunks is
    splitting its *layers*, not its tokens. The chunks of a micro-batch run on
    `v` different virtual stages, all of them owned by the ranks in the same
    order a single-chunk model would use, so a rank with `v` chunks can work on
    chunk `c` of a micro-batch and chunk `c + 1` of another in nearby steps.
    Reading `chunk` as a second micro-batch index would double the tokens and
    change the arithmetic, which is the one thing no plan here may do.

DESIGN DECISION — why is the schedule GPipe over the units, and what does the
bubble become?
    Because the interleaving does not change what work there is, only when the
    ranks do it: the `m * v` units are `m * v` micro-batches as far as the
    pipeline is concerned. GPipe's makespan for `N` micro-batches and `p` stages
    is `2N + 2p - 2`, so for `N = m * v` the idle `(stage, step)` pairs are
    `2p(p - 1)` and the fraction is `(p - 1) / (m * v + p - 1)` — for
    `(p, m, v) = (4, 8, 2)` the same `24` pairs stage 6 idles but over `152`
    instead of `88`, so `3/19` against `3/11`. The formula is not the point:
    the slots are, and replaying them is how the bubble is checked.

DESIGN DECISION — why is the bubble `(stage, step)` pairs and never a formula?
    Because a formula is a claim and the slot list is the thing. The check
    replays the tuple: the makespan is its largest step, a pair that carries one
    task is busy, a pair that carries two is still one pair, and the bubble is
    what is left over. That is the only version of the number that survives a
    schedule someone wrote by hand, and it is why this stage can assert
    `3/19` for `(4, 8, 2)` without an algebra of its own: the pair is exactly
    stage 6's GPipe bubble over `m * v = 16` micro-batches, recomputed there.

DESIGN DECISION — why does an activation live from its forward to its backward,
and why is the peak the union of the intervals?
    Because a pipeline trades memory for time in exactly that currency: the
    forward saves the activation its backward will consume, and the activation
    is dead the moment the backward has it. Its lifetime is therefore a range of
    steps — `(birth, death)`, born at the forward and dead at the backward — and
    the number of activations a rank holds at the peak is the number of those
    ranges that cover one step, which is a **union**: taking the longest single
    lifetime, or the bytes of one activation, undercounts a pipeline by the
    depth it is filled to, and that undercount is the whole mistake this stage
    exists to make visible.

DESIGN DECISION — why does `lifetime` refuse a schedule whose units do not
divide evenly over its chunks?
    Because `v` virtual stages per rank is a promise that each chunk carries the
    same number of units: a rank that owns `v` chunks has to be able to keep
    them fed, and a schedule that hands one chunk more work than another is not
    an interleaving, it is a schedule with an idle buffer and a live one. The
    count per chunk is read off the slots themselves, and the refusal names the
    counts it found.

TODO: implement `interleaved`, `lifetime` and `in_flight`.
"""

from dataclasses import dataclass

import model

#: The phases a slot can carry: a forward or a backward of one micro-batch's
#: chunk.
PHASES = ("f", "b")


@dataclass(frozen=True)
class Slot:
    """One task of one stage: the forward or the backward of one micro-batch's
    chunk, at one step. A stage can carry one `"f"` and one `"b"` in the same
    step; `chunk` is which of the rank's `v` virtual stages the task runs on."""

    step: int
    stage: int
    micro_batch: int
    phase: str
    chunk: int


def interleaved(p, m, v):
    """`p` stages, `m` micro-batches, `v` virtual stages per rank: the schedule
    as data, a canonical tuple of `Slot`s carrying the `chunk`.

    Stage 6's GPipe over the `m * v` units, unit `w = micro_batch * v + chunk`:
    the forward at stage `s` at step `w + s + 1`, the backward there at step
    `2 * (m * v) + 2 * p - 2 - w - s`. With `v = 1` it must reproduce stage 6's
    `gpipe(p, m)` exactly. Refuses `model.ModelError`, naming the offender, a
    `p`, `m` or `v` that is not a positive int.
    """
    raise NotImplementedError("stage 7: implement interleaved()")


def lifetime(schedule):
    """Each activation's `(birth, death)` step range, in `(micro_batch, chunk,
    stage)` order: born at the step its stage forwards it, dead at the step the
    same unit's backward at that stage consumes it.

    Refuses `model.ModelError`, naming the offender, a schedule that is not a
    canonical tuple of `Slot`s over its own `(p, m, v)`, one that misses a
    `(micro_batch, chunk, stage, phase)`, one whose backward is not after its
    own forward, one whose chunk order or stage order breaks the dependency, one
    that puts two tasks of the same phase in one step of one stage, and one
    whose units do not divide evenly over its chunks.
    """
    raise NotImplementedError("stage 7: implement lifetime()")


def in_flight(schedule, shape, *, batch, seq):
    """The bytes of the peak activations alive: the largest number of lifetimes
    covering one step — the union of the live intervals, never the longest one —
    times `shape.activation_bytes(batch, seq)`.

    Refuses `model.ModelError`, naming the offender, the schedules `lifetime`
    refuses, a `shape` that is not a `model.ModelShape`, and a `batch` or `seq`
    that is not a positive int.
    """
    raise NotImplementedError("stage 7: implement in_flight()")
