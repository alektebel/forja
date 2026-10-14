"""Durable Execution From Scratch — stage 1: The line, and the journal that holds it.

A run is not the process that started it; it is the log on disk. So this stage
fixes what a line of that log *is*, before anything writes, syncs, replays or
recovers one: a tick, a kind, and the fields the kind carries — and nothing else.
Nine kinds, one vocabulary, and a refusal that names the offender.

Every later stage reads these lines and none of them re-reads the process that
wrote them: stage 3 folds a state table out of the fields this stage fixes,
stage 5 reads an owner and a deadline out of a `claim`, stage 7 reads a job and
a key out of an `intent`. A line whose shape is decided per-stage is a log two
processes disagree about, and the whole course rests on the opposite.

    LINE_KEYS       the eight fields a line may carry, in writing order
    DurableError    the course's one refusal family (a ValueError)
    JournalError    what a line that is not a line raises
    line            build a line's text from its tick, its kind and its fields
    parse_line      the fields a line's text carries, and nothing it does not
    write_line      append a line to the world's journal, and do not sync it

DESIGN DECISION — why is a field a kind does not carry refused rather than
dropped?
    Because the reader was not there. A line is read by a process that only has
    the disk, so a field outside what its kind says is a claim the reader cannot
    check, and the cheapest thing to do with it — drop it — turns a typo into a
    default. `result status=ok statuz=finished` would parse as a result whose
    status is `ok`, and the reader believes an outcome nobody wrote. The kinds'
    field lists are therefore explicit, a field outside the list is refused by
    name, and the refusal says which fields the kind does carry so the fix is
    one edit away.

DESIGN DECISION — why two tables, `_CARRIED` and `_NEEDED`, instead of one
required-field list?
    Because "may spell" and "must spell" are different questions. A `result`
    line may carry the worker's own `text` detail — contract §3.2 reads that
    detail only for a `done` or `failed` state, and it is the worker's, not the
    journal's — and a line that omits it is still a complete result. So a field
    is *carried* when a line of that kind may spell it and *needed* when a line
    without it is not a line. Collapsing the two would refuse every result that
    has no detail, or accept a `claim` with no owner.

DESIGN DECISION — why does `start` carry `key` and `text` instead of `job`?
    Because a run is not a job and the log has to say so. `job` names a unit of
    work in every other kind, so a `start` that spelled `job=run-1` would be
    indistinguishable from a job line under any replay — and a replay is the
    only reader this log will ever have. `key` is this vocabulary's string
    identifier and `text` is its free text, so `start key=run-1 text=plan:abc`
    reads as "the run `run-1` began against plan `abc`" and stage 9 can count
    runs off the same field it counts effects with.

DESIGN DECISION — why do a deadline and an attempt number travel as `ticks`?
    Because a line carries a number as a number. `claim ticks=5` is a deadline,
    `retry ticks=2` is an attempt, `result ticks=1` is what an attempt cost —
    and all three read back as ints because `ticks` is the one field this stage
    checks as a number: a `float` or a `bool` is refused at the boundary, where
    the line is being written and somebody can still fix it. A deadline sent as
    text (`deadline=5`) would be re-parsed by every later stage and validated by
    none, which is precisely where a `"5"` becomes arithmetic on a string.

DESIGN DECISION — why is the line `"<tick> <kind> [name=value ...]"` with no
trailing space and no terminator?
    Because a line should be a function of its fields and nothing else. The tick
    and the kind are the only positional tokens (a reader always knows where
    they are), every field is `name=value` in `LINE_KEYS` order, and a value may
    not contain whitespace because whitespace is the separator — a separator a
    value could contain is not a separator. The `"\\n"` that ends the line
    belongs to `write_line`, not to `line`: the record is this stage's, the
    terminator is the journal's, and stage 3's `torn` is exactly the tail that
    never got one.

TODO: implement `LINE_KEYS`, `line`, `parse_line` and `write_line`.
"""

from collections.abc import Mapping

import fleet
from disk import DEFAULT_JOURNAL

#: The eight fields a line may carry, in the order a line writes them. A field
#: outside this tuple is a typo, and a typo is refused by name.
LINE_KEYS = ("tick", "kind", "job", "owner", "status", "ticks", "key", "text")


class DurableError(ValueError):
    """The course's one refusal family.

    Every stage derives its own refusal from this one (`JournalError` here, then
    `LeaseError`, `ReplayError`, `EffectError` and stage 8's `ResumeError`), so a
    caller can catch a broken course with one `except DurableError` and still
    read a narrower `except` at the site that knows what it is doing.
    """


class JournalError(DurableError):
    """A line, a kind or a journal entry this stage refuses.

    The refusal always names the offender — the kind, the field, the tick, the
    text — and, when the offender is within edit distance two of a real name,
    the real name too, because this vocabulary is exactly where a typo silently
    becomes a default.
    """


def line(tick, kind, *, job=None, owner=None, status=None, ticks=0, key=None,
         text=None):
    """Build a line's text: `"<tick> <kind> [name=value ...]"`.

    Only the fields the kind carries are written; a field the kind does not
    carry, a missing field the kind needs, a status the kind cannot say and a
    `ticks` that is not a non-negative int are refused, naming the offender.
    """
    raise NotImplementedError("stage 1: implement line()")


def parse_line(text):
    """The fields a line's text carries, and nothing it does not.

    A line that is not a str, is empty, has no kind, names a kind that is not
    one of the nine, carries a field its kind does not have or misses one it
    needs, or spells a number that is not a non-negative int, is refused —
    every refusal naming the line and the field.
    """
    raise NotImplementedError("stage 1: implement parse_line()")


def write_line(disk, entry):
    """Append one line to the world's journal, and return the new length.

    `entry` is a mapping carrying `tick`, `kind` and the kind's fields; a key it
    does not have, a required key it lacks and any value a kind refuses are
    refused, naming the offender. The line is appended through `disk.write` and
    **not** synced: a line is a prediction until a sync makes it a fact.
    """
    raise NotImplementedError("stage 1: implement write_line()")
