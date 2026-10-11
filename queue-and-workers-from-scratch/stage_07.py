"""Queue & Workers From Scratch — stage 7: Backpressure: refuse, shed or
block, and never lose a task.

Stage 2 refuses only at `capacity`, so a producer that keeps offering work
fills every slot before anything says no. By then the pool is holding work it
cannot start for a long time, and the burst that arrives at that point is
either lost or left waiting behind the whole backlog. This stage owns the early
warning: a water mark already in the pool spec (`high_water`) and three ways to
hold the line when `depth()` reaches it — refuse the arrival, shed the least
valuable waiting task to make room, or block the producer.

Still a data structure: `admit` reads `queue.depth()` and the injected clock,
writes stage 2's tables, and returns the decision it took. Nothing sleeps,
nothing moves the clock, and the counters and the record grow at the moment the
decision is taken. The invariant the whole stage rests on: every input ends
admitted, dead-lettered with a reason, or refused naming why — nothing is
dropped in silence, and nothing is queued past capacity.

DESIGN DECISION — why one `admit(queue, task, *, policy=...)` instead of three
functions (`admit_refuse`, `admit_shed`, `admit_block`)?
    Three functions read as the more explicit interface, and they cost the one
    thing this stage is about: the *comparison* against the water mark would be
    written three times, so a fix to the boundary (`<` versus `<=`) reaches the
    confident implementation and misses the other two. Worse, "which policy"
    would stop being data — the run loop would need its own dispatch table and
    an unknown policy would surface as a `KeyError` or an `AttributeError`
    inside a runner instead of a refusal where the policies are known. One
    entry point resolves the policy once, refuses what it does not know, and
    makes the three answers comparable in a single test.

DESIGN DECISION — why is the mark compared against `depth()` instead of
`queued()` (the pending tickets alone)?
    `queued()` is the tempting number because it is the list the next task
    would go into, and it is wrong in exactly the case backpressure exists for:
    a pool of two workers running two long tasks has `queued() == 0` however
    full it feels, so the queue would keep accepting new arrivals past its mark
    and the producer would never be told no. The queue's room is the work the
    pool is *holding* — waiting plus running — which is what stage 2's `depth()`
    counts and what `capacity` is defined against.

DESIGN DECISION — why does `shed` give up the lowest-order *pending* ticket
rather than the newest arrival, the oldest one, or an in-flight task?
    The newest arrival is the cheapest line of code (`pending[-1]`) and the most
    expensive decision: it is the task that just passed validation, often the
    high-priority one, and it turns the policy into a race between submission
    order and the drop. The oldest arrival is no better: waiting is not a fault,
    and dropping the oldest punishes exactly the task that has been patient.
    An in-flight task cannot be given up at all — its worker is holding it, and
    dead-lettering it would leave the task running *and* recorded as finished.
    The lowest-order pending ticket is the one the queue would serve last, so
    shedding it costs the least; taking it from stage 3's `reorder` keeps the
    choice deterministic, with the tie broken by arrival and never by id or by
    list position.

DESIGN DECISION — why are the decision counters bumped at the point of the
decision instead of up front or read back out of the events?
    Bumping up front is the classic version: increment the policy's counter,
    then perform the action, then undo the count if the action failed — and the
    undo is the line that gets forgotten, so the run's record shows an admission
    that never happened. Deriving the counters from the events afterwards is the
    seductive alternative, and it makes the counters a second, subtly different
    tally (an event that is deliberately not logged, a decision taken in a
    helper) with no way to notice the drift. One increment, inside the branch
    that took the decision, keeps the counters and the record the same story.

DESIGN DECISION — why is "shed, but nothing is waiting to be shed" its own
refusal (`ShedError`) instead of quietly admitting the task or reusing
`QueueFull`?
    Quietly admitting is the silent bug: the queue grows past the mark with
    nothing given up, so the policy did nothing and nobody was told. Reusing
    `QueueFull` is the readable-looking alternative, and it costs the caller the
    distinction it needs: "the queue is at capacity" means try again shortly,
    while "everything the queue counts is running" means the wait is bounded by
    a completion, not by a slot in the backlog. A policy that cannot do what it
    was asked must say so, with a type the caller can act on.

DESIGN DECISION — why does `admit` leave validating the task to stage 2's
`submit` rather than checking it first?
    Checking first would mean two validators, and the second one is the one that
    drifts: a task spec the queue accepts today stops being accepted in the
    policy layer tomorrow, and the record then names a task the queue never
    took. The admitted path therefore goes in through the same door as every
    other task — `submit`, with its typo refusal, its arrival number and its
    `submitted` line — and the refusing paths, which create no ticket, only read
    the name off the task for the refusal they write.

TODO: implement `POLICIES`, `ShedError`, `BlockedError` and `admit`.
"""

import fleet

#: The three ways to answer a queue that has reached its water mark, in the
#: order the course lists them: refusing costs nothing the queue already
#: accepted, shedding gives up a waiting task, blocking makes the producer
#: wait.
POLICIES = ("refuse", "shed", "block")


class ShedError(fleet.QueueError):
    """The queue was asked to shed a task to make room and had none to give up.

    A separate type from `QueueFull`: the queue is at its mark and everything it
    counts is running, so the producer waits for a completion rather than for
    room in the backlog.
    """


class BlockedError(fleet.QueueError):
    """The queue is at its water mark and the producer is told to hold the task.

    Nothing is admitted — `block` back-pressures by refusal — and it is not
    `QueueFull`, because the queue is not out of room so much as unwilling to
    hand this wave any more of it.
    """


def admit(queue, task, *, policy="refuse"):
    """One task offered to the queue: admitted, shed for, or refused.

    Below `queue.pool.high_water` every policy admits, through stage 2's
    `submit`, and the decision is `"admitted"`. At or above the mark `refuse`
    raises `QueueFull`, `shed` gives the lowest-order pending ticket up through
    stage 6's `dead_letter` (reason `"shed"`) and then admits (returning
    `"shed"`), and `block` raises `BlockedError` and admits nothing. An unknown
    policy is refused naming the ones the queue knows. The counter for the
    decision is incremented where the decision is taken.
    """
    raise NotImplementedError("stage 7: implement admit()")
