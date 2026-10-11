"""Queue & Workers From Scratch — stage 3: Priority as a total order, and the
tie that makes two runs differ.

Stage 2 let the queue hold tickets; stage 3 decides which one runs next. The
whole course rests on that decision being a *function of the tickets*, never of
the order a Python list happened to be in when the sort ran: two runs of the
same pool over the same tasks must produce the same bytes, and a tie that
depends on anything but arrival is the shortest path to two runs that differ.

DESIGN DECISION — why is a tie broken by arrival (`seq`) and not by the task id?
    Sorting by `id` (or by any field of the task) looks strictly better — it is
    stable under any reordering, and it is already a total order — and that is
    exactly the trap. The id is not the arrival order: two runs that submit the
    same tasks in different orders would be ordered by the alphabet rather than
    by what happened, so a run is no longer reproducible from its inputs alone;
    and a ticket that comes back after a failed attempt would sort back to its
    id's place and starve the tickets that arrived behind it. Submitted order is
    the only tie-break the run itself can vouch for, so `seq` is the tail of the
    key.

DESIGN DECISION — why is the order a two-element key instead of a comparison
over the tickets themselves?
    A `key` that returns the ticket (or a comparator that compares tickets)
    reads as the most direct statement of "sort the tickets", and it fails on
    the only case that matters: two tickets of equal priority are equal in every
    field that could break the tie, and frozen dataclasses have no ordering, so
    the sort raises `TypeError` in the middle of a run. A key of two plain ints
    is total by construction, and it makes the tie-break explicit instead of
    leaving it to whatever the sort does with equal elements.

DESIGN DECISION — why does `reorder` return a fresh tuple rather than sorting
`pending` in place?
    Sorting in place is one line shorter and it destroys the arrival order that
    `pending` holds — the order the retry path and the dead-letter path read to
    answer "what came in when". A caller that receives the queue's own list can
    also reorder the queue by accident, from anywhere. Building a new tuple
    costs one list copy per call and buys the invariant that the only thing that
    ever changes `pending` is a `submit` or a `take_next`.

DESIGN DECISION — why is a ticket whose `ready_at` is in the future skipped
instead of being filtered out of the order?
    A retry that is not ready yet must not hold the head of the queue: if
    `pick_next` returned the head unconditionally, one backoff would stall every
    task behind it until the clock reached it, and the pool would sit idle with
    work to do. But the answer is not to drop the delayed ticket from `reorder`
    either: `reorder` is the whole pending list, and a caller asking "what is
    queued" must see the tasks that are waiting on the clock. The eligibility
    test belongs to the picker, not to the order.

DESIGN DECISION — why is the eligibility boundary `<=` and not `<`?
    `<` reads as "strictly before now, so it is certainly ready", which is the
    reading that makes a ticket due *exactly* at the current tick wait one more
    tick — a bug that is invisible whenever the clock happened to be ahead of
    the ticket, and that leaves the pool idle at the one tick the retry was
    scheduled for. A ticket due at or before `now` is due; the boundary is
    `<=`.

DESIGN DECISION — why does `take_next` remove the ticket by identity instead of
popping the head of the list?
    `pending.pop(0)` is the shortest way to say "hand me the front" and it is
    wrong the moment the list is not in service order: after a requeue, the head
    is the oldest arrival, so the queue would dispatch a ticket nobody picked
    and serve the picked one twice. Removing the object `pick_next` returned
    keeps the two functions in a single order.

TODO: implement `order_key`, `reorder`, `pick_next` and `take_next`.
"""


def order_key(ticket):
    """The sort key of one ticket: `(-ticket.task.priority, ticket.seq)`."""
    raise NotImplementedError("stage 3: implement order_key()")


def reorder(queue):
    """The queue's pending tickets in service order, as a tuple.

    The whole pending list, delayed tickets included; `queue.pending` is not
    touched.
    """
    raise NotImplementedError("stage 3: implement reorder()")


def pick_next(queue):
    """The first pending ticket that is due now, in service order, or `None`."""
    raise NotImplementedError("stage 3: implement pick_next()")


def take_next(queue):
    """`pick_next(queue)`, removed from `queue.pending` and returned."""
    raise NotImplementedError("stage 3: implement take_next()")
