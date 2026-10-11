"""Distributed Training From Scratch — stage 6: Pipeline parallel (implementation).

The reasoning behind the two schedules lives in the template's docstring
(`stage_06.py`); this file is only the body. Steps are counted, never timed;
every number is an `int` and no fraction is ever a float.

The model, fixed once for the whole stage:

* steps are **1-based**;
* stage `s` (0-based) runs the **forward** of micro-batch `mu` at step
  `mu + s + 1` in both schedules, so the last micro-batch's forward leaves the
  last stage at step `m + p - 1`;
* a stage runs **at most one forward and one backward in the same step** — one
  forward, one backward, which is what the name of the second schedule means —
  so a step of a stage carries one slot, or two when one is an `"f"` of one
  micro-batch and the other a `"b"` of another;
* `gpipe` does every forward first and then every backward in reverse order, so
  its backward of micro-batch `mu` at stage `s` is at step
  `m + p + (m - 1 - mu) + (p - 1 - s)` and its last micro-batch exits at
  `2m + 2p - 2`;
* `one_f_one_b` streams the backwards against the forwards —
  `b(mu, s) = 2p - s + mu`, so the last stage back-propagates first and each
  earlier stage one step later — while a stage keeps laying a forward and a
  backward of different micro-batches into the same step; its makespan is
  `m + 2p - 1` and, on the same `p` and `m`, its bubble is half of `gpipe`'s
  (12 against 24 pairs for `p = 4, m = 8`) because its stages are busy while
  GPipe's wait for the fill and the drain;
* a schedule's **makespan** is its largest step, and its **bubble** is the
  number of `(stage, step)` pairs inside the makespan that hold no slot at all:
  a pair that runs one task is busy, a pair that runs two is still one pair.

Every function refuses (`model.ModelError`, naming the offender) a stage count
or micro-batch count that is not a positive int, a schedule that is not a tuple
of `Slot`s, a schedule missing an `(micro_batch, stage, phase)`, a backward
before its own forward, and a schedule that breaks the pipeline's dependencies.
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


def _count(value, what):
    """`value` as a positive int, or a refusal naming `what`."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise model.ModelError("%s=%r is not an int" % (what, value))
    if value < 1:
        raise model.ModelError("%s=%r is not a positive count" % (what, value))
    return value


def _shape(p, m):
    return _count(p, "p"), _count(m, "m")


def _check_schedule(schedule, p, m):
    """The schedule's slots as a dict keyed by `(micro_batch, stage, phase)`,
    or a refusal naming what is wrong with it (see the module docstring)."""
    if not isinstance(schedule, tuple):
        raise model.ModelError("schedule=%r is not a tuple" % (schedule,))
    slots = {}
    for slot in schedule:
        if not isinstance(slot, Slot):
            raise model.ModelError("schedule=%r holds %r, not a Slot"
                                   % (schedule, slot))
        if isinstance(slot.step, bool) or not isinstance(slot.step, int) \
                or slot.step < 1:
            raise model.ModelError("slot %r has step=%r, not a positive int"
                                   % (slot, slot.step))
        if isinstance(slot.stage, bool) or not isinstance(slot.stage, int) \
                or not 0 <= slot.stage < p:
            raise model.ModelError("slot %r names stage=%r, outside 0..%d"
                                   % (slot, slot.stage, p - 1))
        if isinstance(slot.micro_batch, bool) \
                or not isinstance(slot.micro_batch, int) \
                or not 0 <= slot.micro_batch < m:
            raise model.ModelError("slot %r names micro_batch=%r, outside 0..%d"
                                   % (slot, slot.micro_batch, m - 1))
        if slot.phase not in PHASES:
            raise model.ModelError("slot %r has phase=%r, not one of %r"
                                   % (slot, slot.phase, PHASES))
        key = (slot.micro_batch, slot.stage, slot.phase)
        if key in slots:
            raise model.ModelError(
                "micro-batch %d runs its %r through stage %d twice: %r and %r"
                % (slot.micro_batch, slot.phase, slot.stage, slots[key], slot))
        slots[key] = slot
    for micro_batch in range(m):
        for stage in range(p):
            for phase in PHASES:
                if (micro_batch, stage, phase) not in slots:
                    raise model.ModelError(
                        "micro-batch %d never runs its %r through stage %d"
                        % (micro_batch, phase, stage))
    for micro_batch in range(m):
        for stage in range(p):
            forward = slots[(micro_batch, stage, "f")].step
            backward = slots[(micro_batch, stage, "b")].step
            if backward <= forward:
                raise model.ModelError(
                    "micro-batch %d's backward through stage %d is at step %d, "
                    "not after its forward there at step %d"
                    % (micro_batch, stage, backward, forward))
            if stage > 0 and slots[(micro_batch, stage - 1, "f")].step \
                    >= forward:
                raise model.ModelError(
                    "micro-batch %d's forward through stage %d is at step %d, "
                    "not after stage %d's forward at step %d"
                    % (micro_batch, stage, forward, stage - 1,
                       slots[(micro_batch, stage - 1, "f")].step))
            if stage + 1 < p and slots[(micro_batch, stage + 1, "b")].step \
                    >= backward:
                raise model.ModelError(
                    "micro-batch %d's backward through stage %d is at step %d, "
                    "not after stage %d's backward at step %d"
                    % (micro_batch, stage, backward, stage + 1,
                       slots[(micro_batch, stage + 1, "b")].step))
    for stage in range(p):
        for step in set(s.step for s in schedule if s.stage == stage):
            at = [s for s in schedule if s.stage == stage and s.step == step]
            if len(at) > 2 or (len(at) == 2 and at[0].phase == at[1].phase):
                raise model.ModelError(
                    "stage %d carries %d tasks in step %d (%r); a step of a "
                    "stage is one forward, one backward, or both"
                    % (stage, len(at), step, tuple(sorted(s.phase for s in at))))
    return slots


def _canonical(slots):
    """The slots as a canonical tuple: sorted by `(step, stage, phase,
    micro_batch)`, so two schedules that say the same thing are equal."""
    return tuple(sorted(slots,
                        key=lambda s: (s.step, s.stage, s.phase, s.micro_batch)))


def gpipe(p, m):
    """Every forward, then every backward in reverse order."""
    p, m = _shape(p, m)
    slots = []
    for micro_batch in range(m):
        for stage in range(p):
            slots.append(Slot(micro_batch + stage + 1, stage, micro_batch, "f"))
    for micro_batch in range(m):
        for stage in range(p):
            slots.append(Slot(m + p + (m - 1 - micro_batch) + (p - 1 - stage),
                              stage, micro_batch, "b"))
    return _canonical(slots)


def one_f_one_b(p, m):
    """Warm-up, then a forward and a backward per stage per step, then the
    cool-down: the backward stream runs against the forward stream (last stage
    first, one stage earlier per step) while each stage keeps paving its own
    steps with one forward and one backward of different micro-batches."""
    p, m = _shape(p, m)
    slots = []
    for micro_batch in range(m):
        for stage in range(p):
            slots.append(Slot(micro_batch + stage + 1, stage, micro_batch, "f"))
            slots.append(Slot(2 * p - stage + micro_batch,
                              stage, micro_batch, "b"))
    return _canonical(slots)


def _makespan(schedule):
    return max(slot.step for slot in schedule)


def bubble(schedule, p):
    """The idle `(stage, step)` pairs inside the makespan, counted from the
    schedule itself: a pair with one task is busy, a pair with two is one pair."""
    p = _count(p, "p")
    slots = _check_schedule(schedule, p, max(s.micro_batch for s in schedule) + 1)
    steps = {(slot.stage, slot.step) for slot in schedule}
    total = p * _makespan(schedule)
    return total - len(steps)


def bubble_fraction(p, m, *, schedule):
    """The bubble over the `(stage, step)` pairs the makespan spends, exact."""
    p, m = _shape(p, m)
    slots = _check_schedule(schedule, p, m)
    idle = bubble(schedule, p)
    total = p * _makespan(schedule)
    divisor = gcd(idle, total) or 1
    return (idle // divisor, total // divisor)


def replay(schedule, p, m):
    """Each micro-batch's exit step: the step it leaves the pipeline, i.e. the
    largest step any of its slots is at."""
    p, m = _shape(p, m)
    slots = _check_schedule(schedule, p, m)
    return tuple(max(slots[(micro_batch, stage, phase)].step
                     for stage in range(p) for phase in PHASES)
                 for micro_batch in range(m))
