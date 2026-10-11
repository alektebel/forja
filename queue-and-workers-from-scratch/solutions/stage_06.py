"""Queue & Workers From Scratch — stage 6: retries, backoff on the injected
clock, and the poison task.

SOLUTION. Stage 4 hands a failed or died ticket back to `pending` with
`ready_at = None`, and stage 3 then treats it as due immediately: a task that
fails nine times is dispatched ten times in a row, one tick apart, and a task
that can never succeed is dispatched forever. This stage owns the other half of
that policy — *when* the next attempt is allowed (a schedule on the injected
clock), and the moment the queue stops trying (the dead letter, with the reason
it gave up).

Nothing here sleeps and nothing here reads a wall clock. `backoff` is a pure
function of the attempt number; `requeue` reads `queue.clock.now()` and writes
`ready_at`; the only thing that ever moves that clock is the scheduler in a
later stage. A retry is therefore an ordinary pending ticket with a future
`ready_at`, and `due` is the one place that turns that number into "may start
now".
"""

import dataclasses

import fleet
import stage_02
import stage_03

#: The multiplier of the retry schedule: the attempt after attempt `n` waits
#: `BACKOFF_BASE ** (n - 1)` ticks. Two is the usual choice: one tick after the
#: first failure, two after the second — enough for a transient failure to clear,
#: not enough for a poison task to starve the pool while it burns its budget.
BACKOFF_BASE = 2


def backoff(attempt):
    """How many ticks the attempt that follows `attempt` waits. 1-based.

    `backoff(1)` is a single tick, and the wait doubles from there. It is a
    *function*, not a sleep: the caller adds it to the injected clock and the
    scheduler decides when the ticket becomes due. `attempt` is a 1-based count
    of attempts already made, so there is no schedule for attempt zero — asking
    for one is refused with the number, rather than answered with the
    `2 ** -1` that a 0-based reading would produce.
    """
    if isinstance(attempt, bool) or not isinstance(attempt, int):
        raise fleet.QueueError(
            "backoff() takes an int attempt number, not %r"
            % (type(attempt).__name__,))
    if attempt < 1:
        raise fleet.QueueError(
            "backoff() is 1-based and has no schedule for attempt %r"
            % (attempt,))
    return BACKOFF_BASE ** (attempt - 1)


def due(queue):
    """The pending tickets that may start now, in the queue's service order.

    A ticket with no `ready_at` is due; a ticket whose `ready_at` is at or before
    the clock is due; a retry still waiting on its backoff is not. This is a
    filter over stage 3's `reorder`, never over `queue.pending` directly:
    `pending` holds the arrival record, whose order goes stale the moment a
    ticket is requeued, and the dispatcher consumes tickets in service order.
    """
    now = queue.clock.now()
    return tuple(ticket for ticket in stage_03.reorder(queue)
                 if ticket.ready_at is None or ticket.ready_at <= now)


def _drop(queue, ticket):
    """Take the pending entry with `ticket`'s sequence number out, if it is in.

    A ticket's `seq` is the arrival it belongs to and never changes, so it is
    the one field that says "this is the same task, again" across a requeue —
    matching on it is what keeps a retry from queueing the task twice.
    """
    queue.pending[:] = [pending for pending in queue.pending
                        if pending.seq != ticket.seq]


def dead_letter(queue, ticket, reason):
    """Give up on `ticket`: record it in the DLQ, with `reason`, and stop.

    The task leaves `pending` if it was still there — a task the queue has given
    up on must not also be waiting for a slot, or it would be served after it was
    recorded as finished — and the record goes to `queue.dead`, which is where
    the run's record reads it from. This is a recorded outcome, not an error:
    the caller is handed the dead letter.
    """
    _drop(queue, ticket)
    letter = stage_02.DeadLetter(task=ticket.task, attempts=ticket.attempts,
                                 reason=reason, at=queue.clock.now())
    queue.dead.append(letter)
    queue.events.append({"at": queue.clock.now(), "kind": "dead_lettered",
                         "task": ticket.task.id, "attempts": ticket.attempts,
                         "reason": reason})
    return letter


def requeue(queue, ticket, *, reason):
    """One attempt that did not succeed: retry it, or give up on the task.

    `ticket.attempts` counts the attempts *made*, so the retry carries
    `attempts + 1`. If that reaches the task's own `attempts` budget, the queue
    stops trying and the task is dead-lettered; the dead letter is what `requeue`
    returns, because "there will be no next attempt" is the caller's answer too.
    Otherwise the retry is scheduled `backoff(attempts)` ticks after the injected
    clock's now, goes back to `pending`, and the `retried` event is written — the
    schedule is visible in the record, never implied by a sleep. The failure that
    brought the ticket here is not the ticket's own business, so `reason` is
    carried into the record rather than guessed at.
    """
    attempts = ticket.attempts + 1
    if attempts >= ticket.task.attempts:
        return dead_letter(queue,
                           dataclasses.replace(ticket, attempts=attempts),
                           reason)
    now = queue.clock.now()
    retried = dataclasses.replace(ticket, attempts=attempts,
                                  ready_at=now + backoff(attempts))
    _drop(queue, ticket)
    queue.pending.append(retried)
    queue.events.append({"at": now, "kind": "retried", "task": ticket.task.id,
                         "attempt": attempts, "ready_at": retried.ready_at,
                         "reason": reason})
    return retried
