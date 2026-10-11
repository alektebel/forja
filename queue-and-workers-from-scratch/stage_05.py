"""Queue & Workers From Scratch — stage 5: The lease, and the worker that dies
holding the slot.

Stage 4 gave every flight a slot and a `deadline_at` stamped from the `lease=`
its `start` was handed — and left the lease optional, so a flight can also carry
no deadline at all. Stage 5 owns the number, and both ways a flight can end
without the queue having resolved it.

The whole stage rests on one distinction the module fixed at the top: **`died`
is not `failed`.** A `failed` outcome is a worker that finished and reported that
the work did not succeed. `died` is a worker that never finished at all — it went
away, and the slot it held is held for nobody. A queue that treats those the same
way leaks the slot forever, and the task rides off with the worker.

DESIGN DECISION — why is the deadline `started_at + lease` and not the flight's
`finishes_at`?
    Trusting the flight's own cost as the deadline is the shortest route to "the
    worker told us how long it would take", and it is exactly the value that
    must not be trusted: `finishes_at` is a *claim about the work*, made before
    the work happened, by the process that then went away. If the worker dies,
    nothing ever reaches `finishes_at`, so the flight is never resolved, the
    slot is never freed and the task is never requeued — the pool shrinks by one
    slot per death until it is dead. A lease is a claim about *liveness*: a
    separate number, chosen by the scheduler, that expires whatever the work
    said. The worker's estimate can be checked against it; it cannot *be* it.

DESIGN DECISION — why does a flight past its lease put the ticket back, instead
of dropping the task that died?
    "The worker is gone, so the task is gone" reads as tidier — one loss instead
    of a retry that will probably die the same way — and it makes the queue lie
    about what it knows: the queue has no outcome, so it cannot say the task
    failed, and if it drops the task anyway then `died` quietly means two
    different things in one run's record. Putting the ticket back costs the
    attempt the lease already spent, and it leaves the decision about poison to
    the place that owns it (stage 6's attempt limit and dead-letter policy). A
    worker's death is a liveness fact, not a verdict on the task.

DESIGN DECISION — why is the deadline boundary `<=` and not `<`?
    `<` reads as "strictly past the deadline, so it is certainly gone", which is
    the reading that makes a lease of 8 behave like a lease of 9: a flight whose
    deadline is *exactly* the current tick stays in flight for one more tick, and
    the pool sits idle at the precise tick the lease was scheduled to expire on a
    lease that never quite expires. The boundary is the same `<=` stage 3 uses for
    `ready_at`, for the same reason: at the tick something is due, it is due.

DESIGN DECISION — why is the sweep resolved in `(deadline_at, seq)` order
instead of the order the flight table happens to hold?
    Every other order in this course is a function of the data. Iterating
    `in_flight` is a function of the *history*: the dict remembers the order the
    dispatcher happened to start flights in, so two runs that took a different
    path to the same set of flights would append the `died` events in a different
    order — and the run's bytes would differ, which is stage 10's whole test.
    `(deadline_at, seq)` is the same shape as stage 4's `(finishes_at, seq)`, so
    a completion and a death are ordered by the same rule, and the tail is the
    arrival number the ticket already carries. The deadline decides who is dead;
    arrival decides only the tie.

DESIGN DECISION — why does `release` hand the ticket back *without* spending an
attempt, when the sweep's requeue spends one?
    Both put a ticket back, so one requeue helper for both is tempting — and it
    spends an attempt on a caller's housekeeping. The attempt count is the number
    of attempts *made*; a released flight's attempt did not happen, so counting it
    moves every task one step closer to the attempt limit for reasons the task had
    nothing to do with. A rebalance that releases ten tasks would then
    dead-letter a task that never failed. The sweep's requeue *does* spend the
    attempt, because that attempt was made and never reported.

DESIGN DECISION — why is an id the queue is not running a `QueueError` naming it,
instead of `None`?
    `None` is what a lookup that found nothing returns, and every caller here
    would then dereference it: `.ticket` on `None` fails three frames away from
    the id that was wrong, in a place that has no idea what id was meant. Worse,
    `None` cannot tell "never submitted" from "already resolved", which are
    different bugs with different fixes. A refusal naming the id puts the fact
    where the mistake is, and it travels as the queue's own `QueueError` — the
    same type every other refusal in this course uses, so a caller can tell the
    queue's complaint from its own.

TODO: implement `sweep`, `ack` and `release`.
"""

#: How long a flight may run before the queue presumes the worker is gone.
#: Stage 4 stamps `deadline_at = started_at + lease` from the lease it is given;
#: this is the number the scheduler passes when the caller does not name one.
DEFAULT_LEASE = 8


def sweep(queue):
    """Every flight past its lease, resolved as `died`, and back in `pending`.

    Returns the outcomes it resolved, in `(deadline_at, seq)` order, and frees
    the slots: the flight goes, the ticket comes back one attempt older and due
    now, and a `died` event is appended. Each outcome names the task id, the
    status and the attempt that never finished — stage 4's shape with `died`
    where the worker's report would be. A flight with no lease never expires.
    """
    raise NotImplementedError("stage 5: implement sweep()")


def ack(queue, task_id):
    """Take a flight the worker finished with out of the queue.

    Returns the flight's `Ticket`; the task does not go back to `pending`, and
    an id the queue is not running is a `QueueError` naming it.
    """
    raise NotImplementedError("stage 5: implement ack()")


def release(queue, task_id):
    """Give a flight back: the ticket returns to `pending`, no attempt spent.

    Returns the ticket it put back. Like `ack`, an id the queue is not running
    is a `QueueError` naming it.
    """
    raise NotImplementedError("stage 5: implement release()")
