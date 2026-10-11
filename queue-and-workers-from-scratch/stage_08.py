"""Queue & Workers From Scratch — stage 8: Ageing, and the tenant that never
gets served.

Stage 3 made the queue's order a function of the tickets: what a task is worth,
and when it arrived. That order is correct and it still starves somebody — a
tenant that keeps submitting at the top priority is served first every time,
and the task that arrived long ago and is worth little is served never. Ageing
is the *second* order: the same tickets and the same arrival tie-break, on a
priority that grows with how long the task has waited, so waiting buys a place
without buying the whole queue.

DESIGN DECISION — why is the boost a step every `AGE_STEP` ticks instead of one
priority point per tick waited?
    One point per tick is the shortest way to write "the longer you wait, the
    more you are worth", and it ages four times faster than the traffic does:
    the oldest ticket in a normal queue is then past the cap within a dozen
    ticks, so the cap — not the wait — is what decides the order, and the fresh
    interactive task is the one that starves. A step is the same rule with the
    rate made explicit: `AGE_STEP` is a dial, and the check can put a number on
    it.

DESIGN DECISION — why is the boost capped at 9 and not left to grow?
    An uncapped boost fixes the starvation by creating a second one: wait long
    enough and no fresh work can ever outrank you, so the knife simply points
    the other way and the interactive tenant now starves. Capping at the
    catalogue's top priority means ageing can *reach* the front of the queue but
    never pass it — an aged task ties with the top band, and the order's arrival
    tie-break settles the tie. On a fixed clock and a fixed arrival order that
    is deterministic; without the cap, the order grows without bound.

DESIGN DECISION — why does `waited` answer 0 for a `Flight` instead of the
ticket's age, and 0 when no clock is named?
    A running task is not waiting for anything: reading its submission time
    would report a growing wait for work that is already being served, and a
    scheduler that shed or aged on that number would be reordering on a
    quantity that means the opposite of what it says. And a caller that names no
    `now` has no clock at all — there is no queue here to ask — so the only
    honest answer is 0: a wait measured against a clock nobody named is exactly
    the second clock this course is about.

DESIGN DECISION — why is the aged tie settled by stage 3's `seq` rather than by
the id or by the pre-age priority?
    By id is stable-looking and wrong in the same way it was in stage 3: two
    runs that submit the same tasks in a different order would diverge, and a
    ticket that came back after a retry would sort back to its id. By the
    pre-age priority is worse than wrong — it silently removes the ageing: two
    tickets that the boost has just tied would fall back to the order ageing was
    introduced to overturn. The aged key is a *different* key with the *same*
    tail, so the two orders can never disagree about what arrival means.

DESIGN DECISION — why is `reorder_aged` a fresh tuple rather than a sort of
`queue.pending` in place?
    Sorting in place hands the queue's own arrival record back as the service
    order, so the next caller that reads `pending` sees the aged order instead
    of what came in when — the same mistake stage 3 rejected, and it costs one
    list copy per call to avoid. `pending` is the queue's *log*; the aged order
    is a *view* of it.

DESIGN DECISION — why does `starved` count only pending tickets, and compare
with `>` rather than `>=`?
    A ticket in flight is being served: it is the one case where the wait is
    over, and counting it makes the starvation report grow every time the queue
    does the right thing. The boundary is `>` for the same reason `ready_at <=
    now` is due: `limit` is the wait a task is allowed before it is called
    starved, so a ticket that waited exactly `limit` has not crossed it, and a
    report that flips one tick early is a report nobody can calibrate.

TODO: implement `waited`, `effective_priority`, `reorder_aged` and `starved`.
"""

import stage_02

#: How many ticks of waiting buy one step of priority.
AGE_STEP = 4

#: The wait, in ticks, past which a pending task is called starved.
AGE_LIMIT = 20


def waited(ticket, *, now=None):
    """How long `ticket` has been waiting, in ticks, on the caller's clock.

    A pending ticket has been waiting since it was submitted; anything else —
    a running task included — did not wait, and answers 0. A caller that names
    no `now` has no clock, and no clock means no elapsed wait: 0.
    """
    raise NotImplementedError("stage 8: implement waited()")


def effective_priority(ticket, *, now=None):
    """What `ticket` is worth now: its priority plus a step per `AGE_STEP` ticks
    waited, capped at the catalogue's top priority.
    """
    raise NotImplementedError("stage 8: implement effective_priority()")


def reorder_aged(queue, *, now=None):
    """The queue's pending tickets in aged service order, as a fresh tuple.

    The same tickets `reorder` orders, on the aged priority, with stage 3's
    `seq` tie-break; `queue.pending` is not touched and nothing in flight is
    pulled back in. `now` defaults to the queue's clock.
    """
    raise NotImplementedError("stage 8: implement reorder_aged()")


def starved(queue, *, now=None, limit=AGE_LIMIT):
    """The pending tickets that have waited longer than `limit`, in arrival order.

    In-flight tickets do not wait any more; a ticket that waited exactly `limit`
    has not crossed the line. `now` defaults to the queue's clock.
    """
    raise NotImplementedError("stage 8: implement starved()")
