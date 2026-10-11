"""Queue & Workers From Scratch — stage 5: the lease, and the worker that dies
holding the slot (implementation).

The reasoning behind the deadline, the sweep and the two ways a flight can end
lives in the template's docstring (`stage_05.py`); this file is only the body.
Nothing here reads a clock of its own: `sweep` asks the queue's injected `Clock`
what "now" is, and that clock is the only clock.
"""

import dataclasses

import fleet

#: How long a flight may run before the queue presumes the worker is gone.
#: Stage 4 stamps `deadline_at = started_at + lease` from the lease it is given;
#: this is the number the scheduler passes when the caller does not name one.
DEFAULT_LEASE = 8


def _reclaim(queue, ticket):
    """The ticket back in `pending`: one attempt spent, and due now.

    Immediate, never delayed: a lease that expired is a *liveness* signal, not a
    finished attempt waiting on a timer. Stage 6 owns the backoff and the
    dead-letter policy, so nothing here schedules and nothing here sleeps.
    """
    back = dataclasses.replace(ticket, attempts=ticket.attempts + 1, ready_at=None)
    queue.pending.append(back)
    return back


def sweep(queue):
    """Every flight past its lease, resolved as `died` — and back in `pending`.

    A flight is a lease on a slot: `deadline_at` is the tick by which the worker
    said it would be back with an outcome. A flight at or past that deadline,
    with no completion resolved in its place, is a task that never finished —
    the worker is gone. The flight goes, the ticket comes back one attempt
    older, the `died` event is appended, and the slot is free again: a worker
    that goes away must not take the task with it. Each outcome names the task
    id, the status and the attempt that never finished — the shape stage 4's
    `complete` answers in, with `died` instead of the worker's report.

    Ordered by `(deadline_at, seq)`: the earliest deadline first, the tie broken
    by arrival, so two runs over the same flights resolve them in one sequence.
    A `died` here is not a success the ticks say finished: the queue only knows
    what a worker told it, and this one told it nothing at all.
    """
    now = queue.clock.now()
    doomed = [flight for flight in queue.in_flight.values()
              if flight.deadline_at is not None and flight.deadline_at <= now]
    doomed.sort(key=lambda flight: (flight.deadline_at, flight.ticket.seq))
    outcomes = []
    for flight in doomed:
        task_id = flight.ticket.task.id
        del queue.in_flight[task_id]
        _reclaim(queue, flight.ticket)
        queue.events.append({"at": now, "kind": "died", "task": task_id})
        outcomes.append({"task": task_id, "status": "died",
                         "attempt": flight.attempt})
    return tuple(outcomes)


def _take(queue, task_id, verb):
    """The flight for `task_id`, removed from `in_flight` — or a refusal.

    An id the queue is not running is a `QueueError` naming it: `None` would
    travel three frames before anyone noticed, away from the cause, and an
    unguarded lookup would answer `KeyError`, which a caller cannot tell from a
    bug of its own.
    """
    flight = queue.in_flight.pop(task_id, None)
    if flight is None:
        raise fleet.QueueError(
            "%s(%r): the queue is not running that task" % (verb, task_id))
    return flight


def ack(queue, task_id):
    """Take a flight the worker finished with out of the queue.

    The normal path: the outcome is in hand, so the task is done and the ticket
    is handed back to the caller rather than put back in the queue. The task
    does not run twice and the slot is free.
    """
    return _take(queue, task_id, "ack").ticket


def release(queue, task_id):
    """Give a flight back: the task returns to `pending`, no attempt spent.

    A release is housekeeping, not a failure: the caller knows the attempt did
    not happen (or does not count it), so the ticket comes back due now with the
    attempt count it already had. Spending a retry here would let a rebalance
    dead-letter a task that never failed.
    """
    flight = _take(queue, task_id, "release")
    again = dataclasses.replace(flight.ticket, ready_at=None)
    queue.pending.append(again)
    return again
