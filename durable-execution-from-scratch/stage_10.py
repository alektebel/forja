"""Durable Execution From Scratch — stage 10: Two workers, one killed holding the lease.

Nine stages have fixed one decision each: what a line is, which lines are facts,
how a log is replayed, what a lease is, when a silent owner is dead, what a
process that wakes up may believe, how an effect happens exactly once, how a
resume owns a log, and how a run's numbers come back out of it. This stage is the
run itself: a plan, two workers and one of them killed in the middle — and a log
that has to be enough, on its own, for somebody else to finish the work.

    DEFAULT_LIMIT  how many jobs the run has in the air at once
    LEASE_TICKS    how long a synthetic owner's claim lasts
    run            plan, disk, effects, clock and the owners in, §3.5's mapping out

The run is a loop of ticks and one decision per tick. It claims up to `limit`
jobs at once (two workers, in the air together), beats the leases it holds,
writes a `result` when an attempt ends, and, before any effect, commits an
`intent` and syncs it — because the world is the one thing a crash cannot take
back. When an owner's `dies_at` tick arrives the caller's worker stops existing:
the run performs the kill (`disk.crash()`), returns at that tick, and hands back
what the crash discarded. The next call to this same `run` over the same disk is
the process that comes after it.

DESIGN DECISION — why is the cap a count of *claims in the air*, and why does the
run claim before it works?
    Because the whole stage is about a lease that somebody died holding, and a
    lease only matters while its owner is not the only process that knows about
    it. `limit` therefore bounds the jobs claimed and not yet answered with a
    `result`, and the claims go out *before* any of that batch is worked: with
    the default of two, two `claim` lines are in the log before the first
    `result` is, which is the shape every reader of this stage's fixtures has to
    be able to count. A cap applied after the claims is not a cap, and a run that
    claimed one job, finished it and claimed the next would never have a second
    worker in the air to kill.

DESIGN DECISION — why are the owners named in the order the log claims, and never
reused?
    Because an owner label is a fact about the log, not about a process. `w1` in
    a `claim` line is the first owner the log ever heard from, and the process
    that reads that log has to be able to tell the owner that is gone from the
    owner that is asking. So the synthetic owners are `w1`…`wN` in claim order,
    and an explicit `workers` tuple is handed out round-robin *by position across
    the log's claims* — which means a resume continues where the crash left off
    instead of starting at the first label again. A label reused by the second
    process for the same job makes one owner look like two, and the log that was
    supposed to be the only channel between the processes stops saying which of
    them died holding the slot.

DESIGN DECISION — why are there two death paths and only one mechanism?
    Because a kill costs exactly what was not synced, and where the kill lands
    decides which kind of lease the next process finds — and the log has to be
    able to say which. An owner killed *before* any sync leaves no trace of its
    claim at all: the claim is written and never synced (stage 4's `claim`, on
    purpose), so the next read finds no lease, the job is `pending`, and the
    resume re-issues it at once. An owner killed *after* a sync — its claim made
    durable by a checkpoint's barrier, which is a sync over everything written
    before it — leaves a lease the next process must honour until it lapses, so
    the job is `running` until `deadline + MAX_MISSES` and `expired` after that,
    and only then is it reclaimable. Same `crash()`, same disk, same function;
    the difference is a sync, and the difference is the lesson.

DESIGN DECISION — why does the resume wait out a lapsed lease instead of
re-issuing the ids recovery names?
    Because a lease that has not lapsed is a promise somebody else may still be
    keeping, and a resume that takes it a tick early is exactly the second worker
    this course exists to refuse. Stage 5's `reclaimable` answers only for the
    leases that are *dead*, so a job whose owner is gone but whose grace has not
    run out is not in that tuple; the resume advances the injected clock to the
    first tick the lease is dead at (`deadline + MAX_MISSES`), lets stage 6 write
    the `expire` line there, and only then re-issues the id under a fresh owner.
    Waiting is a number of ticks and not a wall clock reading — the clock is
    injected, so "waited too long" is a fixture and not a race.

DESIGN DECISION — why is an effect redone only through stage 7's `settle`, and
why do the states come from the log and never from the run?
    Because the two things a crash leaves behind are a synced `intent` and a
    world that may or may not have been touched, and neither of them is the run's
    memory. A re-issued job asks `settle`, which reads the journal and then the
    world: an `effect` line the log already holds means the effect landed (write
    nothing), a key the world applied means the line can be recorded without
    applying again, and only a key the world never saw is applied — always under
    the job's own key, so however many times the run is resumed the world ends
    with exactly one application per key. And the mapping `run` returns is read
    off the final journal (`state_of`, `report`, the disk's own durable bytes):
    the run's own table is a *prediction* while it works and is worth nothing to
    the process after it, which has only the bytes.

TODO: implement `DEFAULT_LIMIT`, `LEASE_TICKS` and `run`.
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
#: counts claims that no `result` has answered — a job finished and a job claimed
#: are not the same thing, and the second one is what a crash costs.
DEFAULT_LIMIT = 2

#: How long a claim lasts when the caller names no workers: the synthetic owners
#: have no script of their own, so every one of them is granted the same lease.
LEASE_TICKS = 4


def run(plan, *, disk, effects, clock=None, limit=DEFAULT_LIMIT, run_id="run-1",
        workers=None, checkpoint_every=None):
    """Run `plan` to the end, or to the tick an owner is killed at.

    `plan` maps a job id to a `work.Job`; `disk` is the world's disk and
    `effects` the world the run acts on; `clock` is the injected clock (a fresh
    `fleet.Clock` when the caller names none); `limit` is how many jobs may be in
    the air at once; `workers` is `None` — one synthetic owner per claim, named
    `w1`…`wN`, each granted `LEASE_TICKS`, nobody dies — or a tuple of
    `{"owner", "ticks", "dies_at"}` mappings handed out round-robin; and
    `checkpoint_every` is `None` or the number of finished jobs between stage 8's
    checkpoints.

    A call whose disk holds no `start` line for `run_id` begins the run: the
    `start` line is committed and the plan is worked. A call whose disk already
    holds one *resumes* it: the checkpoint is read (and refused when it is not
    this run's or this plan's), the leases the crashed process left are waited
    out and expired, stage 5's `reclaimable` ids are re-issued under fresh owners,
    and the plan is finished. Returns §3.5's mapping — `states` and `report` read
    off the final log, `events` the journal's records, `clock` the tick the run
    stopped at, and `lost` what a crash in *this* call discarded.
    """
    raise NotImplementedError("stage 10: implement run()")
