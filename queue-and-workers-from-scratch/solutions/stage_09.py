"""Queue & Workers From Scratch — stage 9: The record, and the counters that
must come from the tickets

SOLUTION. A run is over; what did it do? The answer is the log it wrote, counted
— never a second tally kept beside it. Stage 2 opened `queue.events` and every
stage since appended its own line: `submitted`/`refused` from admission,
`admitted`/`shed`/`blocked` from backpressure, `started` and
`succeeded`/`failed`/`died` from the flights, `retried`/`dead_lettered` from the
budget. The queue's tables hold the *present* (who waits, who runs, what was
given up on); the log holds the *history*. So `run_record` reads the log for
every counter and the tables for exactly one thing the log cannot give it — the
depth right now — and `max_in_flight` comes from the log too, because a table's
current length can never show the most flights that were in the air at once.

`event` is the single writer of the log, so the line's shape and its twelve
kinds are enforced in one place; `run_record` is the single reader, and it reads
nothing else — the stop included, which it reads off the log rather than
declaring from its own argument.
"""

import fleet
import stage_02

#: Every key a run's record carries, in the order the record presents them.
RUN_KEYS = ("pool", "tasks", "submitted", "admitted", "refused", "shed",
            "blocked", "started", "succeeded", "failed", "died", "retried",
            "dead_lettered", "max_in_flight", "final_depth", "ticks", "stopped")

#: The log kinds that take a flight down: `started` puts one in the air and one
#: of these removes it, so the in-flight high-water mark can be rebuilt from the
#: log alone. A `failed` or `died` attempt still ends the flight that ran it.
_RESOLVED_KINDS = ("succeeded", "failed", "died")

#: The run-level kind: a line about the run, not about one task. A run-level
#: line names no task, so it is never counted as a task the run saw.
_RUN_KINDS = ("stopped",)


def event(queue, kind, **fields):
    """Append one line to `queue`'s log, stamped with the queue's clock.

    The line is `{"at": clock.now(), "kind": kind, "task": …}` plus whatever
    `fields` carries: the task is the caller's, or `None` for a run-level line
    such as `stopped`. A kind outside stage 2's `EVENT_KINDS` is refused with
    the kind in the message, because a log that can carry anything is a log
    that nothing can count. This is the only function that appends to
    `queue.events`; every line a run's record summarises was written here.
    """
    if kind not in stage_02.EVENT_KINDS:
        raise fleet.QueueError(
            "unknown event kind %r: a run's log carries only %r"
            % (kind, list(stage_02.EVENT_KINDS)))
    line = {"at": queue.clock.now(), "kind": kind,
            "task": fields.pop("task", None)}
    line.update(fields)
    queue.events.append(line)
    return line


def _peak_in_flight(lines):
    """The most flights that were in the air at once, rebuilt from the log.

    `started` puts a flight in the air and any resolution takes it down, so the
    running count over the log's own order is the in-flight depth tick by tick.
    The table's length is the count *now*: it reports zero the moment the last
    flight lands, whatever the run peaked at, so the peak can only come from the
    history.
    """
    running = 0
    peak = 0
    for line in lines:
        kind = line["kind"]
        if kind == "started":
            running += 1
        elif kind in _RESOLVED_KINDS:
            running -= 1
        if running > peak:
            peak = running
    return peak


def _logged_stop(lines):
    """The reason the log's last `stopped` line carries, or `None`.

    A stop is a log fact like every other line: whoever stopped the run wrote it
    (through `event`), and the record *reads* it. The last one wins, because a
    log that carries two stops was stopped twice and the later one is the one
    that ended the run.
    """
    reason = None
    for line in lines:
        if line["kind"] in _RUN_KINDS:
            reason = line.get("reason")
    return reason


def run_record(queue, *, stopped=None):
    """The run's record: every `RUN_KEYS` key, counted from the log.

    Every counter is the number of lines of that kind the run wrote — not the
    number it meant to write, and not a tally kept next to the log, because two
    sources of truth is how a record ends up disagreeing with the log it
    summarises. `pool` is the pool's id, `tasks` the number of distinct task ids
    the log names, `max_in_flight` the log's high-water mark of the flights in
    the air, `final_depth` the queue's depth from its tables now, and `ticks`
    what the clock spent. `stopped` is the *log's* stop — the reason on its last
    `stopped` line, `None` for a drained run — and only a log that carries no
    stop at all is given the handed-in reason, written once through `event`. The
    record is derived, never declared: when the two disagree, the log wins.
    """
    lines = list(queue.events)
    reason = _logged_stop(lines)
    if reason is None and stopped is not None:
        reason = stopped
        lines.append(event(queue, "stopped", reason=stopped))

    record = {key: 0 for key in RUN_KEYS}
    for line in lines:
        if line["kind"] in record:
            record[line["kind"]] += 1

    seen = {line["task"] for line in lines
            if line["kind"] not in _RUN_KINDS and line["task"] is not None}
    record["pool"] = queue.pool.id
    record["tasks"] = len(seen)
    record["max_in_flight"] = _peak_in_flight(lines)
    record["final_depth"] = queue.depth()
    record["ticks"] = queue.clock.ticks
    record["stopped"] = reason
    return record
