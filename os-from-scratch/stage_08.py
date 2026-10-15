"""OS From Scratch — stage 8: Two CPUs, and the critical section nobody guarded.

One CPU makes every kernel mistake look like a kernel mistake: a step either
happened or it did not, and the order of a program's own steps is the order it
wrote them in. Two CPUs break that assumption without breaking anything else.
`load`, `add (one)`, `store` over a shared counter is correct code — each of the
three steps is — and two CPUs that interleave it lose an update every time: both
load the old value, both add one, both store it, and one of the two increments is
gone. Nothing raised, nothing faulted, no table is short a frame. The counter is
just wrong, and it is wrong *deterministically* here, because in this course the
interleaving is not a race: it is a schedule the caller hands over.

That is the whole design of this stage. A real SMP kernel cannot grade a spin,
because a spin is timing, and timing is not something a check can pin. So the
schedule is data — the frozen `(cpu, op, name)` steps of §2.4 — and the interesting
operation is `serialize`: walk the steps, and when a CPU reaches a lock somebody
else holds, *defer* that CPU's every step, rather than letting it spin, until the
holder releases. A spinning CPU and a deferred one reach the same state; only one
of the two can be written into a check.

    OPS               the six operations a schedule step may name
    Lock              one owner, a queue of waiters, and the refusals that keep it honest
    serialize         the effective order of a schedule, and how much each CPU deferred
    run_schedule      the lost update: the same schedule, with and without the lock
    detect_deadlock   the cycle in a set of waits, or the honest `None`
    audit_holds       the locks held across a `yield`, and the ones never released

`LockError` is the family: a recursive acquire, a release by a CPU that does not
own the lock, a step that is not a 3-tuple, an op this machine does not have, and
a lock name that is empty or not a `str`. Every refusal names the offender.

DESIGN DECISION — why does a blocked CPU get *deferred* instead of spinning?
Because a spin is the one thing this course cannot check. If cpu 1 spins on a lock
cpu 0 holds, the point at which it finally gets the lock is a property of how the
two are interleaved in time, and time is exactly what the course refuses to have:
no threads, no wall clock, no `random`. Deferring replaces the spin with a rule —
this CPU's remaining steps happen at the moment the lock is released — and a rule
is the same on every machine, so the lost update becomes reproducible from the
schedule alone and the check can pin the whole order.

DESIGN DECISION — why does the *whole* tail of a blocked CPU defer, not just its
`lock` step?
Because a CPU that is spinning has not advanced at all. Suppose only the `lock`
deferred and the `load`, `add`, `store` after it ran early: the counter would come
out right for the wrong reason, and the very bug the stage exists to show would
hide behind a half-correct rule. A blocked CPU is one that has stopped, so every
step it would have taken is queued, in its original order, and replayed at the
release — and a deferred `lock` that now finds the lock free takes it.

DESIGN DECISION — why is a recursive acquire refused rather than allowed?
An `acquire` by the CPU that already holds the lock is the one call whose intent
the kernel cannot read: it is either a nested critical section, which needs a
count and a rule about how many releases it takes, or it is a CPU about to deadlock
against itself, which needs to be told now. This course will not pick a reentrancy
policy silently for the caller, so the call raises and names the lock and the CPU,
and a lock a CPU already holds is a lock it must not ask for again.

DESIGN DECISION — why does the cycle come back closed, starting at the lowest CPU?
So that two runs that describe the same deadlock produce the same tuple. A cycle
written as a path — `(1, 2, 3)` or `(2, 3, 1)`? — differs by where the walk began,
and a check that pins it would be pinning the walk instead of the deadlock. The
front door is the lowest CPU id and the last element repeats the first, which is
what makes the shape self-describing: a closed cycle of one is `(5, 5)`, and that
is exactly the CPU waiting for the lock it already holds.

DESIGN DECISION — why is a lock held across a `yield` a finding, and one held
across a `load` not?
Because the danger is not that the lock is held, it is that the holder has stopped
running. A `load` is the holder making progress; the lock is doing its job. A
`yield` is the holder handing the CPU over with the lock still in hand, which is
the big-kernel-lock bug: everybody else waits for as long as the holder is away,
and the trace ends with the same problem for the locks nobody ever released.

TODO: implement `Lock`, `serialize`, `run_schedule`, `detect_deadlock` and
`audit_holds`.
"""

import machine

OPS = ("load", "add", "store", "lock", "unlock", "yield")


class LockError(ValueError):
    """A lock or a schedule used in a way no kernel in this course allows."""


class Lock:
    """One owner, a queue of waiters, and an acquire that never spins."""

    def __init__(self, name):
        raise NotImplementedError("stage 8: implement Lock.__init__()")

    def acquire(self, cpu):
        """Take the lock for `cpu`, or say that it is held and who holds it.

        The answer is `{"cpu", "acquired", "owner", "waiting"}`: a CPU that finds
        the lock free owns it, and one that finds it held is queued in `waiting`
        and told who to wait for. A CPU that already owns the lock is refused.
        """
        raise NotImplementedError("stage 8: implement Lock.acquire()")

    def release(self, cpu):
        """Give the lock up, handing it to the first waiter, if there is one.

        Only the owner may release: a CPU that does not own the lock, and a lock
        that is already free, are both refused by name.
        """
        raise NotImplementedError("stage 8: implement Lock.release()")

    def owner(self):
        """The CPU that holds the lock, or `None` when it is free."""
        raise NotImplementedError("stage 8: implement Lock.owner()")

    def waiting(self):
        """The CPUs queued on the lock, in the order they were refused it."""
        raise NotImplementedError("stage 8: implement Lock.waiting()")


def serialize(schedule):
    """The effective order of a schedule, and how much each CPU deferred.

    `{"order", "deferred", "acquired"}`: `order` is the steps in the order they
    really happen, `deferred` is the number of steps each CPU in the schedule had
    to wait, and `acquired` is the CPUs that took each lock, in that order.
    """
    raise NotImplementedError("stage 8: implement serialize()")


def run_schedule(schedule):
    """The lost update: the counter the schedule scores, and how it got there.

    Every CPU does `load`, `add` (one), `store` over one shared counter. The same
    schedule without the lock steps loses an update and with them does not; the
    answer is `{"counter", "order", "deferred"}`.
    """
    raise NotImplementedError("stage 8: implement run_schedule()")


def detect_deadlock(waits):
    """The cycle in a set of `(cpu, holding, waiting_for)` triples, or `None`.

    The cycle is closed and starts at its lowest CPU id, and a CPU waiting for a
    lock it already holds is a cycle of one. A wait that nobody's hold can close
    is not a deadlock and answers `None`.
    """
    raise NotImplementedError("stage 8: implement detect_deadlock()")


def audit_holds(trace):
    """Every `(cpu, lock)` held across a `yield`, and every lock never released.

    The trace is the frozen step tuples of §2.4; a lock held while its CPU merely
    loads, adds or stores is not a finding, because the holder is still running.
    """
    raise NotImplementedError("stage 8: implement audit_holds()")
