"""Queue & Workers From Scratch — stage 9: The record, and the counters that
must come from the tickets

A run is over; what did it do? This stage is the answer, and the answer is the
log the run wrote — never a second tally kept beside it. Stage 2 opened the
run's log (`queue.events`) and every stage since appends its own line to it:
`submitted`/`refused` from admission, `admitted`/`shed`/`blocked` from
backpressure, `started` and `succeeded`/`failed`/`died` from the flights,
`retried`/`dead_lettered` from the budget. The queue's tables hold the
*present* — who is waiting, who is running, what was given up on — and the log
holds the *history*. `run_record` summarises the history; the tables contribute
only the one thing the history cannot give it, the depth right now.

`event` is the one writer of the log, so the line's shape and its twelve kinds
are enforced in one place; `run_record` is the one reader, and it reads nothing
else.

DESIGN DECISION — why is every counter derived from `queue.events` instead of
from `queue.decisions`?
    The decisions dict is right there, already counted, and it is the wrong
    source: it counts *intentions* at the moment the queue takes them, while the
    log records what actually happened, line by line. The two drift the first
    time a path bumps the dict and forgets the line (or the reverse), and the
    failure is silent — the record reports a run that never happened, and the
    bytes of two runs that did happen differently look identical. One source of
    truth: the log is counted, the dict is ignored.

DESIGN DECISION — why is `max_in_flight` rebuilt from the log instead of read
off `len(queue.in_flight)`?
    The table's length is the truth about *now*, and the peak is a fact about the
    past: a run that ran three flights at once reports zero the moment the last
    one lands. Reading the table is one line shorter and it makes "the pool never
    exceeded `max_concurrency`" unverifiable exactly when it matters; the pool's
    configured concurrency is the other guess, and it reports the limit rather
    than what the run did. So `started` puts a flight in the air and a resolution
    takes it down, over the log's own order.

DESIGN DECISION — why does `event` refuse a kind outside `EVENT_KINDS` instead
of writing the line anyway?
    Being permissive looks harmless: a later stage adding a kind would not have
    to touch this file. The cost is a log that can carry anything, which is a log
    that cannot be counted — the record's keys are the twelve kinds, so an
    unknown line is invisible in every counter, and a typo (`suceeded`) reads as
    a run with no successes instead of as a bug. The refusal names the kind and
    the twelve, so the typo is a failure at the moment it is written and not a
    silence three stages later.

DESIGN DECISION — why does `run_record` write the `stopped` line itself, through
`event`, and read it back out of the log instead of taking the reason on trust?
    The reason a caller hands in is a *claim*, and a record whose `stopped` field
    is a claim the log cannot corroborate is the record disagreeing with its own
    log — the one failure this stage exists to prevent. So the stop is a log fact
    like every other line: the record reads it off the log's last `stopped` line,
    and only a log that carries no stop at all is given the handed-in reason —
    written exactly once, through the same single writer every other line goes
    through. When the two disagree the log wins, because the record is derived,
    never declared. A drained run has no such line and reports `None`: a run that
    finished must not read as a truncation.

DESIGN DECISION — why is every `RUN_KEYS` key present and zero-filled instead of
only the kinds that happened?
    A record that carries only what happened needs every reader to ask for
    missing keys defensively, and the one reader that forgets turns a quiet zero
    into a `KeyError` on the metrics path. A fixed, ordered shape also makes two
    runs comparable key by key and byte by byte, which is what the next stage
    canonicalises.

TODO: implement `RUN_KEYS`, `event` and `run_record`.

    RUN_KEYS = ("pool", "tasks", "submitted", "admitted", "refused", "shed",
                "blocked", "started", "succeeded", "failed", "died", "retried",
                "dead_lettered", "max_in_flight", "final_depth", "ticks",
                "stopped")
                                 every key, in this order, always present.
    event(queue, kind, **fields) -> dict
                                 append `{"at": clock.now(), "kind": kind,
                                 "task": …, **fields}` and return it; a kind
                                 outside stage 2's `EVENT_KINDS` is refused with
                                 the kind in the message. The only writer of
                                 `queue.events`.
    run_record(queue, *, stopped=None) -> dict
                                 every `RUN_KEYS` key: the counters are the lines
                                 the log wrote (never `queue.decisions`) in
                                 RUN_KEYS order, `pool` the pool's id, `tasks`
                                 the distinct task ids the log names,
                                 `max_in_flight` the log's high-water mark of the
                                 flights in the air, `final_depth` the queue's
                                 depth now, `ticks` `clock.ticks`, and `stopped`
                                 the *log's* stop — the reason on its last
                                 `stopped` line, `None` for a drained run. A log
                                 that carries no stop is given the handed-in
                                 reason, written to the log once through `event`;
                                 when the two disagree the log wins.
"""

import fleet
import stage_02

#: Every key a run's record carries, in the order the record presents them.
RUN_KEYS = ("pool", "tasks", "submitted", "admitted", "refused", "shed",
            "blocked", "started", "succeeded", "failed", "died", "retried",
            "dead_lettered", "max_in_flight", "final_depth", "ticks", "stopped")


def event(queue, kind, **fields):
    """Append one line to `queue`'s log, at the queue's clock, and return it."""
    raise NotImplementedError("stage 9: implement event()")


def run_record(queue, *, stopped=None):
    """The run's record: every `RUN_KEYS` key, counted from the log."""
    raise NotImplementedError("stage 9: implement run_record()")
