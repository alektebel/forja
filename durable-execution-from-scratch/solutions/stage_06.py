"""stage_06.py — crash, and the process that comes after it.

A kill is a `crash()` the caller performs, and the disk is the only channel
between the process before it and the process after it. So this stage fixes what
the second process may believe: everything the first one wrote and never synced
is gone, and a recovery that folds the *volatile* log — or the line list the
caller still has in memory — is the failure the whole course is about.

Two functions, one fold:

    crash       perform the kill, re-read `disk.synced`, write the `expire`
                lines the dead owners are owed, and return (lost, lines, states)
    recovered   the same fold from the disk alone, reading nothing volatile
"""

from disk import DEFAULT_JOURNAL
from stage_01 import DurableError, JournalError, parse_line, write_line

#: How many ticks of grace a lease that passed its deadline is given before its
#: owner counts as dead — stage 5's `MAX_MISSES`, restated here because a stage
#: imports stage 1 and the provided world and never a sibling stage.
MAX_MISSES = 2


class RecoveryError(DurableError):
    """A journal a recovery refuses: a torn tail, a line it cannot parse, or a
    tick that is not a tick.

    Every refusal names the offender — the index and the text of the line, the
    tick — because a recovery that guesses is the failure this stage refuses and
    a message that does not say *where* leaves the caller guessing too.
    """


def _require_now(now):
    """A recovery tick: a real int, not negative, and not the flag `True`."""
    if isinstance(now, bool) or not isinstance(now, int) or now < 0:
        raise RecoveryError(
            "a recovery at now=%r is not a tick: `now` must be a non-negative "
            "int, and a bool is not a number however much it looks like one"
            % (now,))
    return now


def _lines(text, path):
    """The lines a synced text holds, parsed, in order.

    A text whose last line has no terminator was never finished being written:
    that is the index a refusal names, and it is a *question*, never a repair —
    a recovery that silently drops the tail is one that silently drops a
    decision, and stage 8 owns the only function in the course that edits a log.
    """
    if not text:
        return ()
    parts = text.split("\n")
    if parts[-1]:
        raise RecoveryError(
            "the journal at %r has a torn tail at line %d: %r — a line without "
            "its terminator is a write that never finished, and a recovery that "
            "guesses at it is the failure this stage refuses"
            % (path, len(parts) - 1, parts[-1]))
    parsed = []
    for index, raw in enumerate(parts[:-1]):
        try:
            parsed.append(parse_line(raw))
        except JournalError as broken:
            raise RecoveryError(
                "the journal at %r has a line %d a recovery cannot parse: %r "
                "(%s)" % (path, index, raw, broken)) from broken
    return tuple(parsed)


def _survivors(disk, path):
    """What a crash would keep at `path`, parsed — never what `read` shows.

    `disk.synced` is the one method a process that woke up after a crash may
    believe; `disk.read` is what the crashed process believed, and believing it
    is exactly the mistake this stage exists to refuse.
    """
    return _lines(disk.synced(path), path)


def _lease(entry):
    """The lease a `claim` line takes: its owner, the tick it was claimed at, and
    the deadline the line's own lease length sets.

    A claim without `ticks` claims for zero ticks — a real line always carries
    one, and the log is the answer rather than a default of the reader's.
    """
    return {"job": entry["job"], "owner": entry["owner"],
            "claimed_at": entry["tick"],
            "deadline": entry["tick"] + entry.get("ticks", 0)}


def _dead(lease, now):
    """Stage 5's policy: a lease that passed its deadline is dead at `now` once
    it has missed `MAX_MISSES` ticks of grace.

    The grace is the difference between "slow" and "gone": in between, the owner
    may still be about to write a beat, and a recovery that takes a lease that
    is merely late is a second worker rather than a recovery.
    """
    return now >= lease["deadline"] + MAX_MISSES


def _finished(entry):
    """What a `result` line finishes a job as.

    `ok` is `done`; `failed` and `died` are both `failed`, whichever owner the
    line spells — a result is the attempt's answer, not the lease's. The
    worker's own detail travels with the state when the line carried one:
    contract §3.2 reads a record's `text` only for `done` and `failed`.
    """
    status = "done" if entry["status"] == "ok" else "failed"
    if "text" in entry:
        return {"status": status, "text": entry["text"]}
    return status


def _fold(lines, *, now):
    """The state table these lines yield, and the dead owners they leave owed an
    `expire` line: `(states, due)`.

    One pass in the order the lines were written keeps one record per job: a
    `claim` takes the lease and clears whatever finished the job earlier (a
    re-claim is a new attempt), a `beat` by the lease's own owner moves its
    deadline, a `result` finishes the job and clears the lease, a `retry`
    re-issues it (nothing holds it, nothing finished it), and an `expire` is
    believed only while no `result` has finished the job and only for the owner
    that still holds the lease — a `done` overwritten by a later `expire`, or a
    stale expire for an owner who no longer holds anything, is a state the log
    never decided.
    """
    records = {}
    for entry in lines:
        job_id = entry.get("job")
        if job_id is None:
            continue
        record = records.setdefault(
            job_id, {"lease": None, "finished": None, "expired": False})
        kind = entry["kind"]
        if kind == "claim":
            record["lease"] = _lease(entry)
            record["finished"] = None
            record["expired"] = False
        elif kind == "beat":
            standing = record["lease"]
            if standing is not None and entry["owner"] == standing["owner"]:
                standing["deadline"] = entry["tick"] + entry.get("ticks", 0)
        elif kind == "result":
            record["finished"] = _finished(entry)
            record["lease"] = None
        elif kind == "expire":
            held = record["lease"]
            if (record["finished"] is None and held is not None
                    and entry["owner"] == held["owner"]):
                record["expired"] = True
        elif kind == "retry":
            record["lease"] = None
            record["finished"] = None
            record["expired"] = False
    states = {}
    due = []
    for job_id in sorted(records):
        record = records[job_id]
        if record["finished"] is not None:
            states[job_id] = record["finished"]
        elif record["expired"]:
            states[job_id] = "expired"
        elif record["lease"] is None:
            states[job_id] = "pending"
        elif _dead(record["lease"], now):
            states[job_id] = "expired"
            due.append((job_id, record["lease"]["owner"]))
        else:
            states[job_id] = "running"
    return states, tuple(due)


def crash(disk, lines, *, now):
    """Kill the run, and believe only what survived the kill.

    `disk.crash()` discards the volatile buffer and reports what it threw away;
    the survivors are then re-read from `disk.synced`, so the `lines` a caller
    hands in — everything the crashed process believed — decide nothing. The
    recovery rule is folded over what survived: one `expire` line is written and
    **synced** for each dead owner whose job is still standing, in job-id order,
    because a decision a crash could lose is not a decision. The states are then
    read from the log as it stands. Returns `(lost, lines, states)`.
    """
    now = _require_now(now)
    lost = disk.crash()
    kept = _survivors(disk, DEFAULT_JOURNAL)
    _states, due = _fold(kept, now=now)
    written = []
    for job_id, owner in due:
        entry = {"tick": now, "kind": "expire", "job": job_id, "owner": owner}
        write_line(disk, entry)
        written.append(entry)
    if written:
        disk.sync()
    log = kept + tuple(written)
    states, _owed = _fold(log, now=now)
    return lost, log, states


def recovered(disk, *, now, path=DEFAULT_JOURNAL):
    """The states the process that comes after a crash may believe, from the
    disk alone.

    `disk.synced(path)` and never `disk.read`: a byte a crash would lose is not
    evidence, and the volatile buffer is not the log. Nothing is written — a
    reading here, an act in `crash` — so the states equal the states `crash`
    returns for the same disk, with the dead owners' jobs `expired` and the live
    owners' jobs still `running`.
    """
    now = _require_now(now)
    states, _due = _fold(_survivors(disk, path), now=now)
    return states
