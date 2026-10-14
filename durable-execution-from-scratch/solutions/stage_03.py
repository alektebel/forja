"""stage_03.py — replay, and the tail that was never finished.

Durable Execution From Scratch — stage 3: Replay, and the tail that was never finished

A run is not the process that started it; it is the log on disk. Stage 1 fixed
what a line *is*; this stage is the only reader that log will ever have. A
replay turns the text a disk holds into lines, a fold turns those lines into a
state table, and a question tells a log that was finished from one whose last
append never completed.

    ReplayError  what a line this reader cannot believe raises
    replay       the lines a disk holds, parsed, in order
    state_of     the state table a replay yields, id-sorted and fresh
    torn         where a half-written tail sits, or None — a question, no repair

DESIGN DECISION — why is a torn tail *refused* by `replay` instead of dropped?
    Because a line is only a line once it is terminated. Stage 1's `write_line`
    owns the `"\\n"`, so a text whose last piece was never terminated holds half
    a record: it may look complete (a crash between the text and its terminator)
    and it is not a line either way. Dropping it silently is the failure this
    stage names — the reader would fold a log it has quietly truncated and
    report a state built on a write that was never finished. It is refused
    instead, naming its index and its text, and nothing is repaired: `torn`
    answers *where* it is and stage 8 truncates it, because a repair is a write
    and a reader that writes is not a reader.

DESIGN DECISION — why does `torn` take the journal's raw lines, not the parsed
ones?
    Because the question is about the terminator, and a parsed line has already
    forgotten it. `replay` hands back field bags, and every one of them is a
    line that *was* finished; where the unfinished tail sits is a property of
    the text, so `torn` reads the text — a str, or the pieces `split("\\n")`
    produced — and answers with an index counted from zero, so `pieces[:index]`
    are the lines a replay can believe and `pieces[index]` is the tail. A
    journal that ended with its terminator splits to a final empty piece, and
    a blank tail is not torn: it is what a finished log looks like.

DESIGN DECISION — why does the *newest* claim decide a job's state instead of
the last line that names it?
    Because a state is a fold of decisions, and most lines are not decisions. A
    `beat` renames a deadline, an `intent` and an `effect` are about a key;
    none of them says who holds the job or how an attempt ended. So the fold
    walks the lines in order and keeps the last *decision* per job: a `claim`
    makes it `running`, a `result` makes it `done` or `failed`, a `retry`
    re-issues it as `pending`, an `expire` marks the dead owner's lease. A
    reader that took the last line, or the first claim it saw, would answer
    about a beat instead of about the lease, which is exactly the mistake the
    stage is written around.

DESIGN DECISION — why may an `expire` only end a *running* lease, and only its
own owner's?
    Because an expiry is the fingerprint of the owner that stopped answering,
    not a state anyone may assert. A job whose owner wrote its `result` is
    finished, and a later `expire` line cannot reach back past that — "`done`
    overwritten by a later `expire`" is the mistake this rule exists to catch.
    Nothing else is a running lease either: a `retry` has already re-issued the
    job, so the old owner's death is old news. The owner has to match for the
    same reason: the lease belongs to the line that took it.

DESIGN DECISION — why is a `done` or `failed` state a `{"status", "text"}`
record only when the deciding result carried a text?
    Because contract §3.2 reads a worker's own detail only for `done` and
    `failed`, and only when the worker spelled one — a `result` line's `text` is
    the one field stage 1 lets a result omit. So the table keeps J2's house
    shape without inventing a `None` a reader would have to special-case: a job
    whose result carried no detail is the plain status string, and one whose
    result did is the record. The detail kept is the *newest* result's, and it
    is read only when the newest decision about the job was a `result` — a job
    that was retried and re-claimed has moved on, and the state it has now is
    not `done` or `failed`, so no older attempt's detail can be reported as the
    outcome of the current one.
"""

from collections.abc import Mapping

from disk import DEFAULT_JOURNAL, Disk
from stage_01 import DurableError, parse_line

#: The nine kinds a line may be. Stage 1 owns this vocabulary but exports only
#: the field names, and a fold has to know which kind it is reading: a line
#: whose kind is not one of the nine is not a line this stage can fold, and the
#: refusal says so by name.
_KINDS = ("start", "claim", "beat", "intent", "result", "effect", "expire",
          "retry", "done")

#: The seven kinds that name a job. Everything else (`start`, `done`) is about
#: the run, not about a unit of work, which is why they never enter the table.
_JOB_KINDS = ("claim", "beat", "intent", "result", "effect", "expire", "retry")

#: What a `result`'s status says about the job: the worker's answer, mapped into
#: the state table's vocabulary. `died` is not a promotion of `failed` — an
#: attempt that produced no answer did not succeed, so the job is `failed`. The
#: six statuses are `pending`, `running`, `expired`, `done`, `failed` and
#: `skipped`; `skipped` belongs to a plan that decided a job will not run, and
#: no line of a journal says it, so this fold never produces it.
_RESULT_STATES = {"ok": "done", "failed": "failed", "died": "failed"}


class ReplayError(DurableError):
    """A line, a tail or a path a replay refuses.

    The refusal names the offender: the index of the line and its text, the
    path a disk refused, or the value a caller handed where a journal's lines
    belong. A line that does not parse is refused here with stage 1's own
    complaint appended, so the field that broke is still named.
    """


def replay(disk, path=DEFAULT_JOURNAL):
    """The lines the disk holds at `path`, parsed, in order.

    The text is split on the terminator stage 1's `write_line` owns: a journal
    that ended with one splits to a final empty piece, and a text that did not
    ends on the half-written tail a crash leaves behind. That tail is not a line
    — it was never finished — so it is refused, naming its index and its text,
    and nothing is repaired here. Every finished line is parsed by stage 1; a
    line that does not parse is refused naming its index and its text too.
    """
    if not isinstance(disk, Disk):
        raise ReplayError("a replay reads a disk, got %r" % (disk,))
    if not isinstance(path, str) or not path.startswith("/"):
        raise ReplayError(
            "a journal's path must be a non-empty str starting with '/', got %r"
            % (path,))
    pieces = disk.read(path).split("\n")
    if pieces[-1] != "":
        raise ReplayError(
            "the journal %s has a torn tail at line %d: %r was never finished, "
            "so it is not a line" % (path, len(pieces) - 1, pieces[-1]))
    entries = []
    for index, raw in enumerate(pieces[:-1]):
        try:
            entries.append(parse_line(raw))
        except DurableError as bad:
            raise ReplayError(
                "line %d of %s does not parse: %s" % (index, path, bad))
    return tuple(entries)


def state_of(lines):
    """The state table a replay yields, id-sorted and fresh.

    Every job the lines name is in the table, and no job the log never named is
    invented into it. The newest decision about a job decides its status: a
    `claim` makes it `running`, a `result` makes it `done` or `failed`, a
    `retry` re-issues it as `pending`, and an `expire` marks a lease whose
    owner stopped answering — only a *running* lease, and only its own owner's.
    A `beat`, an `intent` and an `effect` decide nothing. A `done` or `failed`
    state is a `{"status", "text"}` record when the deciding result carried the
    worker's detail, and the plain status otherwise.
    """
    if not isinstance(lines, (tuple, list)):
        raise ReplayError(
            "a state table is folded from a journal's parsed lines (a tuple), "
            "got %r" % (lines,))
    table = {}
    claimed_by = {}
    #: The newest `result` line's own detail per job. Only a `result` decides a
    #: `done` or `failed` status, so when this is read the status it belongs to
    #: is the deciding result's — no older attempt's detail can leak through.
    detail = {}
    for index, entry in enumerate(lines):
        if not isinstance(entry, Mapping):
            raise ReplayError(
                "line %d is not a parsed line, got %r" % (index, entry))
        kind = entry.get("kind")
        if kind not in _KINDS:
            raise ReplayError(
                "line %d is not a line of this journal: its kind is %r, and the "
                "kinds are %s" % (index, kind, ", ".join(_KINDS)))
        if kind not in _JOB_KINDS:
            continue
        job = entry.get("job")
        if not isinstance(job, str) or not job:
            raise ReplayError(
                "line %d is a %r line without a job, got %r" % (index, kind, entry))
        table.setdefault(job, "pending")
        if kind == "claim":
            table[job] = "running"
            claimed_by[job] = _owner_of(entry, index)
        elif kind == "beat":
            _owner_of(entry, index)
        elif kind == "expire":
            if table[job] == "running" and _owner_of(entry, index) == claimed_by.get(job):
                table[job] = "expired"
        elif kind == "result":
            status = entry.get("status")
            if status not in _RESULT_STATES:
                raise ReplayError(
                    "line %d is a result whose status is %r, not one of %s"
                    % (index, status, ", ".join(sorted(_RESULT_STATES))))
            table[job] = _RESULT_STATES[status]
            detail[job] = entry.get("text")
        elif kind == "retry":
            table[job] = "pending"
        # `intent` and `effect` decide nothing: a key and an effect are stage
        # 7's, and a job's status is who holds it and how the attempt ended.
    states = {}
    for job in sorted(table):
        status = table[job]
        text = detail.get(job)
        if status in ("done", "failed") and text is not None:
            states[job] = {"status": status, "text": text}
        else:
            states[job] = status
    return states


def _owner_of(entry, index):
    """The owner a `claim`, a `beat` or an `expire` must name, or a refusal."""
    owner = entry.get("owner")
    if not isinstance(owner, str) or not owner:
        raise ReplayError(
            "line %d is a %r line without an owner, got %r"
            % (index, entry.get("kind"), entry))
    return owner


def torn(lines):
    """Where a half-written tail sits in a journal's lines, or `None`.

    `lines` is a journal's lines — its text (a str, split on the terminator), or
    the pieces that split produced. A journal that ended with its terminator
    splits to a final empty piece and has no tail; a non-empty final piece was
    never finished, and this answers with its index, counted from zero, so
    `pieces[:index]` are the lines a replay can believe and `pieces[index]` is
    the tail. It is a question: it reads and changes nothing, and a blank tail
    is not torn — it is what a finished journal looks like.
    """
    if isinstance(lines, str):
        pieces = lines.split("\n")
    elif isinstance(lines, (tuple, list)):
        pieces = list(lines)
        for index, piece in enumerate(pieces):
            if not isinstance(piece, str):
                raise ReplayError(
                    "line %d of a journal is not text, got %r" % (index, piece))
    else:
        raise ReplayError(
            "a journal's lines are its text (a str) or the pieces it splits "
            "into (a tuple of str), got %r" % (lines,))
    if not pieces or pieces[-1] == "":
        return None
    return len(pieces) - 1
