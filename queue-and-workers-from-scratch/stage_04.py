"""Queue & Workers From Scratch — stage 4: The concurrency limit, checked
before the worker starts.

Stage 3 decided *which* ticket is next. Stage 4 decides *whether* it may start
at all, hands it to a worker, and takes it back when it finishes. The limit is
`pool.max_concurrency` flights at once, the ticket that cannot start stays
where it is, and every flight that a worker started has to come back to the
queue — with a status the worker actually reported, not one the queue hoped
for.

This is the first stage that reads the clock, and it still does not move it:
`started_at` is `clock.now()`, `finishes_at` is that plus the ticks the worker
reported, and only a later stage's scheduler advances anything.

DESIGN DECISION — why is the limit checked *before* the worker is called, and
why does `start` return `None` instead of raising?
    Calling the worker first and asking "was there a slot?" afterwards is the
    shape that always starts one task too many: the over-subscribed call has
    already happened, so the pool ran `max_concurrency + 1` tasks and the only
    thing left to do is apologise for it. `None` rather than a `QueueError`
    because a busy pool is not a broken one: "no slot right now" is the normal
    answer to a normal question, and a caller that had to catch an exception
    every tick would stop reading it as a signal. The refusal is not silent,
    either — `decisions["limit_hits"]` counts it, because "we wanted to start
    work and could not" is a fact the run's record has to carry.

DESIGN DECISION — why does `free_slots` count only the in-flight flights,
instead of the pending tickets, the dead letters, or the pool's capacity?
    `capacity` is how much work the queue will *hold*; `max_concurrency` is how
    much of it may *run at once*. Counting the waiting tickets against the
    running limit would stall the pool as soon as it had more queued work than
    slots, and counting the dead letters would shrink the pool every time a task
    was given up on — a limit that the queue's own history eats into. A slot is
    spent by exactly one thing: a flight that has started and has not been
    resolved. So the count is `max_concurrency - len(queue.in_flight)`, and the
    only way to get a slot back is to resolve a flight.

DESIGN DECISION — why is the worker's answer validated instead of trusted?
    The worker is written by somebody else and reports by convention. Filing
    whatever it returned — `{"status": "fine"}`, `"ok"` as a string, `-1` ticks
    — makes the bad answer a *success*: the queue appends `succeeded`, the
    record says the task worked, and nothing anywhere says that the one thing
    the queue was supposed to verify never happened. `-1` ticks is worse than
    wrong, it is backwards: the clock would be charged a negative cost and the
    run would finish before it started. So the answer is checked against
    `fleet.OUTCOMES` and a non-negative `int` of ticks (a `bool` is not an
    `int`), and anything else is an `OutcomeError` naming the offending field —
    never a `KeyError` from three frames away, and never a `succeeded` line.

DESIGN DECISION — where does the worker's answer live between `start` and
`complete`?
    §3 froze `Flight` without a status field, and the worker must be called
    exactly once per attempt — so the answer has to wait somewhere. Calling the
    worker a second time when the flight finishes is the tempting shortcut, and
    its cost is that every attempt is charged twice: a worker's `calls` count
    stops meaning "attempts made", and stage 6's retry check ("the task was
    attempted twice, not once and not three times") reads 4. Adding a field to
    `Flight` is the other shortcut, and its cost is that eight later stages read
    a shape this one changed. So the answer waits in a private table on the
    queue — one per queue instance, never a module global, so two queues in one
    process never share an answer — and `complete` spends it once.

DESIGN DECISION — why does a worker that answers garbage leave the queue
exactly as it found it?
    The ticket is picked, the worker is called, the answer is validated, and
    only then does the ticket leave `pending`. The alternative — take the
    ticket first, then call the worker — is one line shorter and it *loses*
    the ticket: the `OutcomeError` travels up and the task is in neither
    `pending` nor `in_flight`, which is the one thing every check in this course
    asserts is impossible. Nothing has moved when the answer is bad: no ticket
    taken, no flight recorded, no `started` line in the record.

DESIGN DECISION — why does `complete` resolve in `(finishes_at, seq)` order,
and why does a failed ticket come back rather than disappear?
    Iterating `queue.in_flight` resolves in dictionary order, which is
    insertion order *today* and an accident of hashing tomorrow: two runs of the
    same inputs would append their `succeeded` lines in different orders and the
    canonical bytes would differ, which is the failure the whole course exists
    to prevent. `(finishes_at, seq)` is the frozen order of §3 — the finish
    tick first, the arrival order for a tie. And a `failed` or `died` outcome
    does not end the task: the flight is dropped, but the ticket goes back to
    `pending` with one more attempt spent and `ready_at = None`, because an
    attempt that did not succeed is a fact about an attempt, not about the task.
    The backoff that would delay it and the attempt budget that would dead-letter
    it belong to stage 6; here the ticket is simply due again.

TODO: implement `validate_outcome`, `free_slots`, `start` and `complete`.

    validate_outcome(answer) -> dict
                                 exactly `{"status", "ticks", "detail"}`: the
                                 status in `fleet.OUTCOMES`, the ticks a
                                 non-negative int (`bool` is not an int), or an
                                 `OutcomeError` naming what was wrong.
    free_slots(queue) -> int     `pool.max_concurrency - len(queue.in_flight)`
    start(queue, worker, *, lease=None) -> Flight | None
                                 `None` when no slot is free — counting
                                 `decisions["limit_hits"]` — or when nothing is
                                 due; otherwise the next ticket by stage 3's
                                 order, `worker(ticket.task, attempt=…)`
                                 validated, then a `Flight` with `started_at =
                                 clock.now()`, `finishes_at = started_at +
                                 ticks`, `deadline_at = None if lease is None
                                 else started_at + lease`, and a `started` line.
    complete(queue) -> tuple[dict]
                                 every flight with `finishes_at <= clock.now()`
                                 in `(finishes_at, seq)` order: `ok` leaves a
                                 `succeeded` line; `failed`/`died` returns the
                                 ticket with `attempts + 1` and `ready_at = None`
                                 and leaves the matching line. Each result is a
                                 dict carrying at least `task`, `status` and
                                 `attempt`.
"""

import fleet

#: What a worker's answer must carry: exactly these three keys, no more.
OUTCOME_KEYS = ("status", "ticks", "detail")


class OutcomeError(fleet.QueueError):
    """A worker answered something that is not an outcome.

    It is a `QueueError`, so "the queue said no" stays one `except`. It is its
    own type because a worker that reports `"ok"` as a string is a different bug
    from a queue that is full, and a run that files the bad answer as a success
    is a run whose record lies.
    """


def validate_outcome(answer):
    """The worker's answer as an outcome, or an `OutcomeError` saying why not."""
    raise NotImplementedError("stage 4: implement validate_outcome()")


def free_slots(queue):
    """How many more flights the pool may run right now."""
    raise NotImplementedError("stage 4: implement free_slots()")


def start(queue, worker, *, lease=None):
    """Start the next due ticket on `worker`, or `None` if it cannot start."""
    raise NotImplementedError("stage 4: implement start()")


def complete(queue):
    """Resolve every flight that has finished by now, in `(finishes_at, seq)`."""
    raise NotImplementedError("stage 4: implement complete()")
