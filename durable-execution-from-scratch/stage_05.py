"""Durable Execution From Scratch — stage 5: The heartbeat, and the worker that dies holding the slot.

A lease is a line, so "I am still alive" has to be a line too: a `beat` renames
the deadline the `claim` set. This stage writes that line, decides when the
silence after a deadline means the owner is gone rather than slow, and reads the
state that a process which has just woken up must believe — a reading, and one
that writes nothing at all.

    MAX_MISSES      how many beats an owner may miss before its lease is dead
    heartbeat       write a `beat` line and return the lease it renewed
    dead            the grace policy: is this lease dead, or only expired?
    recover         the state table a process that just woke up must believe
    reclaimable     the ids recovery may re-issue, sorted

Stage 4's `renew` catches a heartbeat from somebody else while one process is
running. Stage 5 is what is left when *nobody* is running: the owner that died
holding the slot, whose deadline passed and whose beats stopped coming.

DESIGN DECISION — why does `heartbeat` refuse a lease that is already expired?
    Because a beat is a claim to a slot you still hold. A `beat` line says "the
    lease of this owner on this job is still good"; once the deadline has passed
    there is no lease left to say that about, and a beat written then would
    quietly resurrect a slot another process may have taken — the failure this
    stage exists to catch. What the caller wants in that case is a `claim`,
    which is a *new* lease with a new `claimed_at`, not a renamed deadline on a
    lease that already ended. So the refusal names both ticks — the deadline it
    passed and the tick the beat was attempted at — because the caller's next
    line is a claim, and the number it needs is which of the two is which. The
    boundary is stage 4's: `deadline <= now` is expired, so a beat *at* the
    deadline is already too late.

DESIGN DECISION — why is `recover` a reading, with no `disk` argument at all?
    Because a recovery that writes is a recovery that can lie about what it
    found. Stage 6 writes the `expire` lines, and it writes them *after* this
    reading, over a log this function never touched; a `recover` that decided
    and wrote in the same pass would make "what the log says" and "what recovery
    decided" the same bytes, and then nothing could tell a recovery that read
    the log right from one that overruled it. The very shape of the signature is
    the guard: a function that has no disk cannot write to one by accident.

DESIGN DECISION — why are the policy and the count split between `dead` and its
caller?
    Because the two halves have different owners. `dead` is the *policy* —
    expired, and `MAX_MISSES` beats of grace spent — and the caller counts the
    misses, because the caller is the one that knows what a missed beat is. A
    recovery counts one per tick of silence past the deadline, because a beat
    that is not in the log is the only evidence it has and the log's grain is
    the tick; a run holding the lease itself (stage 10) counts the beats it owed
    and did not send. Folding the count into the policy would make this function
    a function of a clock instead of a decision about two numbers, and it is
    stage 10's `dead` and this one that have to be the same decision.

DESIGN DECISION — why does a beat from somebody who is not the owner revive
nothing?
    Because a lease is a job, an owner and a deadline, and a `beat` line is only
    evidence about the pair it names. A fold that let any `beat` for a job move
    the deadline would hand the slot to whichever process wrote a beat last, and
    a duplicate `<job, owner>` pair is exactly the bug of an owner that came
    back after its lease was re-issued. The fold therefore looks the lease up by
    job and moves the deadline only when the line's owner is that lease's owner;
    a beat for a stranger, or for a job no `claim` ever named, names the job and
    changes nothing. Ownership is decided by a `claim`, and a fold is no place
    to renegotiate it.

DESIGN DECISION — why does `heartbeat` write a line and not sync it?
    Because a beat is a line like every other line in this course: a prediction
    until a sync makes it a fact, and stage 1's `write_line` never syncs, on
    purpose, because stage 2 owns the sync. A `heartbeat` that synced would be
    the pathological answer that stage 2 names — one sync per line — and it
    would also be a second door to durability beside `commit`. What the beat's
    durability *means* is real and stage 10 is where it bites: an unsynced beat
    is a claim to be alive that a crash erases, so the process that comes after
    the crash reads the log and finds no beat, which is the truth about a beat
    that was never durable.

TODO: implement `MAX_MISSES`, `heartbeat`, `dead`, `recover` and `reclaimable`.
"""

from collections.abc import Iterable, Mapping

from stage_01 import LINE_KEYS, JournalError, line, write_line

#: How many beats an owner may miss before its lease is dead rather than merely
#: expired: one missed beat is a slow worker, and this many is a worker that is
#: not coming back. The grace is in ticks, the log's own unit, so the flip is
#: hand-computable — a lease whose deadline was 8 is running at 9 and expired at
#: 10 — and nothing here is timed by a clock anybody has to trust.
MAX_MISSES = 2


def heartbeat(disk, lease, *, now, ticks):
    """Write a `beat` line, and return the lease it renewed.

    The renewed lease is the same job, the same owner and the same `claimed_at`,
    with `deadline` renamed to `now + ticks`, in a fresh dict the caller's lease
    is not part of. A lease already expired at `now`, a lease that is not the
    shape stage 4 fixed, a blank owner and a `ticks` that is not a positive int
    are refused, naming the offender — and the expired lease's refusal names
    both ticks. The line is appended through stage 1's `write_line` and not
    synced: a line is a prediction until a sync makes it a fact.
    """
    raise NotImplementedError("stage 5: implement heartbeat()")


def dead(lease, *, now, misses):
    """Is this lease dead, or only expired?

    `misses` is the beats the owner owed and did not send, counted by the
    caller; the policy is `MAX_MISSES` of them **and** a deadline that has
    passed, both boundaries inclusive. A lease inside its deadline is alive
    however many beats were counted, and an expired lease at `MAX_MISSES - 1` is
    alive too. A lease that is not the shape stage 4 fixed, a tick that is not a
    tick and a count that is not one are refused, naming the offender.
    """
    raise NotImplementedError("stage 5: implement dead()")


def recover(lines, *, now):
    """The state table a process that just woke up must believe.

    A reading and nothing else: the lines a replay produced go in, a fresh
    id-sorted table comes out, and nothing is written — a line stage 1 would
    refuse is refused by name, with its index. `start` and `done` fold nothing;
    a `claim` makes a job `running`; a `beat` renames the deadline of the lease
    it belongs to and no other; a `result` finishes the job; an `expire` marks
    one `expired` unless a result already said otherwise; a `retry` re-issues it
    as `pending`. Then the leases left — the jobs whose newest claim no result
    answered — are judged: live stays `running`, dead becomes `expired`.
    """
    raise NotImplementedError("stage 5: implement recover()")


def reclaimable(lines, *, now):
    """The ids recovery may re-issue, sorted: every job whose lease died.

    Read off `recover`, so the two can never disagree: a job whose owner is
    still inside its deadline, and a job that finished, are not in this tuple.
    """
    raise NotImplementedError("stage 5: implement reclaimable()")
