"""Distributed Training From Scratch — stage 7: Pipeline schedules (implementation).

The reasoning behind the model lives in the template's docstring
(`stage_07.py`); this file is only the body. Steps are counted, never timed;
every number is an `int` and no fraction is ever a float.

The model, fixed once for the whole stage:

* a **unit** is one micro-batch's chunk: micro-batch `mu` and chunk `c` make the
  unit `w = mu * v + c`, and there are `m * v` of them — stage 6's GPipe over
  the `m * v` units, with the `v` chunks of one micro-batch consecutive in the
  unit order, one chunk per virtual stage of the rank that owns it;
* unit `w` runs its **forward** at stage `s` at step `w + s + 1` and its
  **backward** there at step `2 * M + 2 * p - 2 - w - s`, where `M = m * v`;
* a step of a stage carries at most one forward and one backward, of different
  units, and never a backward in the step of its own unit's forward;
* the **bubble** is the `(stage, step)` pairs inside the makespan that carry no
  task: because the schedule is GPipe relabeled, it is stage 6's GPipe bubble
  over `m * v` units — `(p - 1) / (m * v + p - 1)`, and `v = 1` is `gpipe(p, m)`;
* an **activation** is produced by a forward and consumed by the same unit's
  backward at that stage, so its lifetime is `(forward.step, backward.step)`;
  the peak memory is the **union** of those live intervals over the step count —
  as many activations as are alive at once, not the longest one — times the
  bytes of one activation.

Every function refuses (`model.ModelError`, naming the offender) a count that is
not a positive int, a schedule that is not a tuple of `Slot`s with the field
set below, one that misses a `(micro_batch, chunk, stage, phase)`, one whose
chunk order breaks its dependency, one whose units do not divide evenly over its
chunks, and a shape or a token count that is not the reference's.
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


def _count(value, what):
    """`value` as a positive int, or a refusal naming `what`."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise model.ModelError("%s=%r is not an int" % (what, value))
    if value < 1:
        raise model.ModelError("%s=%r is not a positive count" % (what, value))
    return value


def _dims(p, m, v):
    return _count(p, "p"), _count(m, "m"), _count(v, "v")


def _canonical(slots):
    """The slots as a canonical tuple: sorted by `(step, stage, phase,
    micro_batch, chunk)`, so two schedules that say the same thing are equal."""
    return tuple(sorted(slots,
                        key=lambda s: (s.step, s.stage, s.phase,
                                       s.micro_batch, s.chunk)))


def _slots_of(schedule):
    """The schedule validated, as `(slots, p, m, v)` with `slots` keyed by
    `(micro_batch, chunk, stage, phase)`, or a refusal naming what is wrong."""
    if not isinstance(schedule, tuple) or not schedule:
        raise model.ModelError(
            "schedule=%r is not a non-empty tuple" % (schedule,))
    for slot in schedule:
        if not isinstance(slot, Slot):
            raise model.ModelError(
                "schedule=%r holds %r, not a Slot" % (schedule, slot))
    stages = {slot.stage for slot in schedule}
    micro_batches = {slot.micro_batch for slot in schedule}
    chunks = {slot.chunk for slot in schedule}
    p, m, v = max(stages) + 1, max(micro_batches) + 1, max(chunks) + 1
    if stages != set(range(p)) or micro_batches != set(range(m)) \
            or chunks != set(range(v)):
        raise model.ModelError(
            "schedule=%r does not cover stages 0..%d, micro-batches 0..%d and "
            "chunks 0..%d" % (schedule, p - 1, m - 1, v - 1))
    slots = {}
    for slot in schedule:
        if isinstance(slot.step, bool) or not isinstance(slot.step, int) \
                or slot.step < 1:
            raise model.ModelError(
                "slot %r has step=%r, not a positive int" % (slot, slot.step))
        if slot.phase not in PHASES:
            raise model.ModelError(
                "slot %r has phase=%r, not one of %r" % (slot, slot.phase, PHASES))
        key = (slot.micro_batch, slot.chunk, slot.stage, slot.phase)
        if key in slots:
            raise model.ModelError(
                "micro-batch %d runs its %r of chunk %d through stage %d twice: "
                "%r and %r" % (slot.micro_batch, slot.phase, slot.chunk,
                               slot.stage, slots[key], slot))
        slots[key] = slot
    units = sorted({(key[0], key[1]) for key in slots})
    for mu, chunk in units:
        for stage in range(p):
            for phase in PHASES:
                if (mu, chunk, stage, phase) not in slots:
                    raise model.ModelError(
                        "micro-batch %d never runs its %r of chunk %d "
                        "through stage %d" % (mu, phase, chunk, stage))
    unit_set = {(key[0], key[1]) for key in slots}
    for mu, chunk in units:
        for stage in range(p):
            forward = slots[(mu, chunk, stage, "f")].step
            backward = slots[(mu, chunk, stage, "b")].step
            if backward <= forward:
                raise model.ModelError(
                    "micro-batch %d's backward of chunk %d through stage %d "
                    "is at step %d, not after its forward there at step %d"
                    % (mu, chunk, stage, backward, forward))
            if stage > 0 and slots[(mu, chunk, stage - 1, "f")].step >= forward:
                raise model.ModelError(
                    "micro-batch %d's forward of chunk %d through stage %d is "
                    "at step %d, not after stage %d's forward at step %d"
                    % (mu, chunk, stage, forward, stage - 1,
                       slots[(mu, chunk, stage - 1, "f")].step))
            if stage + 1 < p and slots[(mu, chunk, stage + 1, "b")].step >= backward:
                raise model.ModelError(
                    "micro-batch %d's backward of chunk %d through stage %d is "
                    "at step %d, not after stage %d's backward at step %d"
                    % (mu, chunk, stage, backward, stage + 1,
                       slots[(mu, chunk, stage + 1, "b")].step))
            if chunk > 0 and (mu, chunk - 1) in unit_set \
                    and slots[(mu, chunk - 1, stage, "f")].step >= forward:
                raise model.ModelError(
                    "micro-batch %d's chunk %d through stage %d is at step %d, "
                    "not after its chunk %d at step %d"
                    % (mu, chunk, stage, forward, chunk - 1,
                       slots[(mu, chunk - 1, stage, "f")].step))
    for stage in range(p):
        for step in set(slot.step for slot in schedule if slot.stage == stage):
            at = [slot for slot in schedule
                  if slot.stage == stage and slot.step == step]
            if len(at) > 2 or (len(at) == 2 and at[0].phase == at[1].phase):
                raise model.ModelError(
                    "stage %d carries %d tasks in step %d (%r); a step of a "
                    "stage is one forward, one backward, or both"
                    % (stage, len(at), step, tuple(sorted(x.phase for x in at))))
    counts = {chunk: sum(1 for key in slots
                         if key[1] == chunk and key[3] == "f")
              for chunk in range(v)}
    if len(set(counts.values())) != 1:
        raise model.ModelError(
            "the units do not divide evenly over the %d chunks: %r"
            % (v, counts))
    return slots, p, m, v


def interleaved(p, m, v):
    """The interleaved schedule: stage 6's GPipe over the `m * v` units, with
    micro-batch `mu`'s chunk `c` the unit `mu * v + c`. Canonical tuple of
    `Slot`s carrying the `chunk`."""
    p, m, v = _dims(p, m, v)
    units = m * v
    slots = []
    for micro_batch in range(m):
        for chunk in range(v):
            unit = micro_batch * v + chunk
            for stage in range(p):
                slots.append(Slot(unit + stage + 1, stage, micro_batch, "f",
                                  chunk))
                slots.append(Slot(2 * units + 2 * p - 2 - unit - stage, stage,
                                  micro_batch, "b", chunk))
    return _canonical(slots)


def lifetime(schedule):
    """Each activation's `(birth, death)` step range: one per forward, in
    `(micro_batch, chunk, stage)` order, born at the forward's step and dead at
    the same unit's backward at that stage."""
    slots, p, m, v = _slots_of(schedule)
    units = sorted({(key[0], key[1]) for key in slots})
    return tuple((slots[(mu, chunk, stage, "f")].step,
                  slots[(mu, chunk, stage, "b")].step)
                 for mu, chunk in units for stage in range(p))


def in_flight(schedule, shape, *, batch, seq):
    """The bytes of the peak activations alive: the largest number of
    lifetimes covering one step, times one activation's bytes."""
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    batch = _count(batch, "batch")
    seq = _count(seq, "seq")
    intervals = lifetime(schedule)
    makespan = max(death for _, death in intervals)
    peak = 0
    for step in range(1, makespan + 1):
        live = 0
        for birth, death in intervals:
            if birth <= step <= death:
                live += 1
        if live > peak:
            peak = live
    return peak * shape.activation_bytes(batch, seq)
