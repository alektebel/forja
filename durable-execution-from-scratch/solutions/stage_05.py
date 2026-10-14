"""stage_05.py — the heartbeat, and the worker that dies holding the slot.

Durable Execution From Scratch — stage 5: The heartbeat, and the worker that
dies holding the slot.

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

#: The four fields a lease carries — the shape stage 4 fixed, restated here
#: because a stage may import only stage 1, and a lease read off the log is this
#: shape or it is not a lease. A lease is data: no object identity, no `Disk`,
#: nothing the caller can mutate behind the fold's back.
_LEASE_KEYS = ("job", "owner", "deadline", "claimed_at")

#: The nine kinds of line a journal holds, in the order a run writes them. A
#: recovery that folded a line it does not know would report a state out of a
#: log it did not finish reading, so a kind outside these nine is refused.
_KINDS = ("start", "claim", "beat", "intent", "result", "effect", "expire",
          "retry", "done")


def _require_tick(value, what):
    """A tick: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise JournalError(
            "%s must be a non-negative int, got %r" % (what, value))
    return value


def _require_name(value, what):
    """A job or an owner: a non-empty str, and not a blank one."""
    if not isinstance(value, str) or not value.strip():
        raise JournalError("%s must be a non-empty str, got %r" % (what, value))
    return value


def _lease(lease, what="a lease"):
    """The four fields a lease has, or a refusal naming the one that is wrong.

    A lease is read *from the log* by the process that comes after the crash, so
    a caller that hands this stage something else — a partial dict, a deadline
    of `True`, an owner that is not a name — is handing it a lease nobody will
    find on disk. The refusal names the field, and the shape, so the fix is one
    edit away.
    """
    if not isinstance(lease, Mapping):
        raise JournalError("%s must be a mapping, got %r" % (what, lease))
    for name in _LEASE_KEYS:
        if name not in lease:
            raise JournalError("%s has no %r; a lease is %s"
                               % (what, name, ", ".join(_LEASE_KEYS)))
    _require_name(lease["job"], "%s's job" % (what,))
    _require_name(lease["owner"], "%s's owner" % (what,))
    _require_tick(lease["deadline"], "%s's deadline" % (what,))
    _require_tick(lease["claimed_at"], "%s's claimed_at" % (what,))
    return lease


def _record(entry, index):
    """One line of a log, refused unless it is a line this stage may fold.

    The check is stage 1's own `line`: a record is folded only if the journal
    could have held it, so a fold never reads a field its kind does not carry, a
    number that is not an int, or a kind outside the nine. The refusal names the
    index and the offender, because a log is read by index when it is read by a
    process that did not write it.
    """
    if not isinstance(entry, Mapping):
        raise JournalError("the line at index %d is not a mapping, got %r"
                           % (index, entry))
    for name in ("tick", "kind"):
        if name not in entry:
            raise JournalError("the line at index %d has no %r: %r"
                               % (index, name, entry))
    kind = entry["kind"]
    if kind not in _KINDS:
        raise JournalError(
            "there is no line kind %r at index %d; the kinds are %s"
            % (kind, index, ", ".join(_KINDS)))
    for name in entry:
        if name not in LINE_KEYS:
            raise JournalError(
                "the line at index %d has no field %r; a line's fields are %s"
                % (index, name, ", ".join(LINE_KEYS)))
    fields = {name: value for name, value in entry.items()
              if name not in ("tick", "kind")}
    try:
        line(entry["tick"], kind, **fields)
    except JournalError as broken:
        raise JournalError("the line at index %d is not a line: %s"
                           % (index, broken)) from None


def _finished(entry):
    """What a `result` line says a job's state is.

    `ok` is `done` and anything else a worker can answer is `failed` — the
    worker's vocabulary is not the state table's (stage 1 refuses a line that
    says `done`), and this is the one place the two meet. The worker's own
    detail travels only when it wrote one: a result without a `text` is a bare
    status, exactly as contract §3.2 reads it.
    """
    status = "done" if entry["status"] == "ok" else "failed"
    text = entry.get("text")
    return status if text is None else {"status": status, "text": text}


def _status_of(state):
    """The status of a state, whether it is a bare state or a record."""
    return state if isinstance(state, str) else state["status"]


def heartbeat(disk, lease, *, now, ticks):
    """Write a `beat` line, and return the lease it renewed.

    The renewed lease is the same job, the same owner and the same `claimed_at`,
    with `deadline` renamed to `now + ticks`: a beat renames a deadline, it does
    not begin a lease (contract §3.3), and `claimed_at` is what tells a fold
    which claim this beat belongs to. The fresh dict is deliberate — the
    caller's lease is not touched. A lease already expired at `now`, a lease
    that is not the shape stage 4 fixed, a blank owner and a `ticks` that is not
    a positive int are refused, naming the offender and, for the deadline, both
    ticks. The line is appended through stage 1's `write_line` and **not**
    synced: a line is a prediction until a sync makes it a fact, and stage 2
    owns the sync.
    """
    lease = _lease(lease)
    now = _require_tick(now, "the tick a heartbeat is written at")
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 1:
        raise JournalError(
            "a heartbeat's ticks must be a positive int, got %r" % (ticks,))
    deadline = lease["deadline"]
    if now >= deadline:
        raise JournalError(
            "the lease on %r held by %r expired at tick %d; a beat at tick %d is "
            "a new claim, not a heartbeat"
            % (lease["job"], lease["owner"], deadline, now))
    renewed = {"job": lease["job"], "owner": lease["owner"],
               "deadline": now + ticks, "claimed_at": lease["claimed_at"]}
    beat = {"tick": now, "kind": "beat", "job": renewed["job"],
            "owner": renewed["owner"], "ticks": ticks}
    write_line(disk, beat)
    return renewed


def dead(lease, *, now, misses):
    """Is this lease dead, or only expired?

    `misses` is the beats the owner owed and did not send, counted by the
    caller; the policy is `MAX_MISSES` of them **and** a deadline that has
    passed. Both halves matter and both boundaries are inclusive. A lease
    *inside* its deadline is alive however many beats a caller counted — the
    deadline is what the owner promised, and the grace only starts when it
    lapses, which is why a claim with no beat at all is not dead immediately
    (that is the whole difference between `expired` and `dead`). And an expired
    lease whose owner just beat is alive too: the count is the observation, this
    function is only the decision.
    """
    lease = _lease(lease)
    now = _require_tick(now, "the tick a lease is judged at")
    misses = _require_tick(misses, "the beats an owner missed")
    return misses >= MAX_MISSES and now >= lease["deadline"]


def recover(lines, *, now):
    """The state table a process that just woke up must believe.

    A reading and nothing else: it takes the lines a replay produced and returns
    a fresh, id-sorted table, and writes nothing (it has no disk to write to).

    `start` and `done` are the run's own lines and fold nothing. A `claim` makes
    a job `running` under that owner, with `deadline = tick + ticks`; a `beat`
    renames that deadline, but only for the lease it belongs to. A `result`
    finishes the job — `done` for `ok`, `failed` for anything else — and lets
    the lease go, whoever the line says wrote it, because the job is what the
    run has to know about and a result is the log's last word on it. An `expire`
    marks the job `expired`, and does not overwrite `done`/`failed`. A `retry`
    re-issues it as `pending`. An `intent` or an `effect` names the job and
    nothing more, so a job the log only ever mentioned that way is `pending`:
    claimed by nobody. `skipped` is a state no line here says.

    Then the leases that are left are judged — they are exactly the jobs whose
    newest claim no result answered. A live lease stays `running`; a dead one
    becomes `expired`, which is this stage's whole point: the process that held
    it is gone, and the slot has to be reclaimable by whoever reads the log
    next.
    """
    now = _require_tick(now, "the tick a recovery reads the log at")
    if isinstance(lines, (str, bytes)) or not isinstance(lines, Iterable):
        raise JournalError(
            "a recovery reads the lines a replay produced, got %r" % (lines,))
    states = {}
    leases = {}
    for index, entry in enumerate(lines):
        _record(entry, index)
        kind = entry["kind"]
        if kind in ("start", "done"):
            continue
        job = entry["job"]
        tick = entry["tick"]
        if kind == "claim":
            states[job] = "running"
            leases[job] = {"job": job, "owner": entry["owner"],
                           "deadline": tick + entry.get("ticks", 0),
                           "claimed_at": tick}
        elif kind == "beat":
            lease = leases.get(job)
            if lease is not None and lease["owner"] == entry["owner"]:
                lease["deadline"] = tick + entry.get("ticks", 0)
            states.setdefault(job, "pending")
        elif kind == "result":
            states[job] = _finished(entry)
            leases.pop(job, None)
        elif kind == "expire":
            if _status_of(states.get(job, "pending")) not in ("done", "failed"):
                states[job] = "expired"
            leases.pop(job, None)
        elif kind == "retry":
            states[job] = "pending"
            leases.pop(job, None)
        else:
            states.setdefault(job, "pending")
    for job, lease in leases.items():
        misses = now - lease["deadline"]
        if misses < 0:
            misses = 0
        if dead(lease, now=now, misses=misses):
            states[job] = "expired"
    return dict(sorted(states.items()))


def reclaimable(lines, *, now):
    """The ids recovery may re-issue, sorted: every job whose lease died.

    Read off `recover`, so that the two can never disagree about who is gone: a
    job whose owner is still inside its deadline, or one whose result says it
    finished, is not in this tuple. Sorted because it is a decision list the next
    process acts on, and two processes reading the same log must re-issue the
    same jobs in the same order.
    """
    states = recover(lines, now=now)
    gone = [job for job, state in states.items()
            if _status_of(state) == "expired"]
    return tuple(sorted(gone))
