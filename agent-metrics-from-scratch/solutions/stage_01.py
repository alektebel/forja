"""Agent Metrics From Scratch — stage 1: The event, and the fact it records.

An event is one fact about the fleet, written down in twelve fields by a writer
that always writes all twelve and a reader that either reads all twelve or
refuses the line. The kind decides which fields *mean* something: five fields are
the event itself, and `CARRIES` names the rest for each kind, `REQUIRED` the ones
that must not be `ABSENT`. `parse_event` is the only door — a line and a mapping
both come through it — and `write_event` is the same door walked backwards, which
is what makes the two inverses rather than two opinions.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

import fleet
import telemetry

#: The twelve fields of an event, in the order a line writes them.
EVENT_KEYS = ("tick", "task", "pool", "tenant", "kind", "attempt",
              "outcome", "wait", "service", "tokens_in", "tokens_out", "error")

#: The five kinds, in the order they may happen at a single tick.
KINDS = ("admitted", "started", "finished", "retried", "dropped")

#: What a field nobody measured is spelled.
ABSENT = "-"

#: The fields a kind may carry, beyond the five every kind carries.
CARRIES = MappingProxyType({
    "admitted": ("attempt",),
    "started": ("attempt", "wait"),
    "finished": ("attempt", "outcome", "service", "tokens_in", "tokens_out",
                 "error"),
    "retried": ("attempt", "error"),
    "dropped": ("attempt", "error"),
})

#: The fields a kind must carry. `error` is absent from every row on purpose.
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

#: Beyond `_NAMES` and `kind`, these are the fields no event may leave empty.
_ALWAYS = ("tick",)


class TelemetryError(ValueError):
    """The course's one refusal family."""


class EventError(TelemetryError):
    """An event, a line or a field this stage refuses."""


def carries(kind):
    """The fields a kind may carry, beyond the five every kind carries."""
    return CARRIES[_kind(kind)]


def parse_event(what):
    """One event, materialised as a fresh record over exactly `EVENT_KEYS`."""
    if isinstance(what, str):
        record = _read_line(what)
    elif isinstance(what, Mapping):
        record = _read_mapping(what)
    else:
        raise EventError("an event is a line or a mapping, got %r"
                         % (type(what).__name__,))
    _validate(record)
    return record


def write_event(event):
    """The line an event would have been written as, or a refusal."""
    record = parse_event(event)
    return " ".join("%s=%s" % (key, record[key]) for key in EVENT_KEYS)


def read_events(lines):
    """Every line of a run, as records, refusing by index and text."""
    if isinstance(lines, str):
        lines = (lines,)
    elif isinstance(lines, Sequence) and not isinstance(lines, (bytes, bytearray)):
        lines = tuple(lines)
    else:
        raise EventError("read_events takes a line or a sequence of lines, got %r"
                         % (type(lines).__name__,))
    events = []
    for index, text in enumerate(lines):
        if not isinstance(text, str):
            raise EventError("line %d is not a str, got %r"
                             % (index, type(text).__name__))
        try:
            events.append(parse_event(text))
        except EventError as wrong:
            raise EventError("line %d is not an event: %s — %r"
                             % (index, wrong, text)) from None
    return tuple(events)


def _has_space(text):
    """Whether a name would break the one line format there is: no quoting."""
    return any(character.isspace() for character in text)


def _kind(kind):
    """A kind out of the vocabulary, or a refusal that names it."""
    if not isinstance(kind, str):
        raise EventError("a kind must be a str, got %r (%s)"
                         % (kind, type(kind).__name__))
    if kind not in KINDS:
        raise EventError("no such kind: %r%s" % (kind, telemetry._near(kind, KINDS)))
    return kind


def _read_line(text):
    """A line in the world's format, as a record with its numbers converted."""
    chunks = text.split(" ")
    if len(chunks) != len(EVENT_KEYS):
        raise EventError("a line carries %d fields, not the %d of the format: %r"
                         % (len(chunks), len(EVENT_KEYS), text))
    record = {}
    for position, chunk in enumerate(chunks):
        key, sep, value = chunk.partition("=")
        if not sep:
            raise EventError("field %d is not key=value: %r" % (position, chunk))
        if key != EVENT_KEYS[position]:
            raise EventError("field %d is %r where the format has %r"
                             % (position, key, EVENT_KEYS[position]))
        record[key] = _number(value, key, position) if key in _NUMERIC else value
    return record


def _number(text, key, position):
    """A numeric field of a line: `ABSENT`, or an int the field could hold."""
    if text == ABSENT:
        return ABSENT
    body = text[1:] if text.startswith("-") else text
    if not body.isdigit() or not body.isascii():
        raise EventError("field %d (%s) is not a number: %r" % (position, key, text))
    return int(text)


def _read_mapping(given):
    """A record over `EVENT_KEYS`, in the format's order, or a refusal."""
    missing = [key for key in EVENT_KEYS if key not in given]
    if missing:
        raise EventError("an event is missing %r" % (missing[0],))
    extra = [key for key in given if key not in EVENT_KEYS]
    if extra:
        raise EventError("an event has no field %r%s"
                         % (extra[0], telemetry._near(extra[0], EVENT_KEYS)))
    return {key: given[key] for key in EVENT_KEYS}


def _validate(record):
    """Every rule the kind decides, and every rule a field decides."""
    kind = _kind(record["kind"])
    for key in _ALWAYS + _NAMES:
        if record[key] is ABSENT:
            raise EventError("a %s event needs %r" % (kind, key))
    for key in _NUMERIC:
        value = record[key]
        if value is ABSENT:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise EventError("the field %r of an event of kind %r must be an "
                             "int, got %r" % (key, kind, type(value).__name__))
        if value < 0:
            raise EventError("the field %r of an event of kind %r is negative: %d"
                             % (key, kind, value))
    if record["attempt"] is not ABSENT and record["attempt"] < 1:
        raise EventError("an attempt is counted from 1, got %r" % (record["attempt"],))
    for key in _NAMES:
        value = record[key]
        if not isinstance(value, str) or not value or _has_space(value):
            raise EventError("the field %r must be a name without whitespace, got "
                             "%r" % (key, value))
    outcome = record["outcome"]
    if outcome is not ABSENT and outcome not in fleet.OUTCOMES:
        raise EventError("no such outcome: %r%s"
                         % (outcome, telemetry._near(outcome, fleet.OUTCOMES)))
    error = record["error"]
    if error is not ABSENT and (not isinstance(error, str) or not error
                                or _has_space(error)):
        raise EventError("an error is a space-free word or %r, got %r"
                         % (ABSENT, error))
    carried = CARRIES[kind]
    for key in EVENT_KEYS:
        if key in _BASE or key in carried:
            continue
        if record[key] is not ABSENT:
            raise EventError("a %s event does not carry %r" % (kind, key))
    for key in REQUIRED[kind]:
        if record[key] is ABSENT:
            raise EventError("a %s event needs %r" % (kind, key))
