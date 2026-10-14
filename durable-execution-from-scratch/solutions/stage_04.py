"""Durable Execution From Scratch — stage 4: The lease, and the owner that stops answering.

A run is not the process that started it; it is the log on disk, and a lease is
no exception. J1's lease was a field on a living object, read by the code that
wrote it. Here a lease is a *line* — a job, an owner and a deadline — so the
process that reads it is not the process that took it, and the only thing it can
trust is what the disk holds.

That changes the three questions this stage answers. "Is this job free?" is
asked of the log (`lease_of`), not of a table in memory. "Is this lease still
held?" is asked of the injected clock (`expired`), not of a wall clock, so the
boundary is a number a check can pin instead of a moment nobody can reproduce.
And "may I beat it?" is asked of the *owner* (`renew`): a lease with an owner
and a deadline is exactly the data that tells a heartbeat from a steal, and a
second worker taking a job somebody else holds is the bug this stage exists to
refuse.

    LeaseError  a claim, a lease and a heartbeat this stage refuses
    claim       take a job at a tick: the claim line, and the lease it spells
    lease_of    the newest claim for a job, as a lease — or None
    expired     is a lease over at this tick? `deadline <= now`, inclusive
    renew       the same owner, a later deadline — and nobody else

DESIGN DECISION — why is a lease four plain fields instead of an object?
    Because a lease has to outlive the process that took it. An object carries
    identity, so a reader that was not there cannot reconstruct it; four fields
    (the job, the owner, the deadline, the tick it was taken) can be written
    into a line and read back by anybody holding the disk, and `claimed_at` is
    what lets a later stage tell a lease that was *renewed* from one that was
    *re-taken*. `_require_lease` therefore hands back its own fresh dict: a lease
    the caller can edit in place would be a lease the next reader never sees.

DESIGN DECISION — why is the deadline `now + ticks` rather than `claimed_at + ticks`?
    Because a claim is taken *now* and a heartbeat is heard *now*, and both
    promise `ticks` more ticks of life from that moment. `claimed_at` is a fact
    about the past — the log's record of when the job was taken — and computing
    the deadline from it would make a beat a no-op the moment `now` moved on: a
    renewal that leaves the deadline where it was is a worker that thinks it
    said it is alive when it said nothing.

DESIGN DECISION — why is the boundary `deadline <= now` instead of `< now`?
    Because the deadline is the tick by which the owner promised to be back. At
    that tick the promise is already broken, so the lease is over; `<` would
    keep a dead owner's job locked for one more tick, and that one tick is
    exactly the tick recovery would have used to hand the job to somebody who
    can finish it. The check pins both sides: a lease with deadline 8 is not
    expired at 7 and is expired at 8.
DESIGN DECISION — why does `renew` take the owner it is renewing for?
    Because "the same owner only" is a comparison, and a comparison needs both
    sides. A lease read from the log carries the owner that holds it, and the
    process that wants to beat it carries its own label; `renew(lease, owner,
    ...)` refuses when the two differ, naming both, because a heartbeat from
    somebody else is not a heartbeat — it is a steal, and it is precisely the
    mistake an owner field is there to catch. Whether an *expired* lease may be
    beaten at all is the heartbeat's policy (stage 5), not this stage's: here
    the question is who, and the answer is `lease["owner"]`.

DESIGN DECISION — why does a claim over a live lease refuse instead of overwriting?
    Because the journal is append-only and its lines are facts: a second
    `claim` for a job somebody holds does not take the job, it *adds a lie* to
    the log, and every later reader has to guess which claim believed. The
    refusal names the owner and the tick the lease runs to, so the caller learns
    whether to wait or to renew. That the claim is written and not synced — and
    so dies with the process — is the caller's decision, which is exactly what
    stage 10's killed worker depends on.
"""

from collections.abc import Mapping

import stage_01
import work
from disk import DEFAULT_JOURNAL

#: The four fields a lease carries, in the order a reader meets them: the job it
#: is for, the owner that holds it, the tick by which it must be beaten, and the
#: tick it was taken. A field outside this tuple is a typo, and a typo is
#: refused by name.
_LEASE_KEYS = ("job", "owner", "deadline", "claimed_at")

#: How far a typo may be from a real name and still earn a suggestion. The
#: course's vocabulary — lease, heartbeat, checkpoint, intent, effect — is short
#: and its words are close, so two edits is where a suggestion stops being a
#: guess.
_NEAR = 2


class LeaseError(stage_01.DurableError):
    """A claim, a lease or a heartbeat this stage refuses.

    It derives from stage 1's `DurableError`, so one `except DurableError` still
    catches a broken course and a narrower `except LeaseError` reads better at
    the site that knows what it is doing. Every refusal names the offender — the
    job, the owner, the tick, the field, the line — and, when the offender is
    within edit distance two of a real name, the real name too: a lease whose
    field is a typo is a lease whose deadline silently became a default.
    """


def _edits(one, other):
    """The Levenshtein distance between two strings, as an int.

    Small and deterministic: no threshold below a full distance is needed, and
    the names in this course are short.
    """
    previous = list(range(len(other) + 1))
    for i, left in enumerate(one, 1):
        current = [i]
        for j, right in enumerate(other, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def _near(name, known):
    """The known name within `_NEAR` edits of `name`, or `None`.

    A non-str, an int, or a name that is already known is never measured: the
    suggestion exists for a typo, and a name that is not a string is a mistake
    the refusal has already named.
    """
    if not isinstance(name, str) or name in known:
        return None
    best = None
    for candidate in known:
        if abs(len(candidate) - len(name)) > _NEAR:
            continue
        distance = _edits(name, candidate)
        if distance <= _NEAR and (best is None or distance < best[1]
                                  or (distance == best[1]
                                      and candidate < best[0])):
            best = (candidate, distance)
    return None if best is None else best[0]


def _maybe(name, known):
    """`; did you mean 'x'?` for a typo, and nothing when there is no candidate."""
    guessed = _near(name, known)
    return "" if guessed is None else "; did you mean %r?" % (guessed,)


def _require_text(value, what):
    """A string that can be read back out of a line: non-empty, and no whitespace.

    Whitespace separates a line's fields, so an owner that carried it could
    never be read out of the journal again — the claim would name a different
    owner, or none. The refusal names the field and the value.
    """
    if not isinstance(value, str) or not value.strip():
        raise LeaseError("%s must be a non-empty str, got %r" % (what, value))
    for char in value:
        if char.isspace():
            raise LeaseError(
                "%s must not contain whitespace, got %r: whitespace separates a "
                "line's fields" % (what, value))
    return value


def _require_tick(value, what):
    """A tick: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LeaseError(
            "%s must be a non-negative int, got %r" % (what, value))
    return value


def _require_positive(value, what):
    """A lease's length: a real int, positive, and not the flag `True`.

    Zero is refused although it is a non-negative int: a lease that expires at
    the tick it was taken is not a short lease, it is a job nobody may hold —
    the same mistake as a deadline already in the past, made harder to see.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LeaseError("%s must be a positive int, got %r" % (what, value))
    return value


def _require_job(job_id):
    """A job the plan has, or a refusal naming it and the plan's ids."""
    if not isinstance(job_id, str) or job_id not in work.JOBS:
        raise LeaseError(
            "there is no job %r; the plan has %s%s"
            % (job_id, ", ".join(sorted(work.JOBS)), _maybe(job_id, work.JOBS)))
    return job_id


def _require_lease(lease):
    """The lease's four fields, as a fresh dict.

    A lease is data read out of a log by a process that was not there, so a
    field a lease does not have is refused by name (with the real field named
    when the typo is one edit from it), every field it needs must be present,
    and what comes back is this stage's own copy: a lease the caller keeps a
    handle on cannot be edited in place behind the log's back.
    """
    if not isinstance(lease, Mapping):
        raise LeaseError(
            "a lease must be a mapping of %s, got %r"
            % (", ".join(_LEASE_KEYS), lease))
    for name in lease:
        if name not in _LEASE_KEYS:
            raise LeaseError(
                "a lease has no field %r; its fields are %s%s"
                % (name, ", ".join(_LEASE_KEYS), _maybe(name, _LEASE_KEYS)))
    for name in _LEASE_KEYS:
        if name not in lease:
            raise LeaseError(
                "a lease needs %r; it carries %s"
                % (name, ", ".join(sorted(lease))))
    return {
        "job": _require_text(lease["job"], "a lease's job"),
        "owner": _require_text(lease["owner"], "a lease's owner"),
        "deadline": _require_tick(lease["deadline"], "a lease's deadline"),
        "claimed_at": _require_tick(lease["claimed_at"], "a lease's claimed_at"),
    }


def _journal(disk):
    """The journal's lines, parsed, in the order the log holds them.

    A claim is decided against the log, not against a table in memory, so this
    is the read a claim makes: what the disk shows the process *right now*
    (`disk.read` — a claim this process wrote a moment ago is there, even
    though no sync has made it a fact yet), read back through stage 1's parser.
    A line this vocabulary cannot read is refused rather than skipped: a claim
    decided over half a journal is a guess.
    """
    lines = []
    for index, raw in enumerate(disk.read(DEFAULT_JOURNAL).split("\n")):
        if not raw:
            continue
        try:
            lines.append(stage_01.parse_line(raw))
        except stage_01.JournalError as bad:
            raise LeaseError(
                "a claim needs a journal it can read; line %d is %r: %s"
                % (index, raw, bad))
    return lines


def claim(disk, job_id, owner, *, now, ticks):
    """Take `job_id` for `owner` at `now`, for `ticks`: the claim line, and the lease.

    The claim is refused for a job the plan does not have, an owner that could
    not be read back out of a line, a `ticks` that is not a positive int, and a
    job whose newest claim has *not* expired at `now` — naming the owner that
    holds it and the tick the lease runs to, because a second claim over a live
    lease is a steal, not a claim. The line goes to the world's journal through
    stage 1's `write_line`, and, like every line, it is written and not synced:
    whether a claim is durable is the caller's decision (stage 2's `commit`),
    and a lease that dies with the process is exactly what stage 10's killed
    worker needs.
    """
    job_id = _require_job(job_id)
    owner = _require_text(owner, "an owner")
    now = _require_tick(now, "now")
    ticks = _require_positive(ticks, "ticks")
    held = lease_of(_journal(disk), job_id)
    if held is not None and not expired(held, now):
        raise LeaseError(
            "the job %r is claimed by %r until %d, and %r may not claim it at "
            "%d: a claim over a live lease is a steal"
            % (job_id, held["owner"], held["deadline"], owner, now))
    stage_01.write_line(disk, {"tick": now, "kind": "claim", "job": job_id,
                               "owner": owner, "ticks": ticks})
    return {"job": job_id, "owner": owner, "deadline": now + ticks,
            "claimed_at": now}


def lease_of(lines, job_id):
    """The newest `claim` for `job_id`, as a lease — or `None` when the log has none.

    Newest, not first: a job claimed, expired and claimed again is held by the
    owner of the *second* claim, and a reader that returned the first would hand
    a live job to a worker that already lost it. The deadline is *computed* —
    the claim's tick plus the claim's ticks — so a log written in stage 1's
    vocabulary is all the state a lease needs, and nothing has to be kept in
    memory beside it.

    The lines are the parsed records a replay hands over. A line that is not a
    mapping, or that carries no `kind` at all, is refused by name; a claim whose
    owner or length the log never wrote is refused too, because a lease with an
    invented owner is a lease nobody holds. The returned dict is fresh on every
    call: a lease the caller edits cannot rewrite the log it was read from.
    """
    job_id = _require_text(job_id, "a job id")
    newest = None
    for entry in lines:
        if not isinstance(entry, Mapping):
            raise LeaseError(
                "a journal line must be a mapping, got %r" % (entry,))
        if "kind" not in entry:
            raise LeaseError(
                "a journal line needs 'kind', got %r" % (dict(entry),))
        if entry["kind"] != "claim" or entry.get("job") != job_id:
            continue
        newest = entry
    if newest is None:
        return None
    claimed_at = _require_tick(newest.get("tick"), "a claim line's tick")
    owner = _require_text(newest.get("owner"), "a claim line's owner")
    ticks = _require_positive(newest.get("ticks"), "a claim line's ticks")
    return {"job": job_id, "owner": owner, "deadline": claimed_at + ticks,
            "claimed_at": claimed_at}


def expired(lease, now):
    """Is `lease` over at `now`? `deadline <= now` — the boundary is inclusive.

    Inclusive because the deadline is the tick by which the owner promised to be
    back: at that tick the promise is already broken. The alternative (`<`)
    keeps a dead owner's job locked for one more tick, which is one tick more
    than recovery needs; the check pins both sides of the boundary, a lease with
    deadline 8 being alive at 7 and over at 8.
    """
    lease = _require_lease(lease)
    now = _require_tick(now, "now")
    return lease["deadline"] <= now


def renew(lease, owner, *, now, ticks):
    """`owner`'s heartbeat on `lease`: the same job, the same owner, a later deadline.

    The deadline is `now + ticks`, measured from the tick the beat is *heard* —
    not from the lease's old deadline (a beat is not an accumulation) and not
    from `claimed_at` (a lease is renewed, not re-taken). `claimed_at` stays put
    for the same reason: a reader that saw it move would think a second worker
    had taken the job.

    The owner is what makes this a heartbeat instead of a steal. Somebody who is
    not the lease's owner is refused, naming both owners; whether an *expired*
    lease may be beaten at all is the heartbeat's policy (stage 5), not this
    one's, because this stage's question is who may renew and not when.
    """
    lease = _require_lease(lease)
    owner = _require_text(owner, "an owner")
    now = _require_tick(now, "now")
    ticks = _require_positive(ticks, "ticks")
    if owner != lease["owner"]:
        raise LeaseError(
            "a heartbeat from %r is a steal: the lease for %r is held by %r "
            "until %d, and only its owner may renew it"
            % (owner, lease["job"], lease["owner"], lease["deadline"]))
    return {"job": lease["job"], "owner": owner, "deadline": now + ticks,
            "claimed_at": lease["claimed_at"]}
