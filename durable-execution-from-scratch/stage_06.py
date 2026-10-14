"""Durable Execution From Scratch — stage 6: Crash, and the process that comes after it.

A run is not the process that started it; it is the log on disk — and the moment
that sentence earns its keep is the kill. A crash the caller performs discards
every byte that was not synced, so the process that comes after the kill may
know *nothing* but what survived it, and this stage writes the function that
reads exactly that: not the log the crashed process believed, not the volatile
buffer it can still see, but the lines a crash would have kept.

    MAX_MISSES      the ticks of grace a lease past its deadline still gets
    RecoveryError   a journal a recovery refuses: a torn tail, a broken line, a
                    tick that is not a tick
    crash           perform the kill, replay only `disk.synced`, write the
                    `expire` lines the dead owners are owed, and return
                    `(lost, lines, states)`
    recovered       the same states from the disk alone, reading no volatile byte

DESIGN DECISION — why does `crash` take the caller's `lines` and then not
believe them?
    Because the parameter is the belief under test. The process that crashed
    still has its own line list — the one that includes the `result` it wrote and
    never synced — and the whole stage is the discovery that this list is not
    evidence: the survivors are re-read from `disk.synced` and the caller's lines
    decide nothing. A `crash` that folded the lines it was handed would report a
    job `done` that no disk would ever agree with, which is the failure mode the
    course is built to refuse.

DESIGN DECISION — why is the recovery rule folded here instead of imported from
stage 5?
    Because the ladder lets a stage import stage 1 and the provided world, never
    a sibling, and the rule has to live *somewhere* the next process can reach:
    `MAX_MISSES` is therefore restated with the fold that reads a lease out of
    the surviving claims — a dead owner's job is `expired`, a live owner's stays
    `running`, and a job the log names without ever deciding anything about it is
    `pending`. Nothing is invented: the table holds exactly the ids the surviving
    lines name, because the plan is not evidence and the lines are.

DESIGN DECISION — why does a recovery *write*, and why must those writes be
synced?
    Because a decision the next process cannot read is not a decision. The fold
    finds owners whose lease has died; `crash` records that finding as one
    `expire` line per dead owner, in job-id order, and syncs them — a decision
    that the next crash could lose would leave the log saying "running" for a
    job nobody is running. `recovered` writes nothing: it is the *reading* a
    process performs before it decides anything, so the same disk gives the same
    states whether it is asked through a kill or through a plain read.

DESIGN DECISION — why is a torn tail refused by index, rather than dropped or
repaired?
    Because a half-written line is a question the recovery must not answer. A
    text whose last line has no terminator is a write that never finished, and
    the two cheap answers are both wrong: dropping it silently loses a decision
    the crashed process may have been about to make, and repairing it invents
    bytes nobody wrote. So the refusal names the line's index and its text — and
    no byte is written, because refusing must cost nothing.

TODO: implement `MAX_MISSES`, `RecoveryError`, `crash` and `recovered` in
stage_06.py.
"""

from disk import DEFAULT_JOURNAL
from stage_01 import DurableError, JournalError, parse_line, write_line

#: How many ticks of grace a lease that passed its deadline is given before its
#: owner counts as dead — stage 5's `MAX_MISSES`, restated here because a stage
#: imports stage 1 and the provided world and never a sibling stage.
MAX_MISSES = 2


class RecoveryError(DurableError):
    """A journal a recovery refuses: a torn tail, a line it cannot parse, or a
    tick that is not a tick.

    Every refusal names the offender — the index and the text of the line, the
    tick — because a recovery that guesses is the failure this stage refuses and
    a message that does not say *where* leaves the caller guessing too.
    """


def crash(disk, lines, *, now):
    """Kill the run, and believe only what survived the kill.

    Calls `disk.crash()`, re-reads the survivors with `disk.synced` (the `lines`
    the caller hands in decide nothing), folds the recovery rule over them,
    writes and syncs one `expire` line per dead owner, and returns
    `(lost, lines, states)`: the text the crash discarded, the log the next
    process must read, and the states read from it.

    Refuses a tick that is not a non-negative int, and a surviving journal whose
    tail is torn or whose line cannot be parsed — naming the index and the text.
    """
    raise NotImplementedError("stage 6: implement crash()")


def recovered(disk, *, now, path=DEFAULT_JOURNAL):
    """The states the process that comes after a crash may believe.

    Reads `disk.synced(path)` — never `disk.read`, because a byte a crash would
    lose is not evidence — folds the same recovery rule `crash` folds, and
    returns the state table. Writes nothing, so the states equal what `crash`
    returns for the same disk.

    Refuses the same tick and the same torn or unparseable tail by name.
    """
    raise NotImplementedError("stage 6: implement recovered()")
