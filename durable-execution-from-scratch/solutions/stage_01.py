"""stage_01.py — the line, and the journal that holds it.

Durable Execution From Scratch — stage 1: The line, and the journal that holds it

A run is not the process that started it; it is the log on disk. Before anything
else this course has to fix what a line of that log *is*: a tick, a kind, and the
fields the kind carries — and nothing else. Nine kinds, one vocabulary, and a
refusal that names the offender every time a line carries a field its kind does
not have, omits one it needs, or spells a number that is not a non-negative int.

    LINE_KEYS   the eight fields a line may carry, in the order they are written
    DurableError  the course's one refusal family (a ValueError)
    JournalError  what a line that is not a line raises
    line        build a line's text from its tick, its kind and its fields
    parse_line  the fields a line's text carries, and nothing it does not
    write_line  append a line to the world's journal — and do not sync it

DESIGN DECISION — why a field a kind does not carry is a refusal and not a
silent drop? A line is read by a process that was not there, so a field the
reader's kind does not expect is a *claim the reader cannot check*. Dropping it
turns a typo (`statuz=ok`) into a result whose status is its default, and the
reader then believes an outcome nobody wrote. The kinds' field lists below are
therefore explicit: a field outside the list is refused by name, with the fields
the kind does carry.

DESIGN DECISION — why the two tables `_CARRIED` and `_NEEDED` instead of one
required-field list? Because a `result` line may carry the worker's own `text`
detail ($3.2: `text` is read only for a `done` or `failed` state), and a line
that omits it is still a complete result. So a field is *carried* by a kind if
the kind may spell it, and *needed* if a line of that kind without it is not a
line. Everything else is the intersection, and the intersection is most of it.

DESIGN DECISION — why `key` and `text` for `start` rather than `job`? The run's
id and the plan's hash are not a job: `job` names a unit of work everywhere else
in the log, and a `start` line that used it would be indistinguishable from a
job line under any replay. `key` is this vocabulary's string identifier and
`text` is its free text, so `start key=run-1 text=plan:abc` reads the same way a
`claim job=fast owner=w1 ticks=5` does.

DESIGN DECISION — why the deadline and the attempt number travel as `ticks`? A
line carries ints as ints, and a number that is not a non-negative int must be
refused at the boundary; `claim ticks=5` (a deadline), `retry ticks=2` (an
attempt) and `result ticks=1` (what the attempt cost) all read back as ints, and
`ticks` is the one field that is checked as a number. A deadline sent as text
would be re-parsed by every later stage and refused by none.

DESIGN DECISION — why the line's text is `"<tick> <kind> [name=value ...]"` with
no trailing space or terminator? The tick and the kind are the only positional
tokens; every field is `name=value`, in `LINE_KEYS` order, so a line is a
function of its fields and nothing else. `write_line` owns the `"\\n"` that ends
it: a line is a *record*, and the terminator is the journal's business (stage 3's
`torn` is exactly the tail that never got one). A value may not contain
whitespace, because whitespace is the field separator, and a separator a value
could contain is not a separator.

TODO: implement `LINE_KEYS`, `line`, `parse_line` and `write_line`.
"""

from collections.abc import Mapping

import fleet
from disk import DEFAULT_JOURNAL

#: The eight fields a line may carry, in the order a line writes them. A field
#: outside this tuple is a typo, and a typo is refused by name.
LINE_KEYS = ("tick", "kind", "job", "owner", "status", "ticks", "key", "text")

#: The nine kinds of line a journal holds, in the order a run writes them:
#: the run begins, a worker takes a job, it says it is alive, it announces an
#: effect, an attempt ends, the effect landed, a lease ran out, the job is
#: re-issued, and the run has nothing left.
_KINDS = ("start", "claim", "beat", "intent", "result", "effect", "expire",
          "retry", "done")

#: What a `result` line's status may say — a worker's answer, not a state. The
#: state table's `pending`/`running`/`expired`/`done`/`failed`/`skipped` is a
#: replay's reading (stage 3), and a line that spelled one of those would be
#: reporting a decision the log has not made yet.
_STATUSES = fleet.OUTCOMES

#: The fields every kind carries, in the order they are written. A field here is
#: allowed; a field outside it is refused. `result` carries `text` because the
#: worker's own detail is what a `done`/`failed` state reads (contract §3.2).
_CARRIED = {
    "start": ("key", "text"),
    "claim": ("job", "owner", "ticks"),
    "beat": ("job", "owner", "ticks"),
    "intent": ("job", "key"),
    "result": ("job", "owner", "status", "ticks", "text"),
    "effect": ("job", "key"),
    "expire": ("job", "owner"),
    "retry": ("job", "ticks"),
    "done": (),
}

#: The fields a line of each kind cannot do without. Everything a kind carries
#: is needed except a `result`'s `text`, which is a detail a replay may not have.
_NEEDED = {
    "start": ("key", "text"),
    "claim": ("job", "owner"),
    "beat": ("job", "owner"),
    "intent": ("job", "key"),
    "result": ("job", "owner", "status"),
    "effect": ("job", "key"),
    "expire": ("job", "owner"),
    "retry": ("job",),
    "done": (),
}

#: Every field a caller may spell for a line, in `LINE_KEYS` order, `ticks`
#: excepted (it always has a value, so it is checked by its own rule): the set
#: the "does this kind carry it?" pass walks.
_SPELLED = ("job", "owner", "status", "key", "text")

#: How far a typo may be from a real name and still earn a suggestion. The
#: course's vocabulary is short and its words are close, so two edits is where a
#: suggestion stops being a guess.
_NEAR = 2


class DurableError(ValueError):
    """The course's one refusal family.

    Every stage derives its own refusal from this (`JournalError` here, then
    `LeaseError`, `ReplayError`, `EffectError` and stage 8's `ResumeError`), so a
    caller can catch a broken course with one `except DurableError` and still
    read a narrower `except` at the site that knows what it is doing.
    """


class JournalError(DurableError):
    """A line, a kind or a journal entry this stage refuses.

    The refusal always names the offender — the kind, the field, the tick, the
    text — and, when the offender is within edit distance two of a real name,
    the real name too. The vocabulary here is exactly where a typo silently
    becomes a default.
    """


def _edits(one, other):
    """The Levenshtein distance between two strings, as an int.

    Small and deterministic: no threshold below a full distance is needed, and
    the strings in this course are short.
    """
    previous = list(range(len(other) + 1))
    for i, left in enumerate(one, 1):
        current = [i]
        for j, right in enumerate(other, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _near(name, known):
    """The known name within `_NEAR` edits of `name`, or `None`.

    A `bool`, a number or a string of the wrong shape is never measured: the
    suggestion exists for a typo, and a name that is not a string is a mistake
    the refusal has already named.
    """
    if not isinstance(name, str) or name in known:
        return None
    best = None
    for candidate in known:
        if abs(len(candidate) - len(name)) > _NEAR:
            continue
        distance = _edits(name, candidate)
        if distance <= _NEAR and (best is None or distance < best[1]
                                  or (distance == best[1]
                                      and candidate < best[0])):
            best = (candidate, distance)
    return None if best is None else best[0]


def _maybe(name, known):
    """`; did you mean 'x'?` for a typo, and nothing when there is no candidate."""
    guessed = _near(name, known)
    return "" if guessed is None else "; did you mean %r?" % (guessed,)


def _require_tick(value, what):
    """A tick: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise JournalError(
            "a line's %s must be a non-negative int, got %r" % (what, value))
    return value


def _require_text(value, what):
    """A field's value: a non-empty str with no whitespace in it.

    Whitespace is the separator between a line's fields, so a value that
    contained it could not be read back: `text=a b` is not one field, it is a
    field and a mistake. The refusal names the field and the value.
    """
    if not isinstance(value, str) or not value.strip():
        raise JournalError("%s must be a non-empty str, got %r" % (what, value))
    for char in value:
        if char.isspace():
            raise JournalError(
                "%s must not contain whitespace, got %r: whitespace separates a "
                "line's fields" % (what, value))
    return value


def _require_kind(kind):
    """A kind that is one of the nine, or a refusal naming it and the nine."""
    if kind not in _KINDS:
        raise JournalError(
            "there is no line kind %r; the kinds are %s%s"
            % (kind, ", ".join(_KINDS), _maybe(kind, _KINDS)))
    return kind


def line(tick, kind, *, job=None, owner=None, status=None, ticks=0, key=None,
         text=None):
    """Build a line's text: `"<tick> <kind> [name=value ...]"`.

    The fields written are exactly the fields the kind carries that the caller
    spelled, in `LINE_KEYS` order; a field the kind does not carry, a missing
    field the kind needs, a status the kind cannot say and a `ticks` that is not
    a non-negative int are all refused here, naming the offender.
    """
    kind = _require_kind(kind)
    tick = _require_tick(tick, "tick")
    carried = _CARRIED[kind]
    given = {"job": job, "owner": owner, "status": status, "key": key,
             "text": text}

    for name in _SPELLED:
        if given[name] is not None and name not in carried:
            raise JournalError(
                "a %r line does not carry %r; it carries %s"
                % (kind, name, ", ".join(carried) if carried else "nothing"))

    if "ticks" not in carried and ticks != 0:
        raise JournalError(
            "a %r line does not carry 'ticks', got %r" % (kind, ticks))

    parts = ["%d" % tick, kind]
    for name in carried:
        if name == "ticks":
            parts.append("ticks=%d" % _require_tick(ticks, "ticks"))
            continue
        value = given[name]
        if value is None:
            if name in _NEEDED[kind]:
                raise JournalError(
                    "a %r line needs %r; it carries %s"
                    % (kind, name, ", ".join(carried)))
            continue
        if name == "status":
            if value not in _STATUSES:
                raise JournalError(
                    "a result's status must be one of %s, got %r"
                    % (", ".join(_STATUSES), value))
        else:
            _require_text(value, "a line's %r" % (name,))
        parts.append("%s=%s" % (name, value))
    return " ".join(parts)


def parse_line(text):
    """The fields `text` carries, and nothing it does not.

    A line that is not a str, is empty, has no kind, names a kind that is not
    one of the nine, carries a field its kind does not have or misses one it
    needs, or spells a number that is not a non-negative int, is refused here —
    every refusal naming the line and the field.
    """
    if not isinstance(text, str):
        raise JournalError("a line must be a str, got %r" % (text,))
    if not text.strip():
        raise JournalError("a line must not be empty, got %r" % (text,))
    tokens = text.split()
    if len(tokens) < 2:
        raise JournalError(
            "a line must carry a tick and a kind, got %r" % (text,))
    raw_tick, kind = tokens[0], tokens[1]
    if not raw_tick.isdigit():
        raise JournalError(
            "a line's tick must be a non-negative int, got %r in %r"
            % (raw_tick, text))
    kind = _require_kind_in(kind, text)
    entry = {"tick": int(raw_tick), "kind": kind}
    carried = _CARRIED[kind]
    for token in tokens[2:]:
        if "=" not in token:
            raise JournalError(
                "a line's field must be name=value, got %r in %r"
                % (token, text))
        name, value = token.split("=", 1)
        if name not in LINE_KEYS:
            raise JournalError(
                "a line has no field %r in %r%s"
                % (name, text, _maybe(name, LINE_KEYS)))
        if name not in carried:
            raise JournalError(
                "a %r line does not carry %r, in %r; it carries %s"
                % (kind, name, text, ", ".join(carried) if carried else "nothing"))
        if name in entry:
            raise JournalError("a line has %r twice, in %r" % (name, text))
        if name == "ticks":
            if not value.isdigit():
                raise JournalError(
                    "a line's ticks must be a non-negative int, got %r in %r"
                    % (value, text))
            entry["ticks"] = int(value)
        elif name == "status":
            if value not in _STATUSES:
                raise JournalError(
                    "a result's status must be one of %s, got %r in %r"
                    % (", ".join(_STATUSES), value, text))
            entry["status"] = value
        elif not value:
            raise JournalError(
                "a line's %r must not be blank, in %r" % (name, text))
        else:
            entry[name] = value
    for name in _NEEDED[kind]:
        if name not in entry:
            raise JournalError(
                "a %r line needs %r, in %r; it carries %s"
                % (kind, name, text, ", ".join(carried) if carried else "nothing"))
    return entry


def _require_kind_in(kind, text):
    """A parsed kind, refused with the line it came from."""
    if kind not in _KINDS:
        raise JournalError(
            "there is no line kind %r in %r; the kinds are %s%s"
            % (kind, text, ", ".join(_KINDS), _maybe(kind, _KINDS)))
    return kind


def write_line(disk, entry):
    """Append one line to the world's journal, and return the new length.

    `entry` is a mapping carrying `tick`, `kind` and the kind's fields; a key it
    does not have, a required key it lacks and any value the kind refuses are
    refused here, naming the offender. The line is appended through
    `disk.write` and **not** synced: a line is a prediction until a sync makes
    it a fact, and stage 2 owns the sync.
    """
    if not isinstance(entry, Mapping):
        raise JournalError("a journal entry must be a mapping, got %r" % (entry,))
    for name in entry:
        if name not in LINE_KEYS:
            raise JournalError(
                "a journal entry has no field %r; a line's fields are %s%s"
                % (name, ", ".join(LINE_KEYS), _maybe(name, LINE_KEYS)))
    for name in ("tick", "kind"):
        if name not in entry:
            raise JournalError(
                "a journal entry needs %r; a line's fields are %s"
                % (name, ", ".join(LINE_KEYS)))
    fields = {name: value for name, value in entry.items()
              if name not in ("tick", "kind")}
    text = line(entry["tick"], entry["kind"], **fields)
    return disk.write(DEFAULT_JOURNAL, text + "\n")
