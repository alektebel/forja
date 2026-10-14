"""Durable Execution From Scratch — stage 8: The resume, and the log that is not this run's.

A run is not the process that started it; it is the log on disk. This stage adds
the two things a log needs before a second process may pick up a first one's
work: a **checkpoint** — what the run had already folded, written whole and
synced before it is believed — and a `repair`, the one function in the course
that edits a log, for the half-written tail a kill leaves behind. And it adds the
refusal that makes a resume safe at all: a resume is allowed only over a
checkpoint that is *this* run's and *this* plan's, because a resume over somebody
else's log is a second run wearing the first one's name (contract §0).

    DEFAULT_CHECKPOINT  the checkpoint's path: the world's journal, plus a suffix
    ResumeError         what a resume refuses, and what a broken checkpoint raises
    checkpoint          write this run's states whole, synced, and return the length
    read_checkpoint     the checkpoint on disk, or None when there is none
    repair              drop a torn tail from a log, and return what was kept and lost
    resume              the checkpoint's states, the lines after it, and whose they are

DESIGN DECISION — why is the checkpoint a file of its own, and not a rewrite of the journal?
    Because the journal is evidence and a checkpoint is a summary, and a summary
    that eats its source cannot be checked against it. A resume replays the lines
    after the checkpoint, so the lines the checkpoint folded have to still be
    there: `repair` has to know what a torn tail was appended to, stage 9 counts
    the run's lines and compares them with the world, and stage 6 recovers a dead
    lease from the `claim` line the owner wrote — none of which survives a
    checkpoint that overwrites the journal. So the checkpoint is written *beside*
    the journal with `disk.replace` (a whole-file rewrite, never an append, so a
    crash leaves the old checkpoint or the new one and never a mixture), and the
    journal stays the append-only tail that follows it.

DESIGN DECISION — why is the checkpoint's path the journal's path plus a suffix?
    Because the two are one thing. The world owns the journal's path
    (`disk.DEFAULT_JOURNAL`) and a path a stage invented would be a path the next
    process cannot find; deriving the checkpoint's from the journal's means a
    journal that moves takes its checkpoint with it. A checkpoint without its
    journal is a summary of nothing — its states are only worth as much as the
    lines they were folded from.

DESIGN DECISION — why does `resume` replay only the lines after the checkpoint's tick?
    Because the checkpoint's states already fold every line at or before `now`,
    and this course's clock is what makes "after" a fact instead of a guess: ticks
    never go backwards, a line carries the tick it was written at, and a
    checkpoint is written at the end of a tick. Re-folding what was already folded
    is not harmless: an `intent` folded there would be reconciled a second time,
    and "the effect happened exactly once" is the one property this course will
    not let a resume soften.

DESIGN DECISION — why does a resume only believe what `disk.synced` holds, and write a checkpoint only when there is none?
    The first is contract §3.3's rule: a process that came after a crash may only
    believe what a crash would keep, so a line written and not synced did not
    happen — and neither did a checkpoint written and not synced. The second is
    the difference between resuming and starting: a run that finds no checkpoint
    is starting, and writes one (`resumed` is False, because *this* run wrote its
    own checkpoint); a run that finds one reuses it and writes nothing, because a
    resume that rewrote the checkpoint on every call would turn a read into a
    write and a summary into a second source of truth.

DESIGN DECISION — why does `resume` reconcile the replayed intents and apply nothing?
    Because a replay's job is to make the *log* true, not to do work. An effect
    that landed before the crash has an application in the world and no `effect`
    line in the log, so the run that comes after would apply it a second time;
    writing the line it can prove is what stops that. An intent the world never
    saw is left alone: the run re-applies it under the same key when it runs the
    job, which is a run's business and not a resume's. `effects` is a parameter
    for exactly this — the world is the only witness to what landed.

DESIGN DECISION — why is `repair` a text operation that keeps every complete line?
    Because a repair must not decide what a line means: it drops the fragment
    after the last terminator and nothing else, so a half-written line costs
    exactly itself. A repair that parsed the log would refuse to fix a log it
    cannot parse, and a repair that dropped the last *complete* line to be safe
    would throw away a decision the run really made — the mistake this stage
    names. It writes only when something was dropped, and it writes the kept
    prefix whole with `replace` and syncs it, because a repair a crash undoes is
    not a repair.

TODO: implement `DEFAULT_CHECKPOINT`, `ResumeError`, `checkpoint`,
`read_checkpoint`, `repair` and `resume`.
"""

from collections.abc import Mapping

import stage_01 as s1
from disk import DEFAULT_JOURNAL
from stage_01 import DurableError

#: The checkpoint's path: the world's journal path plus a suffix, because a
#: checkpoint and the journal it summarizes are one thing, and a reader that
#: finds one has to be able to find the other.
DEFAULT_CHECKPOINT = DEFAULT_JOURNAL + ".checkpoint"


class ResumeError(DurableError):
    """A checkpoint, a log or a resume this stage refuses.

    The refusal always names the offender — the run, the plan, the line, the
    field, the state — and, when the offender is a typo of a real name, the real
    name too: `run`/`plan`/`states` and the six statuses are exactly where a typo
    silently becomes a default.
    """


def checkpoint(disk, run_id, plan_hash, *, states, now):
    """Write this run's checkpoint whole, sync it, and return its length.

    A checkpoint is a *whole-file rewrite* (`disk.replace`) of
    `DEFAULT_CHECKPOINT`: after it the file reads the new checkpoint, and after a
    crash without the sync it reads the old one — never a mixture. It carries the
    run, the plan, the tick it was taken at and the states the run had folded by
    then; a blank run or plan, a tick that is not a non-negative int, a states
    table that is not a mapping and a state that is not one of the six are all
    refused, naming the offender.
    """
    raise NotImplementedError("stage 8: implement checkpoint()")


def read_checkpoint(disk):
    """The checkpoint on disk, or `None` when there is none.

    Read through `disk.synced` and not `disk.read`: a checkpoint a crash would
    take away is not a checkpoint. An empty file is no checkpoint; a file that is
    not a checkpoint is refused, naming it, because somebody wrote it by hand and
    guessing is worse than refusing.
    """
    raise NotImplementedError("stage 8: implement read_checkpoint()")


def repair(disk, *, path=DEFAULT_JOURNAL):
    """Drop a torn tail from the log at `path`, and return what was kept and lost.

    `kept` is the complete lines the log still holds, in order and without their
    terminators; `dropped` is the fragment that never got one, and it is `""` when
    nothing was torn. Every complete line is kept, however torn the tail after it
    is, and the kept prefix is written whole (`disk.replace`) and synced — but only
    when something was dropped.
    """
    raise NotImplementedError("stage 8: implement repair()")


def resume(disk, effects, *, now, run_id, plan_hash):
    """Pick this run up from its checkpoint, or start it.

    Returns `{"states", "resumed", "reused", "replayed", "checkpoint"}`: the table
    a process that just woke up must believe, whether a checkpoint was reused
    (`False` when this call had to write one), how many *jobs* the checkpoint
    already had, how many the replayed lines name, and the checkpoint in force. A
    checkpoint that names another run or another plan refuses by name, and so does
    a log that names another run; a torn tail refuses naming the fragment.
    """
    raise NotImplementedError("stage 8: implement resume()")
