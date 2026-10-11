"""Queue & Workers From Scratch — stage 3: priority as a total order, and the
tie that makes two runs differ (implementation).

The reasoning behind the key, the eligibility rule and the non-mutating
`reorder` lives in the template's docstring (`stage_03.py`); this file is only
the body. Nothing here reads a clock of its own: `pick_next` and `take_next` ask
the queue's injected `Clock` what "now" is, and that clock is the only clock.
"""


def order_key(ticket):
    """The total order over the queue: worth first, arrival second.

    `(-ticket.task.priority, ticket.seq)` — a higher priority sorts first, and
    two equal priorities are ordered by the sequence number the ticket was given
    when it was submitted. Never by the task's id, never by the tenant, and
    never by the order the ticket happens to sit in `pending` after a requeue.
    """
    return (-ticket.task.priority, ticket.seq)


def _due(ticket, now):
    """May `ticket` start at tick `now`?

    A ticket with no `ready_at` is due; a ticket whose `ready_at` is at or
    before `now` is due; a ticket whose `ready_at` is still in the future is
    not. The boundary is `<=` and not `<`: a retry that becomes ready at tick 5
    is due at tick 5, and waiting one more tick would be a bug that shows up only
    on the exact tick.
    """
    return ticket.ready_at is None or ticket.ready_at <= now


def reorder(queue):
    """Every pending ticket in service order — the delayed ones included.

    This is a fresh tuple: sorting it (or any copy of it) never touches
    `queue.pending`, whose order is the arrival record the retries and the dead
    letters are read from.
    """
    return tuple(sorted(queue.pending, key=order_key))


def pick_next(queue):
    """The first ticket in service order that is due now, or `None`.

    The highest-order ticket is not always the one to start: a ticket whose
    `ready_at` is in the future is passed over in favour of the next eligible
    one, and `pending` is left exactly as it was found.
    """
    now = queue.clock.now()
    for ticket in reorder(queue):
        if _due(ticket, now):
            return ticket
    return None


def take_next(queue):
    """`pick_next`, and remove the ticket it returned from `pending`.

    The ticket removed is the one that was picked, not the head of the list:
    `pending` is a list whose order is the arrival order, and its head is the
    oldest arrival, which is not what `pick_next` chose.
    """
    ticket = pick_next(queue)
    if ticket is not None:
        queue.pending.remove(ticket)
    return ticket
