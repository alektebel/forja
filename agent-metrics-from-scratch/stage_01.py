"""Agent Metrics From Scratch — stage 1: The event, and the fact it records.

A trace is not a metric. A trace is what one call did — E1's harness writes one
per call — and a metric is a *fold over a window of events*, which is a different
kind of object entirely. So this stage fixes the event: twelve fields, five
kinds, and one rule that decides the rest, namely that the **kind decides which
fields exist**. An `admitted` event has an attempt and nothing else; a `started`
event adds the wait it just finished; a `finished` event adds its outcome, the
service it took, the tokens it spent and the error it ended with; a `retried` and
a `dropped` event each add the reason. Every field is always present in the line —
a field the kind does not carry is written `-` — because a field that is simply
missing is a field two readers will disagree about.

    EVENT_KEYS      the twelve fields, in the order a line writes them
    KINDS           the five kinds, in the order they may happen at one tick
    ABSENT          what a field nobody measured is spelled
    CARRIES         the fields a kind may carry, beyond the five every kind has
    REQUIRED        the fields a kind must carry
    TelemetryError  the course's one refusal family (a ValueError)
    EventError      what an event that is not one raises
    carries         the fields a kind may carry, by name, or a refusal
    parse_event     a line or a mapping, materialised as a record over EVENT_KEYS
    write_event     the exact inverse: a record, as the line it would have been
    read_events     every line of a run, refusing by index and text

DESIGN DECISION — why does the *kind* decide which fields exist, instead of one
event shape with optional fields?
    Because an optional field is a field whose absence has two meanings and no
    reader can tell them apart. A `started` event with `outcome="-"` and a
    `started` event with no `outcome` key at all are the same fact, and the moment
    two stages disagree about which spelling means what, every fold above them
    answers a different question than the one it was asked. So the kind is the
    schema: `carries(kind)` is the one place the rule is written, a field the kind
    does not carry must be `ABSENT`, and a field it does carry must not be — a
    `finished` event that does not say how it finished is not a finished event.
    The one exception is deliberate: `error` is carried by `finished`, `retried`
    and `dropped` and may still be `ABSENT`, because a call that succeeded has no
    error and inventing one would be worse than an empty field.

DESIGN DECISION — why is an absent field written `-` rather than omitted, and why
does the writer refuse a record that is missing one?
    Because the line is a *format*, and a format is something a reader can rely on
    without parsing the sentence that describes it. Every line carries exactly
    twelve fields in one order, so a reader that splits on a single space and
    counts keys either reads the whole event or refuses it; nothing is ever
    silently dropped. A writer that skipped an empty field would produce a line
    whose fifth position depends on which fields were empty, and the first bug it
    would cause is invisible: a `finished` event whose `error` was omitted would
    read back with `tokens_out=1` in the wrong column. `write_event` therefore
    validates through the same door `parse_event` uses, and the two are inverses
    on every well-formed event.

DESIGN DECISION — why is a field the kind carries refused when it is `-`?
    Because `-` is the only thing in this format that means "nobody measured
    this", and the kinds that carry a field are exactly the kinds for which it was
    measured. A `finished` event with `outcome="-"` is not a finish without an
    outcome; it is a line that a later fold will either skip or count as zero, and
    both are wrong in a way no check downstream can see. So the rule runs both
    ways: not carried must be `-`, carried must not be. `REQUIRED` names the
    second half of it, and the refusal says which of the two mistakes it is.

DESIGN DECISION — why does the reader refuse a line whose fields are in the wrong
*order*, when the keys are all there?
    Because the order is not decoration, it is the reason a line can be split on a
    single space at all. This format has no quoting, no escaping and no nesting:
    the writer joins `key=value` pairs with one space and the reader splits them,
    so any value containing a space would silently become two fields — which is
    exactly why the world's own closed vocabularies (`KINDS`, the outcomes,
    `telemetry.ERRORS`) are all space-free. A reader that accepted a reordered line
    would be accepting a *different* format that happens to parse today, and the
    first record it would mis-read is the one where a caller built the mapping in
    their own key order. So the order is checked, the check names the position
    that is wrong, and the whole sequence is refused by index and text.

DESIGN DECISION — why is every numeric field an `int`, and why is a `bool`
refused even though it is one?
    Because a tick, an attempt and a token count are *counts*, and a count that is
    a float is a number nobody can add up to a whole. `True` is an instance of
    `int` in Python and would sail through `isinstance(value, int)` as one tick,
    so it is refused by name: a boolean in a count is a caller who reached for a
    flag where the schema wanted a number, and this course would rather fail at
    the door than sum a `True` into a latency.

TODO: implement `carries`, `parse_event`, `write_event` and `read_events`.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

import fleet
import telemetry

#: The twelve fields of an event, in the order a line writes them. Every line
#: carries all twelve; a field the kind does not carry is `ABSENT`.
EVENT_KEYS = ("tick", "task", "pool", "tenant", "kind", "attempt",
              "outcome", "wait", "service", "tokens_in", "tokens_out", "error")

#: The five kinds, in the order they may happen at a single tick. A finish at
#: tick t is a departure at tick t, so a task admitted and finished at the same
#: tick nets out to zero — which is a rule about *depth*, in stage 3, and the
#: reason this order is written down once.
KINDS = ("admitted", "started", "finished", "retried", "dropped")

#: What a field nobody measured is spelled. Never a number, never an empty
#: string: a field is a position in the line, and a silence is not a value.
ABSENT = "-"

#: The fields a kind may carry, beyond the five every kind carries — `tick`,
#: `task`, `pool`, `tenant` and `kind`, which are the event itself.
CARRIES = MappingProxyType({
    "admitted": ("attempt",),
    "started": ("attempt", "wait"),
    "finished": ("attempt", "outcome", "service", "tokens_in", "tokens_out",
                 "error"),
    "retried": ("attempt", "error"),
    "dropped": ("attempt", "error"),
})

#: The fields a kind must carry. `error` is absent from every row on purpose: a
#: call that succeeded has no error, and a field that may be empty is not the
#: same as a field that may be missing.
REQUIRED = MappingProxyType({
    "admitted": ("attempt",),
    "started": ("attempt", "wait"),
    "finished": ("attempt", "outcome", "service", "tokens_in", "tokens_out"),
    "retried": ("attempt",),
    "dropped": ("attempt",),
})

#: The five fields every kind carries, in the order `EVENT_KEYS` has them.
_BASE = ("tick", "task", "pool", "tenant", "kind")

#: The fields whose value is a count, and the ones whose value is a name.
_NUMERIC = ("tick", "attempt", "wait", "service", "tokens_in", "tokens_out")
_NAMES = ("task", "pool", "tenant")


class TelemetryError(ValueError):
    """The course's one refusal family.

    Every stage derives its own refusal from this one (`EventError` here, then
    `WindowError`, `GaugeError`, `QuantileError`, `LatencyError`, `CostError`,
    `RateError`, `PartitionError`, `ReportError` and stage 10's `SloError`), so a
    caller can catch a broken course with one `except TelemetryError` and still
    read a narrower `except` at the site that knows what it is doing.
    """


class EventError(TelemetryError):
    """An event, a line or a field this stage refuses.

    The refusal names the offender — the position, the key, the kind, the value —
    and, when the offender is within edit distance two of a field or a kind the
    vocabulary has, the name it probably meant.
    """


def carries(kind):
    """The fields a kind may carry, beyond the five every kind carries.

    Refuses a name that is not one of `KINDS`, with a suggestion when it is
    close — a kind is a closed vocabulary and a typo in one is never a new kind.
    """
    raise NotImplementedError("stage 1: implement carries()")


def parse_event(what):
    """One event, materialised as a fresh record over exactly `EVENT_KEYS`.

    `what` is either a line in the world's format (twelve `key=value` fields, one
    space apart, in `EVENT_KEYS` order) or a mapping over `EVENT_KEYS`. Every
    refusal names the field position or the key, and the offending text: a field
    outside the vocabulary, a field the kind does not carry that is not `ABSENT`,
    a field the kind carries that is (`"a finished event needs an outcome"`), a
    numeric field that is not a non-negative `int` (a `bool` is refused by name),
    a name field that is empty or carries whitespace, a kind outside `KINDS`, an
    outcome outside `fleet.OUTCOMES`, and an error that is not a space-free
    string.
    """
    raise NotImplementedError("stage 1: implement parse_event()")


def write_event(event):
    """The line an event would have been written as, or a refusal.

    The exact inverse of `parse_event`: `parse_event(write_event(e)) == e` for
    every well-formed record, and `write_event(parse_event(line)) == line` for
    every line the world wrote. Fields are joined with a single space, in
    `EVENT_KEYS` order, with `ABSENT` where nobody measured anything — so a
    record that is missing a field, or carrying one its kind does not have, is
    refused here rather than written into a line somebody else has to guess at.
    """
    raise NotImplementedError("stage 1: implement write_event()")


def read_events(lines):
    """Every line of a run, as records, refusing by index and text.

    A `str` is one line; any other sequence is a sequence of lines. The first
    line that is not an event is refused naming the index it was at and the text
    it was ("line 3 is not an event: …"), because a run whose fourth line was
    dropped is not a run with three lines in it.
    """
    raise NotImplementedError("stage 1: implement read_events()")
