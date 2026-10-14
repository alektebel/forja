"""Durable Execution From Scratch — stage 10: Two workers, one killed holding the lease.

This is the run the nine stages were for: a plan, two workers in the air at once,
and one of them killed holding a lease. What is left after the kill is a disk, and
the disk is the only channel between the process before it and the process after
it — so the same function, called again over the same disk, has to be able to
finish the work, and the properties a reader can check are properties of the
*world*: equal states, and every effect key applied exactly once.

    DEFAULT_LIMIT  how many jobs the run has in the air at once
    LEASE_TICKS    how long a synthetic owner's claim lasts
    run            plan, disk, effects, clock and the owners in, §3.5's mapping out

The loop is one decision per tick: a tick passes, an owner whose `dies_at` has
arrived stops existing (the kill, and the run returns at that tick with what the
crash discarded), the leases still held are beaten, the work advances, an
attempt that ends writes its `result`, a job that is owed a finished job per
`checkpoint_every` writes stage 8's checkpoint, and the cap is filled again.

DESIGN DECISION — why is the cap a count of claims in the air, and why does the
run claim before it works?
    Because the stage is about a lease somebody died holding, and a lease only
    matters while a second worker is in the air to be killed. `limit` bounds the
    jobs claimed and not yet answered with a `result`, and the claims go out
    before any of the batch is worked — with the default of two, two `claim` lines
    precede the first `result`, which is a shape a reader can count. A cap applied
    after the claims is not a cap.

DESIGN DECISION — why are the owners named in the order the log claims, never
reused?
    Because an owner label is a fact about the log. The synthetic owners are
    `w1`…`wN` in claim order, and an explicit `workers` tuple is handed out
    round-robin by position *across the log's claims* — so a resume continues
    where the crash left off. A label reused by the second process for the same
    job makes one owner look like two, and the log stops saying which owner died
    holding the slot.

DESIGN DECISION — why are there two death paths and one mechanism?
    Because a kill costs exactly what was not synced, and where it lands decides
    which lease the next process finds. An owner killed *before* any sync leaves
    no trace of its claim (stage 4's `claim` never syncs, on purpose): the next
    read finds no lease, the job is `pending`, and the resume re-issues it at
    once. An owner killed *after* a sync — its claim made durable by a
    checkpoint's barrier, which flushes everything written before it — leaves a
    lease the next process must honour until `deadline + MAX_MISSES`, and only
    then is the job reclaimable. Same `crash()`, same disk, same function; the
    difference is a sync, and the difference is the lesson.

DESIGN DECISION — why does the resume wait a lapsed lease out, and read the states
off the log?
    Because a lease that has not lapsed is a promise somebody else may still be
    keeping; a resume that takes it a tick early is the second worker this course
    refuses. Stage 5's `reclaimable` names only the dead leases, so the resume
    advances the injected clock to the first tick each live lease is dead at, lets
    stage 6 write the `expire` line there, and only then re-issues the id under a
    fresh owner. And what `run` returns is read off the final journal — `states`
    from `state_of`, `report` from stage 9, `events` the journal's records — never
    from the table the run kept while it worked, which is a prediction the process
    after it cannot see.

DESIGN DECISION — why is an effect redone only through stage 7's `settle`?
    Because the two things an interruption leaves are a synced `intent` and a
    world that may or may not have been touched. A re-issued job asks the journal
    first (an `effect` line for its key means the effect is already proven) and
    then the world: `settle` records the line it can prove, or applies under the
    job's *own* key — so however many times the run is resumed, the world ends
    with exactly one application per key.
"""

from collections.abc import Mapping

import fleet
import work
from disk import Disk
from stage_01 import DurableError, write_line
from stage_02 import commit
from stage_03 import replay, state_of
from stage_04 import claim as take
from stage_05 import MAX_MISSES, heartbeat, reclaimable
from stage_06 import crash as kill
from stage_07 import intent, settle
from stage_08 import ResumeError, checkpoint, read_checkpoint
from stage_09 import report

#: How many jobs the run has in the air at once: two workers, so that one of them
#: can be killed holding a lease while the other is still on its feet. The cap
#: counts claims no `result` has answered.
DEFAULT_LIMIT = 2

#: How long a claim lasts when the caller names no workers: the synthetic owners
#: have no script of their own, so every one of them is granted the same lease.
LEASE_TICKS = 4

#: The keys an explicit owner may carry, in the order a reader meets them.
_OWNER_KEYS = ("owner", "ticks", "dies_at")

#: The statuses a state table may hold — stage 3's vocabulary. A job is finished
#: when the log says `done` or `failed`, and nothing else is finished.
_FINISHED = ("done", "failed")


def _require_text(value, what):
    """A name that can be read back out of a line: non-empty, no whitespace.

    Whitespace separates a line's fields, so an id or a key that carried it could
    never be read out of the journal again. The refusal names the field and the
    value.
    """
    if not isinstance(value, str) or not value.strip():
        raise DurableError("%s must be a non-empty str, got %r" % (what, value))
    for char in value:
        if char.isspace():
            raise DurableError(
                "%s must not contain whitespace, got %r: whitespace separates a "
                "line's fields" % (what, value))
    return value


def _require_tick(value, what):
    """A tick: a real int, not negative, and not the flag `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DurableError(
            "%s must be a non-negative int, got %r" % (what, value))
    return value


def _require_positive(value, what):
    """A count or a lease's length: a real int, at least one, not `True`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DurableError("%s must be a positive int, got %r" % (what, value))
    return value


def _plan(plan):
    """The plan's jobs, id-sorted, refused when it is not a plan of `work.Job`s.

    A plan is a mapping of job id to job, and the id is the name the journal will
    hold: a key that is not the job's own id would make two names for one unit of
    work, which is exactly the ambiguity the log cannot afford. Nothing here
    depends on the order the caller wrote the mapping in — the plan is worked in
    id order, so two runs of one plan are the same run.
    """
    if not isinstance(plan, Mapping):
        raise DurableError(
            "a run works a plan: a mapping of job id to work.Job, got %r"
            % (plan,))
    for job_id in plan:
        if not isinstance(job_id, str) or not job_id.strip():
            raise DurableError(
                "a plan's job id must be a non-empty str, got %r" % (job_id,))
    jobs = {}
    for job_id in sorted(plan):
        job = plan[job_id]
        if not isinstance(job, work.Job):
            raise DurableError(
                "the plan's job %r is %r, not a work.Job: a run works the plan's "
                "own jobs" % (job_id, job))
        if job.id != job_id:
            raise DurableError(
                "the plan names the job %r and the job names itself %r: a plan's "
                "key is the id its journal will hold" % (job_id, job.id))
        jobs[job_id] = job
    if not jobs:
        raise DurableError(
            "a run works a plan with at least one job, got %r" % (plan,))
    return jobs


def _plan_hash(jobs):
    """A plan's hash: the FNV-1a of its id-sorted text, as `plan-<hex>`.

    The `start` line carries it and a checkpoint carries it too, so a resume over
    another plan — or another run — is refused instead of finishing somebody
    else's work under this run's name. It is computed from the plan alone: two
    runs of one plan agree, and nothing about the process that ran it is in it.
    """
    text = "|".join(
        "%s:%s:%d:%s:%s" % (jobs[job_id].id, jobs[job_id].label,
                            jobs[job_id].ticks, jobs[job_id].key,
                            jobs[job_id].value)
        for job_id in sorted(jobs))
    value = 2166136261
    for char in text:
        value = ((value ^ ord(char)) * 16777619) & 0xffffffff
    return "plan-%08x" % (value,)


def _owners(workers):
    """The owners the caller named, validated — or `None` for the synthetic ones.

    A worker spec is `{"owner", "ticks", "dies_at"}` and all three are needed: an
    owner without a lease length cannot be claimed for, and an owner without a
    `dies_at` (a tick or `None`) is an owner whose death was forgotten rather than
    one that never dies.
    """
    if workers is None:
        return None
    if isinstance(workers, (str, bytes)) or not isinstance(workers, (tuple, list)):
        raise DurableError(
            "workers is None — one synthetic owner per claim — or a tuple of "
            "mappings, got %r" % (workers,))
    specs = []
    for index, one in enumerate(workers):
        if not isinstance(one, Mapping):
            raise DurableError(
                "the worker at index %d is %r, not a mapping of %s"
                % (index, one, ", ".join(_OWNER_KEYS)))
        for name in one:
            if name not in _OWNER_KEYS:
                raise DurableError(
                    "the worker at index %d has no field %r; a worker is %s"
                    % (index, name, ", ".join(_OWNER_KEYS)))
        for name in _OWNER_KEYS:
            if name not in one:
                raise DurableError(
                    "the worker at index %d needs %r; a worker is %s"
                    % (index, name, ", ".join(_OWNER_KEYS)))
        dies_at = one["dies_at"]
        if dies_at is not None:
            dies_at = _require_tick(
                dies_at, "the worker %r's dies_at" % (one["owner"],))
        specs.append({"owner": _require_text(one["owner"], "an owner"),
                      "ticks": _require_positive(one["ticks"], "an owner's ticks"),
                      "dies_at": dies_at})
    if not specs:
        raise DurableError(
            "workers is a tuple of at least one owner, got %r" % (workers,))
    return tuple(specs)


def _owner_at(owners, index):
    """The owner of the `index`-th claim this disk has ever seen.

    The synthetic owners are named in claim order — `w1` for the log's first
    claim, `w2` for its second, and so on — and an explicit tuple is walked
    round-robin over that same count, so neither a fresh run nor a resume can
    hand a job to a label the log already read as somebody else.
    """
    if owners is None:
        return {"owner": "w%d" % (index + 1,), "ticks": LEASE_TICKS,
                "dies_at": None}
    return owners[index % len(owners)]


def _status(state):
    """A state's status, whether the table spells it bare or as a record."""
    return state if isinstance(state, str) else state["status"]


def _top(lines):
    """The highest tick the lines name — the tick a run stopped at, per stage 9."""
    top = None
    for entry in lines:
        if top is None or entry["tick"] > top:
            top = entry["tick"]
    return top


def _leases(lines):
    """The leases the lines still stand: `job -> {owner, deadline, claimed_at}`.

    Stage 4's and stage 5's fold, read here because the resume has to know the
    deadline it is waiting out: a `claim` takes the lease, a `beat` by the same
    owner renames the deadline, and a `result` or a `retry` lets it go. A beat by
    somebody who is not the holder revives nothing.
    """
    standing = {}
    for entry in lines:
        job = entry.get("job")
        if job is None:
            continue
        kind = entry["kind"]
        if kind == "claim":
            standing[job] = {"job": job, "owner": entry["owner"],
                             "claimed_at": entry["tick"],
                             "deadline": entry["tick"] + entry.get("ticks", 0)}
        elif kind == "beat":
            lease = standing.get(job)
            if lease is not None and lease["owner"] == entry["owner"]:
                lease["deadline"] = entry["tick"] + entry.get("ticks", 0)
        elif kind in ("result", "retry"):
            standing.pop(job, None)
    return standing


def _count(lines, kind, job_id=None):
    """How many lines of `kind` the log holds — for one job, when named."""
    total = 0
    for entry in lines:
        if entry["kind"] != kind:
            continue
        if job_id is not None and entry.get("job") != job_id:
            continue
        total += 1
    return total


def _proven(lines, job):
    """Is the job's effect already written into the log, under its own key?"""
    for entry in lines:
        if (entry["kind"] == "effect" and entry.get("job") == job.id
                and entry.get("key") == job.key):
            return True
    return False


def _answer(answer, job_id):
    """The worker's answer, as `(status, ticks, detail)`, or a refusal naming it.

    A worker is a scripted function, and a script that answers something that is
    not an outcome — a string, a status nobody defined, a negative cost — is
    refused here rather than filed as a success: `fleet.bad_shape` is in the
    catalogue for exactly this reason, and a run that charged a negative number
    of ticks would report a clock that ran backwards.
    """
    if not isinstance(answer, Mapping) or "status" not in answer:
        raise DurableError(
            "the worker of job %r answered %r, not a fleet outcome"
            % (job_id, answer))
    status = answer["status"]
    if status not in fleet.OUTCOMES:
        raise DurableError(
            "the worker of job %r answered the status %r, not one of %s"
            % (job_id, status, ", ".join(fleet.OUTCOMES)))
    ticks = answer.get("ticks", 0)
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise DurableError(
            "the worker of job %r answered ticks=%r: an attempt costs a "
            "non-negative int" % (job_id, ticks))
    detail = answer.get("detail", "")
    if not isinstance(detail, str):
        raise DurableError(
            "the worker of job %r answered the detail %r, not a str"
            % (job_id, detail))
    return status, ticks, detail


def _settle_effect(disk, effects, job, now):
    """A finished attempt's effect: proven, recorded, or applied — exactly once.

    The journal is asked first: an `effect` line for the job's own key means the
    effect is already a fact and nothing happens (this is a re-issued job whose
    effect landed before the crash). Otherwise the intent is written *and synced*
    (stage 7's rule: a promise that can be lost is not a promise) and stage 7's
    `settle` decides from the world — recording the line it can prove, or
    applying under the job's own key. Either way the world ends with one
    application of the key, however many attempts this job has taken.
    """
    if _proven(replay(disk), job):
        return "proven"
    intent(disk, job.id, job.key)
    return settle(disk, effects, replay(disk), job, tick=now)


def _token(detail):
    """A worker's own detail, when a line can carry it — a single token, or none.

    A line's fields are separated by whitespace, so `slow but correct` is three
    tokens and not one field: the detail is kept when the worker spelled a single
    token (`fine`, `done`) and dropped otherwise, rather than mangled into
    something the worker did not say.
    """
    if not detail:
        return None
    for char in detail:
        if char.isspace():
            return None
    return detail


def _recovered(disk, clock):
    """The state a process that comes after the crash must believe, and the wait.

    Nothing here is the crashed process's memory: the log `disk.synced` would
    keep is re-read, every lease that is still alive is waited out — the clock is
    advanced to the first tick that lease is dead at, `deadline + MAX_MISSES` —
    and stage 6 writes the `expire` line each dead owner is owed. Returns
    `(lost, lines, states)`: `lost` is what *this* call's crash discarded, which
    is nothing, because the crash that matters belongs to the call before it and
    its volatile bytes are gone for good.
    """
    lost, lines, states = kill(disk, (), now=clock.now())
    top = _top(lines)
    if top is not None and clock.now() < top:
        clock.tick(top - clock.now())
        lost, lines, states = kill(disk, (), now=clock.now())
    while True:
        standing = _leases(lines)
        running = [job for job in sorted(states)
                   if _status(states[job]) == "running"]
        if not running:
            return lost, lines, states
        target = max(standing[job]["deadline"] + MAX_MISSES for job in running)
        clock.tick(target - clock.now())
        lost, lines, states = kill(disk, (), now=clock.now())


def _returned(disk, effects, clock):
    """§3.5's mapping, read off the final log — never off the run's own table.

    `states` is what the lines decide (stage 3's `state_of`), `events` is the
    journal as records, `report` is stage 9's recomputation over those lines —
    which cross-checks the table and the world, so a run that returned a state
    its log does not justify is refused here rather than reported — and `clock`
    is the tick the run stopped at. `lost` is what a crash in this call
    discarded, and nothing else: the volatile bytes of the crash before it are
    not knowable from a disk that has already forgotten them.
    """
    lines = tuple(replay(disk))
    states = state_of(lines)
    return {"states": states, "events": lines,
            "report": report(disk, lines, states=states, ticks=_top(lines),
                             effects=effects),
            "clock": clock.now(), "lost": ()}


def run(plan, *, disk, effects, clock=None, limit=DEFAULT_LIMIT, run_id="run-1",
        workers=None, checkpoint_every=None):
    """Run `plan` to the end, or to the tick an owner is killed at.

    A call whose journal holds no `start` line for `run_id` begins the run; a call
    whose journal already holds one resumes it — the checkpoint is read and must
    be this run's and this plan's, the leases the crashed process left are waited
    out and expired, stage 5's `reclaimable` ids are re-issued under fresh owners,
    and the plan is finished. Returns §3.5's mapping: `states` and `report` read
    off the final log, `events` the journal's records, `clock` the tick the run
    stopped at, and `lost` what a crash in this call discarded.
    """
    jobs = _plan(plan)
    if not isinstance(disk, Disk):
        raise DurableError("a run works the world's Disk, got %r" % (disk,))
    if not isinstance(effects, work.Effects):
        raise DurableError(
            "a run acts on the world, a work.Effects, got %r" % (effects,))
    if clock is None:
        clock = fleet.Clock()
    elif not isinstance(clock, fleet.Clock):
        raise DurableError(
            "a run's clock is a fleet.Clock, or None for a fresh one, got %r"
            % (clock,))
    limit = _require_positive(limit, "limit")
    run_id = _require_text(run_id, "a run id")
    owners = _owners(workers)
    every = (None if checkpoint_every is None
             else _require_positive(checkpoint_every, "checkpoint_every"))
    plan_hash = _plan_hash(jobs)

    # ---- the log this call inherits, and whether it is this run's ----------

    kept = read_checkpoint(disk)
    if kept is not None and (kept.get("run"), kept.get("plan")) != (run_id,
                                                                    plan_hash):
        raise ResumeError(
            "the checkpoint on this disk is the run %r's over the plan %r, and "
            "this run is %r over the plan %r: a resume over somebody else's "
            "checkpoint is a second run wearing the first one's name"
            % (kept.get("run"), kept.get("plan"), run_id, plan_hash))
    lines = replay(disk)
    beginnings = [one for one in lines if one["kind"] == "start"]
    if lines and not beginnings:
        raise ResumeError(
            "the journal holds %d line(s) and no `start` line: a log no run "
            "begins is not this run's to finish" % (len(lines),))
    if beginnings and beginnings[0]["key"] != run_id:
        raise ResumeError(
            "the journal is the run %r's and this run is %r: a resume over "
            "somebody else's log is a second run wearing the first one's name"
            % (beginnings[0]["key"], run_id))
    if beginnings and beginnings[0]["text"] != plan_hash:
        raise ResumeError(
            "the journal's plan is %r and this run's is %r: the same run id over "
            "another plan is not the same run"
            % (beginnings[0]["text"], plan_hash))

    if beginnings:
        _lost, lines, states = _recovered(disk, clock)
    else:
        commit(disk, {"tick": clock.now(), "kind": "start", "key": run_id,
                      "text": plan_hash})
        states = {}

    # ---- the work that is left --------------------------------------------

    gone = set(reclaimable(lines, now=clock.now()))
    ready = [job_id for job_id in sorted(jobs)
             if _status(states.get(job_id, "pending")) not in _FINISHED]
    in_flight = {}
    roster = []
    claims = _count(lines, "claim")
    finished = sum(1 for job_id in sorted(jobs)
                   if _status(states.get(job_id, "pending")) in _FINISHED)

    def start_one(job_id):
        """Claim one job for the next owner and take its first answer."""
        nonlocal claims
        job = jobs[job_id]
        spec = _owner_at(owners, claims)
        roster.append(spec)
        now = clock.now()
        attempt = 1 + _count(replay(disk), "claim", job_id)
        if job_id in gone:
            gone.discard(job_id)
            write_line(disk, {"tick": now, "kind": "retry", "job": job_id,
                              "ticks": spec["ticks"]})
        lease = take(disk, job_id, spec["owner"], now=now, ticks=spec["ticks"])
        status, cost, detail = _answer(work.worker_for(job.label)(
            job, attempt=attempt), job_id)
        claims += 1
        return {"owner": spec["owner"], "spec": spec, "lease": lease,
                "ticks": spec["ticks"], "remaining": cost, "cost": cost,
                "attempt": attempt, "status": status, "detail": detail}

    def fill():
        """The cap: claims in the air, applied before the work, never after."""
        while len(in_flight) < limit and ready:
            job_id = ready.pop(0)
            in_flight[job_id] = start_one(job_id)

    def dying(now):
        """Is one of the owners this run handed a job to killed at `now`?

        The roster and not the workers *airborne*: a worker is a process, and a
        process whose tick has come stops existing whether or not it happens to
        be holding a lease at that moment. What the kill *costs* is another
        question, and the answer is always the same one — everything that was
        not synced.
        """
        for spec in roster:
            if spec["dies_at"] is not None and spec["dies_at"] == now:
                return True
        return False

    # ---- the loop: one tick, one set of decisions -------------------------

    fill()
    while in_flight or ready:
        if dying(clock.now()):
            return _stopped(disk, effects, clock)
        now = clock.tick(1)
        if dying(now):
            return _stopped(disk, effects, clock)
        for job_id in sorted(in_flight):
            entry = in_flight[job_id]
            entry["lease"] = heartbeat(disk, entry["lease"], now=now,
                                       ticks=entry["ticks"])
        for job_id in sorted(in_flight):
            entry = in_flight[job_id]
            entry["remaining"] -= 1
            if entry["remaining"] > 0:
                continue
            _settle_effect(disk, effects, jobs[job_id], now)
            result = {"tick": now, "kind": "result", "job": job_id,
                      "owner": entry["owner"], "status": entry["status"],
                      "ticks": entry["cost"]}
            text = _token(entry["detail"])
            if text is not None:
                result["text"] = text
            write_line(disk, result)
            del in_flight[job_id]
            finished += 1
            if every is not None and finished % every == 0:
                checkpoint(disk, run_id, plan_hash,
                           states=state_of(replay(disk)), now=now)
        fill()
    commit(disk, {"tick": clock.now(), "kind": "done"})
    return _returned(disk, effects, clock)


def _stopped(disk, effects, clock):
    """The kill: discard what was never synced, and report this tick's mapping.

    `disk.crash()` is the whole mechanism — the volatile buffer goes and the lost
    text comes back — and everything returned afterwards is read from what the
    disk would keep. The `clock` is the tick the run stopped at, which is the
    owner's `dies_at` and not necessarily the highest tick the survivors carry:
    the difference between the two is exactly what the kill threw away.
    """
    lost = disk.crash()
    lines = tuple(replay(disk))
    states = state_of(lines)
    return {"states": states, "events": lines,
            "report": report(disk, lines, states=states, ticks=_top(lines),
                             effects=effects),
            "clock": clock.now(), "lost": lost}
