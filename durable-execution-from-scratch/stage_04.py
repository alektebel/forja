"""Durable Execution From Scratch — stage 4: The lease, and the owner that stops answering.

A run is not the process that started it; it is the log on disk, and a lease is
no exception. J1's lease was a field on a living object, read by the code that
wrote it. Here a lease is a *line* — a job, an owner and a deadline — so the
process that reads it is not the process that took it, and the only thing it can
trust is what the disk holds.

Every later stage leans on this one: stage 5 beats a lease and refuses a beat it
did not earn, stage 6 marks a dead owner's job `expired` by reading the claim
this stage writes, and stage 10 kills a worker holding one. So the lease has to
be *data* — four fields a stranger can read out of a journal — and the two
decisions that keep a second worker away from a live job (a claim over an
unexpired lease, a heartbeat from an owner that is not the lease's) have to be
refusals, not conventions.

    LeaseError  a claim, a lease and a heartbeat this stage refuses
    claim       take a job at a tick: the claim line, and the lease it spells
    lease_of    the newest claim for a job, as a lease — or None
    expired     is a lease over at this tick? `deadline <= now`, inclusive
    renew       the same owner, a later deadline — and nobody else

DESIGN DECISION — why is a lease four plain fields instead of an object?
    Because a lease has to outlive the process that took it, and an object
    carries identity a reader that was not there cannot reconstruct. The four
    fields — job, owner, deadline, `claimed_at` — can be written into a line and
    read back by anybody holding the disk, and `claimed_at` is what lets a later
    stage tell a lease that was *renewed* from one that was *re-taken*. The dict
    that comes back is therefore a fresh copy: a lease the caller can edit in
    place is a lease the next reader never sees.

DESIGN DECISION — why is the deadline `now + ticks` rather than `claimed_at + ticks`?
    Because a claim is taken *now* and a heartbeat is heard *now*, and both
    promise `ticks` more ticks of life from that moment. `claimed_at` is a fact
    about the past, and computing the deadline from it would make a beat a no-op
    the moment `now` moved on: a renewal that leaves the deadline where it was
    is a worker that thinks it said it is alive when it said nothing.

DESIGN DECISION — why is the boundary `deadline <= now` instead of `< now`?
    Because the deadline is the tick by which the owner promised to be back: at
    that tick the promise is already broken. `<` would keep a dead owner's job
    locked for one more tick, which is one tick more than recovery needs — and a
    check can pin both sides of `<=`, which it cannot do for a wall clock.
DESIGN DECISION — why does `renew` take the owner it is renewing for?
    Because "the same owner only" is a comparison, and a comparison needs both
    sides. A lease read from the log carries the owner that holds it, and the
    process that wants to beat it carries its own label; when the two differ the
    renewal is refused, naming both, because a heartbeat from somebody else is
    not a heartbeat — it is a steal, and that is exactly the mistake an owner
    field exists to catch. Whether an *expired* lease may be beaten at all is
    the heartbeat's policy (stage 5): here the question is who, and the answer is
    the lease's own owner.

DESIGN DECISION — why does a claim over a live lease refuse instead of overwriting?
    Because the journal is append-only and its lines are facts: a second `claim`
    for a job somebody holds does not take the job, it *adds a lie* to the log,
    and every later reader has to guess which claim believed. The refusal names
    the owner and the tick the lease runs to, so the caller learns whether to
    wait or to renew. That the claim is written and not synced — and so dies
    with the process — is the caller's decision, and stage 10's killed worker
    depends on exactly that.

TODO: implement `LeaseError`, `claim`, `lease_of`, `expired` and `renew`.
"""

import stage_01


class LeaseError(stage_01.DurableError):
    """A claim, a lease or a heartbeat this stage refuses.

    It derives from stage 1's `DurableError`, so one `except DurableError` still
    catches a broken course while a narrower `except LeaseError` reads better at
    the site that knows what it is doing. Every refusal names the offender — the
    job, the owner, the tick, the field, the line — and, when the offender is
    within edit distance two of a real name, the real name too.
    """


def claim(disk, job_id, owner, *, now, ticks):
    """Take `job_id` for `owner` at `now`, for `ticks`: the claim line, and the lease.

    Refused for a job the plan does not have, an owner that could not be read
    back out of a line, a `ticks` that is not a positive int, and a job whose
    newest claim has not expired at `now` (naming the owner that holds it: a
    second claim over a live lease is a steal). The line goes to the world's
    journal through stage 1's `write_line` — written, not synced.
    """
    raise NotImplementedError("stage 4: implement claim()")


def lease_of(lines, job_id):
    """The newest `claim` for `job_id`, as a lease — or `None` when the log has none.

    The lease is `{"job", "owner", "deadline", "claimed_at"}` with
    `deadline = the claim's tick + the claim's ticks`, and it is a fresh dict.
    A line that is not a mapping, one with no `kind`, and a claim whose owner or
    length the log never wrote are all refused by name.
    """
    raise NotImplementedError("stage 4: implement lease_of()")


def expired(lease, now):
    """Is `lease` over at `now`? `deadline <= now` — the boundary is inclusive.

    The alternative (`<`) keeps a dead owner's job locked for one tick more than
    recovery needs, and the check pins both sides of the boundary.
    """
    raise NotImplementedError("stage 4: implement expired()")


def renew(lease, owner, *, now, ticks):
    """`owner`'s heartbeat on `lease`: the same job, the same owner, a later deadline.

    The deadline is `now + ticks` — not the old deadline plus `ticks`, and not
    `claimed_at + ticks` — while `claimed_at` stays the tick the claim was
    taken, because a heartbeat extends a lease instead of starting one. An owner
    that is not the lease's owner is refused as a steal, naming both.
    """
    raise NotImplementedError("stage 4: implement renew()")
