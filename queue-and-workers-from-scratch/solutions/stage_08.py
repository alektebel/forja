"""Queue & Workers From Scratch — stage 8: Ageing, and the tenant that never
gets served.

SOLUTION. Stage 3 fixed the queue's order as a function of the tickets — what a
task is worth, and when it arrived — and that order has one failure mode: a
tenant that keeps submitting at the top priority is served first every time, and
a task that arrived long ago and is worth little is served never. Ageing is the
*second* order: the same tickets, the same arrival tie-break, and a priority
that grows with how long the task has waited — capped, so that waiting is a
floor under the oldest work and not a licence to leapfrog everything. Stage 3's
`order_key` is not touched: the aged order is a different key, not a patched one.
Nothing here reads a clock of its own — `now` is handed in, or read off the
queue's injected clock when the caller has a queue — so the scheduler stays the
only thing that moves time.
"""

import stage_02

#: How many ticks of waiting buy one step of priority. A *step* and not a tick
#: is what keeps the boost slower than the arrival rate of a flood.
AGE_STEP = 4

#: The wait, in ticks, past which a pending task is called starved. It is a
#: report, not a policy: nothing in this stage sheds, refuses or dead-letters.
AGE_LIMIT = 20


def waited(ticket, *, now=None):
    """How long `ticket` has been waiting, in ticks, on the caller's clock.

    A pending ticket has been waiting since it was submitted:
    `now - ticket.submitted_at`. Anything else did not wait, and the one that
    matters is the in-flight one — a `stage_02.Flight` is a task that is
    *running*, its turn has come, so its wait is over: 0. A caller that names no
    `now` has no clock, and a wait measured against a clock nobody named is the
    second clock this course is about: 0.
    """
    if not isinstance(ticket, stage_02.Ticket) or now is None:
        return 0
    return now - ticket.submitted_at


def effective_priority(ticket, *, now=None):
    """What `ticket` is worth *now*: its priority plus a step per `AGE_STEP`
    ticks waited, capped at 9.

    The cap is the catalogue's top priority and the whole point: without it,
    any task that waits long enough outranks the interactive tenant forever, and
    the queue simply starves somebody else. With it, ageing lifts the oldest
    work to the front of its own band and leaves the order's arrival tie-break
    to settle the rest.
    """
    return min(9, ticket.task.priority + waited(ticket, now=now) // AGE_STEP)


def _aged_key(ticket, now):
    """The aged total order: worth-after-ageing first, arrival second.

    The tail is `ticket.seq` — the tie-break stage 3 fixed, unchanged. An aged
    tie is still settled by what arrived first: never by the id, never by the
    order the pending list happens to be sitting in after a requeue.
    """
    return (-effective_priority(ticket, now=now), ticket.seq)


def reorder_aged(queue, *, now=None):
    """Every pending ticket in *aged* service order, as a fresh tuple.

    The whole pending list — the delayed tickets included — ordered by
    `effective_priority` instead of the raw priority, with stage 3's `seq` tail.
    `queue.pending` is never touched, and nothing that is in flight is pulled
    back into the order. `now` defaults to the queue's clock.
    """
    now = queue.clock.now() if now is None else now
    return tuple(sorted(queue.pending, key=lambda ticket: _aged_key(ticket, now)))


def starved(queue, *, now=None, limit=AGE_LIMIT):
    """The *pending* tickets that have waited longer than `limit`, in arrival order.

    A running ticket is not starving — it is being served, and it is not in
    `pending` at all; a ticket that waited exactly `limit` is not starving
    either, because the boundary is `>`. `now` defaults to the queue's clock.
    """
    now = queue.clock.now() if now is None else now
    return tuple(ticket for ticket in queue.pending
                 if waited(ticket, now=now) > limit)
