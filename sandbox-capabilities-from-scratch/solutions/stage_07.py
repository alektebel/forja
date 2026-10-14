"""stage_07.py — the audit line, and the reason that is a word.

Sandbox & Capabilities From Scratch — stage 7: The audit line, and the reason that is a word

A run's power is decided by three sets, but the only proof of *which* one said no
is the line it leaves behind. Stage 8 writes one line per call — allowed or
denied — *before* the world is asked to do anything; stage 9 recomputes the whole
report out of those lines and decides it against the world's own record. So this
stage fixes the line's shape and its vocabulary and nothing else: seven keys
written in one order, a decision and a reason drawn from two closed tuples, and a
`parse_line` that is the exact inverse of `line`, so that the reader of a line and
its writer cannot disagree about what is in it.

    REASONS / DECISIONS   the two words a line's verdict is built from
    AUDIT_KEYS            the seven fields a line carries, in writing order
    SandboxError / AuditError   the course's refusal family, and this stage's
    line                  one line, every key, in AUDIT_KEYS order
    parse_line            the line read back, refusing what `line` would not write
    write_line            one line appended through the world's sink, and its count
"""

from collections.abc import Mapping

import tools

#: The seven reasons a decision can carry, in the order a line writes them. The
#: vocabulary is closed on purpose — a free-text reason is a reason nobody can
#: count — and its first member is `granted`: a call that was allowed because
#: every question answered yes is a reason too, and the most common one.
REASONS = ("granted", "unknown", "capability", "jail", "host", "limit", "secret")

#: The two decisions, in the order a line writes them.
DECISIONS = ("allowed", "denied")

#: The seven fields a line carries, in the order a line writes them. Every one of
#: them is always written: a line a reader has to guess at is not an audit.
AUDIT_KEYS = ("tick", "principal", "tool", "target", "decision", "reason", "bytes")

#: The audit's whole word set: the two decisions and the seven reasons, in
#: declared order. A refused word is offered the nearest word *of the audit*,
#: because a caller who wrote `denyed` where a reason belongs has confused the
#: two axes, and the word that does exist is the hint that matters.
_WORDS = DECISIONS + REASONS

#: What a line spells where a field has nothing to say: the *absence* of a target
#: is a position, not a silence.
_ABSENT = "-"


class SandboxError(ValueError):
    """The course's one refusal family, as `stage_01` declares it."""


class AuditError(SandboxError):
    """A line, a field or a vocabulary entry this stage refuses."""


def _count(value, what):
    """A non-negative int, refusing a bool and a float by name."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditError("%s must be an int, got %r" % (what, value))
    if value < 0:
        raise AuditError("%s must not be negative, got %r" % (what, value))
    return value


def _bare(value, what):
    """A non-empty `str` with no whitespace in it, or a refusal that names it."""
    if not isinstance(value, str):
        raise AuditError("%s must be a str, got %r" % (what, value))
    if not value:
        raise AuditError(
            "%s must not be empty: every key is always written, and an empty one "
            "is a field a reader has to guess at" % (what,))
    if any(char.isspace() for char in value):
        raise AuditError(
            "%s must not contain whitespace, got %r: a line is fields separated "
            "by single spaces, and a space inside one is a second field"
            % (what, value))
    return value


def _target(value):
    """A target: a `str`, empty or not, with no whitespace and no marker."""
    if not isinstance(value, str):
        raise AuditError("the target must be a str, got %r" % (value,))
    if value == _ABSENT:
        raise AuditError(
            "a target of %r is the marker for no target at all: a line that "
            "spells it has a target the reader cannot tell from its absence"
            % (value,))
    if any(char.isspace() for char in value):
        raise AuditError("the target must not contain whitespace, got %r"
                         % (value,))
    return value


def _member(value, vocabulary, what):
    """One word from a closed vocabulary, or a refusal with a suggestion.

    The suggestion is the world's own `tools._near`, over the audit's whole word
    set (`_WORDS`): a reason refused the word `denyed` names the decision it
    meant, and a value with no near word grows no suggestion at all.
    """
    if not isinstance(value, str):
        raise AuditError("%s must be a str, got %r" % (what, value))
    if value not in vocabulary:
        raise AuditError("%s is not one of %s: %r%s"
                         % (what, ", ".join(vocabulary), value,
                            tools._near(value, _WORDS)))
    return value


def _digit(token, text, what):
    """The non-negative int a bare field spells, or a refusal that names it."""
    if not token.isdigit():
        raise AuditError("%s of %r is %r, not a non-negative int"
                         % (what, text, token))
    return int(token)


def line(tick, *, principal, tool, target, decision, reason, bytes):
    """One audit line: every key, in `AUDIT_KEYS` order, no trailing space."""
    tick = _count(tick, "the tick")
    principal = _bare(principal, "the principal")
    tool = _bare(tool, "the tool")
    target = _target(target)
    decision = _member(decision, DECISIONS, "the decision")
    reason = _member(reason, REASONS, "the reason")
    bytes = _count(bytes, "the bytes")
    return "%d principal=%s tool=%s target=%s decision=%s reason=%s bytes=%d" % (
        tick, principal, tool, target or _ABSENT, decision, reason, bytes)


def parse_line(text):
    """The inverse of `line`: a mapping over `AUDIT_KEYS`, or a refusal."""
    if not isinstance(text, str):
        raise AuditError("an audit line must be a str, got %r" % (text,))
    fields = text.split(" ")
    if len(fields) != len(AUDIT_KEYS):
        raise AuditError(
            "the line %r carries %d field(s), not %d: a line is the tick and the "
            "six `key=value` pairs, and a field count that differs is a key set "
            "that differs" % (text, len(fields), len(AUDIT_KEYS)))
    tick = _digit(fields[0], text, "the tick")
    values = {}
    for index in range(1, len(AUDIT_KEYS)):
        key = AUDIT_KEYS[index]
        name, equals, value = fields[index].partition("=")
        if not equals or name != key:
            raise AuditError(
                "the field %r at index %d of %r is not %r: a line's keys are "
                "AUDIT_KEYS, in order" % (fields[index], index, text, key))
        values[key] = value
    principal = _bare(values["principal"], "the principal")
    tool = _bare(values["tool"], "the tool")
    raw = values["target"]
    if raw == _ABSENT:
        target = ""
    elif raw == "":
        raise AuditError(
            "the target of %r is empty: an absent target is spelled %r"
            % (text, _ABSENT))
    else:
        target = _target(raw)
    decision = _member(values["decision"], DECISIONS, "the decision")
    reason = _member(values["reason"], REASONS, "the reason")
    count = _digit(values["bytes"], text, "the bytes")
    return {"tick": tick, "principal": principal, "tool": tool, "target": target,
            "decision": decision, "reason": reason, "bytes": count}


def write_line(audit, entry):
    """One line built by `line`, appended through the sink, and its new count."""
    if not isinstance(entry, Mapping):
        raise AuditError("an audit entry must be a mapping over AUDIT_KEYS, got %r"
                         % (entry,))
    for key in entry:
        if key not in AUDIT_KEYS:
            hint = tools._near(key, AUDIT_KEYS) if isinstance(key, str) else ""
            raise AuditError("an audit entry has no field %r%s: a line is exactly "
                             "AUDIT_KEYS" % (key, hint))
    for key in AUDIT_KEYS:
        if key not in entry:
            raise AuditError(
                "an audit entry omits %r: every key is always written, and an "
                "omitted field is a line a reader has to guess at" % (key,))
    text = line(entry["tick"], principal=entry["principal"], tool=entry["tool"],
                target=entry["target"], decision=entry["decision"],
                reason=entry["reason"], bytes=entry["bytes"])
    return audit.record(text)
