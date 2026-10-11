"""Queue & Workers From Scratch — stage 4: the concurrency limit, checked
before the worker starts.

SOLUTION. The reasoning lives in the template's docstring (`stage_04.py`); this
file is the body. Two things are worth repeating here because the code hangs
off them.

First, the limit is *data*: `free_slots` is a subtraction, and `start` answers
`None` when it is zero instead of raising, because "no slot right now" is the
normal state of a busy pool, not an error. What moves it is only ever
`queue.in_flight`, so the deadline of an unfinished flight is the only thing
that can return a slot.

Second, the flight lifecycle needs a place for the worker's answer. `Flight`
(§3, frozen, declared by stage 2) carries no status field, and the worker is
called exactly once per attempt — so `start` records the validated answer in a
private per-queue table and `complete` reads it back when the flight comes due.
Nothing here moves the clock: `started_at` is the clock's reading, and
`finishes_at` is that reading plus the ticks the worker reported.
"""

import dataclasses

import fleet
import stage_02
import stage_03

#: What a worker's answer must carry: exactly these three keys, no more.
OUTCOME_KEYS = ("status", "ticks", "detail")

#: The name of the per-queue table a started flight's answer waits in.
ANSWERS = "_answers"


class OutcomeError(fleet.QueueError):
    """A worker answered something that is not an outcome.

    It is a `QueueError`, so "the queue said no" stays one `except`. It is its
    own type because a worker that reports `"ok"` as a string is a different
    bug from a queue that is full, and a run that files the bad answer as a
    success is a run whose record lies.
    """


def validate_outcome(answer):
    """The worker's answer, or an `OutcomeError` naming what was wrong.

    Exactly `{"status", "ticks", "detail"}`: a status from `fleet.OUTCOMES`, a
    tick count that is a non-negative `int` (a `bool` is not an `int`, and
    neither is `"3"`), and a detail string. Nothing else is an outcome, and
    nothing here is trusted because it looked close enough.
    """
    if not isinstance(answer, dict):
        raise OutcomeError(
            "a worker's answer must be an outcome mapping, not %r: %r"
            % (type(answer).__name__, answer))
    if set(answer) != set(OUTCOME_KEYS):
        raise OutcomeError(
            "a worker's answer must carry exactly %r, got keys %r"
            % (list(OUTCOME_KEYS), sorted(answer)))
    if answer["status"] not in fleet.OUTCOMES:
        raise OutcomeError(
            "a worker's answer must have a status in %r, got %r"
            % (list(fleet.OUTCOMES), answer["status"]))
    ticks = answer["ticks"]
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise OutcomeError(
            "a worker's answer must have a non-negative int of ticks, got %r"
            % (ticks,))
    return answer


def free_slots(queue):
    """How many more flights the pool may run right now.

    `pool.max_concurrency - len(queue.in_flight)`: the running flights are the
    only thing a slot is spent on, so the dead letters and the waiting tickets
    do not enter the count.
    """
    return queue.pool.max_concurrency - len(queue.in_flight)


def _answers(queue):
    """The queue's private table of started-but-unresolved answers.

    One table per queue object, created on first use, so two queues sharing a
    process never share an answer — and so the frozen `Queue` of §3 keeps
    exactly the fields stage 2 declared.
    """
    table = getattr(queue, ANSWERS, None)
    if table is None:
        table = {}
        object.__setattr__(queue, ANSWERS, table)
    return table


def start(queue, worker, *, lease=None):
    """Start the next due ticket on `worker`, or `None` if it cannot start.

    `None` means "not now": either every slot is taken — counted in
    `decisions["limit_hits"]`, because a refused dispatch is a fact the record
    must carry — or nothing is due. The worker is called before anything has
    moved, so a worker that answers garbage leaves the queue exactly as it
    found it instead of eating the ticket it was handed.
    """
    if free_slots(queue) <= 0:
        queue.decisions["limit_hits"] += 1
        return None
    ticket = stage_03.pick_next(queue)
    if ticket is None:
        return None
    attempt = ticket.attempts + 1
    answer = validate_outcome(worker(ticket.task, attempt=attempt))
    queue.pending.remove(ticket)
    now = queue.clock.now()
    flight = stage_02.Flight(
        ticket=ticket, attempt=attempt, started_at=now,
        finishes_at=now + answer["ticks"],
        deadline_at=None if lease is None else now + lease)
    queue.in_flight[ticket.task.id] = flight
    _answers(queue)[ticket.task.id] = answer
    queue.events.append({"at": now, "kind": "started", "task": ticket.task.id})
    return flight


def _answer_of(queue, flight):
    """The answer `start` recorded for this flight; spent exactly once."""
    answer = _answers(queue).pop(flight.ticket.task.id, None)
    if answer is None:
        raise fleet.QueueError(
            "flight %r has no outcome recorded by start(), so completing it "
            "would file a status nobody reported" % (flight.ticket.task.id,))
    return answer


def complete(queue):
    """Resolve every flight that has finished by now, in `(finishes_at, seq)`.

    An `ok` flight is done: it leaves the queue with a `succeeded` line. A
    `failed` or `died` flight leaves its ticket behind with one more attempt
    spent and `ready_at = None` — due immediately, because the backoff and the
    attempt budget belong to stage 6, not here. The resolved outcomes come back
    in the order they were resolved, never in the dictionary's order.
    """
    now = queue.clock.now()
    finished = [flight for flight in queue.in_flight.values()
                if flight.finishes_at <= now]
    finished.sort(key=lambda flight: (flight.finishes_at, flight.ticket.seq))
    resolved = []
    for flight in finished:
        task_id = flight.ticket.task.id
        answer = _answer_of(queue, flight)
        status = answer["status"]
        del queue.in_flight[task_id]
        if status == "ok":
            queue.events.append({"at": now, "kind": "succeeded", "task": task_id})
        else:
            queue.pending.append(dataclasses.replace(
                flight.ticket, attempts=flight.attempt, ready_at=None))
            queue.events.append({"at": now, "kind": status, "task": task_id})
        resolved.append({"task": task_id, "status": status,
                         "attempt": flight.attempt})
    return tuple(resolved)
