"""Queue & Workers From Scratch — stage 6: Retries, backoff on the injected
clock, and the poison task.

Stage 4 gave a failed or died ticket straight back to `pending` with
`ready_at = None`, and stage 3 then calls it due at once: nine failures buy ten
attempts in a row, one tick apart, and a task that can never succeed is
dispatched forever. This stage owns the missing half of that policy — *when* the
next attempt is allowed, and the moment the queue stops trying. The whole stage
is still a data structure: `backoff` is a pure function of the attempt number,
`requeue` writes a future `ready_at` on the queue's injected clock, and nothing
sleeps. A retry is an ordinary pending ticket that is simply not due yet.

DESIGN DECISION — why is the wait a pure function of the attempt number instead
of a real delay (`time.sleep`, a wall clock, or a timestamp)?
    A sleep reads as the obvious way to say "wait before trying again", and it
    costs the three properties this course is built on: it blocks the only
    thread there is, so one slow retry stalls every other task; it makes the run
    depend on how fast the machine happens to be, so two runs of the same inputs
    no longer produce the same bytes; and it puts a second clock in the system,
    so no check can advance time and assert what happens at tick 5. `backoff(n)
    -> int` keeps the decision "when may this run" as data, and the scheduler
    that owns the clock is the only thing that ever moves it.

DESIGN DECISION — why is `attempt` 1-based, and why is `backoff(0)` refused
instead of answered?
    An off-by-one here is invisible: the schedule still grows, the tests still
    pass, and every retry is simply one wait late. A 0-based reading of "the
    attempt that is about to happen" is the natural mistake, and it is the one
    that answers `2 ** -1 == 0.5` for the first retry — a float, which this
    course bans outright, and which would make a retry due a tick *before* it
    failed. Refusing `n < 1`, with the number in the message, makes the counting
    convention impossible to get wrong silently.

DESIGN DECISION — why does `requeue` dead-letter the task itself, instead of
always scheduling a retry and leaving the budget check to the caller?
    Splitting the two looks more flexible: the caller knows the reason and can
    decide when to give up. But then two pieces of code must agree on `attempts
    >= task.attempts`, and the failure mode is silent — a caller that forgets
    re-queues a task whose budget is spent, forever, and nothing in the record
    says why the pool is spinning. One function, one boundary: `requeue` either
    returns the retried ticket or the dead letter, so "there is no next attempt"
    cannot be missed.

DESIGN DECISION — why does the retry path remove the ticket it is about to
re-add, and why does `dead_letter` remove a ticket that is still pending?
    The shorter version assumes the caller already took the ticket out of the
    queue, and it is wrong twice over. Stage 4's `complete` puts the failed
    ticket back into `pending` by itself, so a `requeue` that only appends
    leaves the same task queued twice: it is dispatched twice and its attempt
    count runs away. And a task dead-lettered while it still sits in `pending`
    — which is exactly what a shed policy does — would be given up on *and*
    still waiting for a slot, so it runs again after the record says it is done.
    Matching on `ticket.seq` (the one field a requeue does not change) makes
    both re-add paths idempotent.

DESIGN DECISION — why is the attempt count carried on the ticket rather than on
the flight?
    The flight is the natural home for "what is running now", and it is dropped
    the instant the attempt ends — precisely when the retry needs the count. A
    count kept there is lost at the moment it matters, so `attempts >=
    task.attempts` can never be true and the task is retried forever. The ticket
    outlives the attempt: it comes back with `attempts + 1`, and the next flight
    is built from it with the next attempt number.

DESIGN DECISION — why does `due` filter stage 3's service order rather than
`queue.pending`'s arrival order?
    `pending` is the arrival record — the list a submit appends to and a requeue
    re-appends to — and its order is stale the moment a ticket is requeued to
    the tail. A dispatcher that consumed `due` in that order would serve the
    oldest arrival rather than the highest-order due ticket, and would disagree
    with `pick_next` about the very same queue. Running the filter over `reorder`
    costs one sort and makes `due` the eligibility view of the order the rest of
    the scheduler already uses.

TODO: implement `BACKOFF_BASE`, `backoff`, `due`, `dead_letter` and `requeue`.
"""

import fleet

#: The multiplier of the retry schedule: the attempt after attempt `n` waits
#: `BACKOFF_BASE ** (n - 1)` ticks.
BACKOFF_BASE = 2


def backoff(attempt):
    """How many ticks the attempt that follows `attempt` waits. 1-based.

    `backoff(1)` is a single tick and the wait doubles from there; an `attempt`
    that is not an int count, or is less than 1, is refused with the value.
    """
    raise NotImplementedError("stage 6: implement backoff()")


def due(queue):
    """The pending tickets that may start now, in the queue's service order."""
    raise NotImplementedError("stage 6: implement due()")


def dead_letter(queue, ticket, reason):
    """Give up on `ticket`: record it in `queue.dead` with `reason`, and stop.

    The task leaves `pending` if it was still there, and the `dead_lettered`
    event is appended. Returns the `DeadLetter`.
    """
    raise NotImplementedError("stage 6: implement dead_letter()")


def requeue(queue, ticket, *, reason):
    """One finished attempt that did not succeed: retry it, or give it up.

    The retry carries `attempts + 1` and is scheduled `backoff(attempts)` ticks
    after `queue.clock.now()`; when that count reaches the task's own `attempts`
    the task is dead-lettered instead. Returns the retried `Ticket` or the
    `DeadLetter`.
    """
    raise NotImplementedError("stage 6: implement requeue()")
