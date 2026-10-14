"""Sandbox & Capabilities From Scratch — stage 7: The audit line, and the reason that is a word.

A run's power is decided by three sets — what a tool declares, what its principal
granted, and what the world will still afford — but the only proof of *which* one
said no is the line the run leaves behind. So before any stage writes one, this
stage fixes the line: seven keys written in one order, every one of them always
present, a decision and a reason drawn from two closed tuples, and a reader that
is the exact inverse of the writer so that the two can never disagree.

Every later stage speaks in these words and none of them invents its own: stage 8
writes one line per call, allowed or denied, *before* the world is asked to do
anything; stage 9 recomputes the whole report out of the parsed lines and decides
it against the world's own record; and stage 10's capstone states its property
over the run's lines. A line whose shape every stage decides for itself is a set
of records no two of them agree on, and the whole audit is that agreement.

    REASONS        the seven reasons a decision can carry, in writing order
    DECISIONS      the two decisions, in writing order
    AUDIT_KEYS     the seven fields a line carries, in writing order
    SandboxError   the course's one refusal family (a ValueError)
    AuditError     what a line, a field or a vocabulary entry this stage refuses
    line           one line, every key, in AUDIT_KEYS order, and no trailing space
    parse_line     the line read back, refusing what `line` would not write
    write_line     one line appended through the world's sink, and its new count

DESIGN DECISION — why is every key always written, with `-` for an absent target?
    Because a line is a reader's only evidence, and evidence a reader has to fill
    in is a guess. A tool whose target kind is `"none"` has no target; the honest
    spelling of that is a *position* — `target=-` — not a missing field, because a
    line that omits `target` entirely cannot be told apart from a line written by
    a version of the writer that did not yet have the field. The count is fixed at
    seven, the key set is fixed at `AUDIT_KEYS`, and the marker says "nothing to
    say here", which is data, while silence says nothing at all.

DESIGN DECISION — why is the reason vocabulary *closed*, and why is `granted` in
it while `denied` is not?
    Because the audit is something that has to be counted, and a count needs a
    vocabulary that two writers cannot disagree about: `"denied"` is a *decision*
    and `"not allowed"` is a sentence, and a run whose reasons are free text can
    be read but never aggregated — "how often did the jail say no?" becomes a
    question about spelling. The reason records *why* the decision came out that
    way, so `granted` is its most common member (the call was allowed because no
    question answered no) and `denied` is deliberately not — a decision answers
    "what", a reason answers "why", and the two tuples are two axes.

DESIGN DECISION — why is a `bytes` that is `True` refused when `True` is an int?
    Because `bool` is a subclass of `int` in Python, and the subtraction that
    makes `True == 1` is exactly the kind of accident this course exists to refuse.
    A byte count is a count of bytes the world's record reported, never a flag;
    accepting `True` would let `bytes=True` write `bytes=1` into the audit, and a
    reader comparing two runs would find them equal for the wrong reason. The same
    rule is applied to the tick: every number in this course is an int, and a bool
    that walks in through `isinstance` is refused by name rather than silently
    kept as the one it happens to equal.

DESIGN DECISION — why does `parse_line` validate too, instead of only splitting?
    Because it is the gate on the *other* side: a line read from a sink is text
    somebody else could have written, and the reader is what decides against it in
    stages 9 and 10. A reader that only splits would hand a decision, a reason or
    a negative count straight into the report, so it re-validates exactly what
    `line` guarantees — the field count, the keys at their own indices, the two
    closed vocabulary words, and both counts — and refuses, by index and by text,
    anything the writer would not have produced. The index is the field's own
    position, so the refusal points at the token that is wrong rather than at the
    line as a whole.

DESIGN DECISION — why does `write_line` return the sink's own count and never
re-read the sink?
    Because the count is the sink's answer, not the writer's opinion: the world's
    `Audit.record` appends and returns how many lines it now holds, and a writer
    that re-read the sink to count would be asking the world a second question
    with a different answer the moment two writers interleave. It also builds the
    text with `line` and nothing else, so a malformed line is impossible to
    append: the validation that refuses a bad field is the same code that formats
    a good one, which is the only way "it never writes a line it would not read"
    is a fact about the code rather than a hope about the caller.

TODO: implement `line`, `parse_line` and `write_line`.
"""

#: The seven reasons a decision can carry, in the order a line writes them. The
#: vocabulary is closed on purpose — a free-text reason is a reason nobody can
#: count — and its first member is `granted`.
REASONS = ("granted", "unknown", "capability", "jail", "host", "limit", "secret")

#: The two decisions, in the order a line writes them.
DECISIONS = ("allowed", "denied")

#: The seven fields a line carries, in the order a line writes them. Every one of
#: them is always written: a line a reader has to guess at is not an audit.
AUDIT_KEYS = ("tick", "principal", "tool", "target", "decision", "reason", "bytes")


class SandboxError(ValueError):
    """The course's one refusal family, as `stage_01` declares it.

    Every stage derives its own refusal from this one (`ToolError`, `GrantError`,
    `JailError`, `HostError`, `LimitError`, `SecretError`, `AuditError` here, then
    `CallError`, `ReportError` and stage 10's `RunError`), so a caller can catch a
    broken course with one `except SandboxError` and still read a narrower
    `except` at the site that knows what it is doing.
    """


class AuditError(SandboxError):
    """A line, a field or a vocabulary entry this stage refuses.

    The refusal names the offender — the tick, the byte count, the target, the
    field at its index, the decision or the reason — and, when the offender is a
    decision or a reason within edit distance two of a real word, that word too,
    because this is exactly the vocabulary where a typo silently becomes a value.
    """


def line(tick, *, principal, tool, target, decision, reason, bytes):
    """One audit line: every key, in `AUDIT_KEYS` order, and no trailing space.

    `tick` and `bytes` are non-negative ints (a bool is not a byte count),
    `principal` and `tool` are non-empty `str`s with no whitespace, `target` is a
    `str` with no whitespace (an empty one is spelled `-`), and `decision` and
    `reason` are drawn from `DECISIONS` and `REASONS` — each refusal naming the
    field and the offender, with the nearest word within `_NEAR = 2` for a
    decision or a reason.
    """
    raise NotImplementedError("stage 7: implement line()")


def parse_line(text):
    """The inverse of `line`: a mapping over `AUDIT_KEYS`, or a refusal.

    Refuses a `text` that is not a `str`, a line whose field count or keys differ
    from `AUDIT_KEYS` (naming the index and the text), a decision or a reason
    outside its tuple, a `bytes` that is not a non-negative int, and a target that
    is empty rather than spelled `-`. A `-` target reads back as `""`, and the
    returned mapping carries exactly `AUDIT_KEYS`, in that order.
    """
    raise NotImplementedError("stage 7: implement parse_line()")


def write_line(audit, entry):
    """One line built by `line`, appended through the sink, and its new count.

    `entry` is a mapping over `AUDIT_KEYS` — a field outside it is refused by
    name, and a field it omits is refused too, because every key is always
    written. The text is built with `line`, so a line this stage would refuse to
    parse is a line it will not append, and the return value is the count
    `Audit.record` reports rather than the sink read back a second time.
    """
    raise NotImplementedError("stage 7: implement write_line()")
