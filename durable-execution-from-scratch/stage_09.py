"""Durable Execution From Scratch — stage 9: The report, and the number that has to come from the log.

A run is not the process that started it; it is the log on disk. So the last
thing a run hands back is not what it remembers but the numbers its lines
account for, recomputed from those lines every time somebody asks: the run's
memory is a *reading* of the log, and this stage is the arithmetic of the
original. It is also the two doors out of that arithmetic — `report` refuses a
caller's total the log contradicts, and `audit` reports where a table and the
log disagree instead of refusing.

A counter here is a count of *lines*, never of jobs: two attempts of one job are
two `result` lines and one job, and the number a reader can check is the one the
log holds. `report` therefore never echoes a number it was handed; it compares,
and every comparison it makes is a comparison the lines can decide.

    REPORT_KEYS  the eleven numbers a report carries, in the order it writes them
    report       those numbers, recomputed from the lines and the disk, refusing
                 a caller's total the log contradicts by naming the key and both
                 numbers
    audit        the same walk, told the other way: what the table is missing and
                 what it has extra, and how many lines the log holds

DESIGN DECISION — why do the counters count lines and not jobs?
    Because a job's history is several lines and the lines are what happened.
    `slow` in this course's own fixture is claimed twice, beaten once, intented
    twice, expired once, retried once and resultied twice: one job, and nine
    decisions a reader can count. A report that counted jobs would show one
    claim for a job that was taken from a dead owner and re-issued, which is
    precisely the story this course exists to tell; and a report that counted
    jobs could not distinguish a job attempted once from a job attempted three
    times. The counter is therefore `len(lines of that kind)`, and `jobs` is the
    number of *ids* the log names — a repeated id counts once, because a job is a
    name, while a repeated line counts twice, because a line is an event.

DESIGN DECISION — why is `ticks` the highest tick the log names, and why is a
caller's tick refused rather than preferred?
    Because a run's clock is not evidence. `report` is handed the tick the caller
    believes the run stopped at, and the only thing that can justify that belief
    is a line carrying it: the run stopped where its last decision was written,
    so the highest tick the lines name is the tick the run stopped at, and a
    caller that hands over a clock reading the log does not carry is describing a
    run that did not happen — the number would be the process's memory again,
    wearing the report's authority. It is refused naming the key and both
    numbers, because a report is exactly the place where a wrong total is cheap
    to make and expensive to notice.

DESIGN DECISION — why does `synced` count the disk's durable bytes over every
path, and not the journal's text?
    Because bytes are a fact about the disk and the report is the only place the
    course admits one. A byte that was written and not flushed is a byte a crash
    takes back, so it is not counted: the report's `synced` is the answer to "how
    much of this run would survive a power cut", and a number computed from
    volatile writes is the failure this whole course is about — a program
    believing a write it never synced. Every path counts and not just the
    journal, because a checkpoint is a fact too: the disk that keeps the
    checkpoint and the journal holds both, and a run resumed from it believes
    both.

DESIGN DECISION — why is `effects` counted off the lines but checked against the
world?
    Because the log must agree with what really happened, and the world is the
    only witness to that. The counter is the number of `effect` lines — the log's
    own account — and each key those lines name is then checked against
    `Effects.count(key)`: an `effect` line the world never saw is a log lying
    about an application, and a key the world applied more often than the log
    records is the same lie from the other side, and neither is a number a report
    may publish. Exactly-once is why the key exists at all, so the two numbers
    have to be the same number; a world that applied a key twice while the log
    records it once is the accident this stage refuses to launder into a count.

DESIGN DECISION — why does `audit` report where `report` refuses, and why does it
read `disk.synced`?
    Because a disagreement is sometimes the answer somebody is looking for: a
    check, a probe or a reader wants to know *where* a table and the log parted
    company, and an exception cannot say "these four lines are missing and this
    one is extra". So `audit` is the same walk with the findings returned —
    `missing` for the lines the log holds and the table does not name, `extra` for
    the lines the table names and the log does not hold, and `count` for how many
    lines the log holds, which is the number a table has to match. It reads
    `disk.synced` and not `disk.read` for the same reason `synced` counts durable
    bytes: a line the table believes that a crash would take away is exactly the
    disagreement worth reporting, and contract §3.3's rule — only what the disk
    would keep may be believed — is the test the table has to pass.

TODO: implement `REPORT_KEYS`, `report` and `audit`.
"""

from collections.abc import Mapping

import stage_01 as s1
from disk import DEFAULT_JOURNAL
from stage_01 import DurableError

#: The eleven numbers a report carries, in the order it writes them. The log
#: supplies ten — the run, the jobs, the seven kinds it counts and the tick it
#: stopped at — and the disk supplies the last: the durable bytes. A report whose
#: keys are not these, in this order, is a report a reader cannot trust twice.
REPORT_KEYS = ("run", "jobs", "claimed", "beats", "intents", "results",
               "effects", "expires", "retries", "ticks", "synced")


def report(disk, lines, *, states, ticks, effects):
    """The run's numbers, recomputed from the lines — and the disk's durable bytes.

    `lines` is the journal as a replay hands it over, `states` the table the
    caller believes, `ticks` the tick the caller says the run stopped at and
    `effects` the world it worked against. Every counter comes from the lines,
    `synced` from the disk, and every claim of the caller's that the log
    contradicts is refused by name — the key and both numbers. The result carries
    `REPORT_KEYS`, in that order.
    """
    raise NotImplementedError("stage 9: implement report()")


def audit(disk, lines):
    """The lines a table claims against the lines the disk would keep.

    The same walk as `report`, told the other way: where a report refuses, an
    audit reports. `missing` is every line the disk durably holds that the table
    does not account for, in the log's order; `extra` is every line the table
    names that the log does not durably hold, in the table's order; `count` is
    how many lines the log holds — the number a table has to match. An audit with
    nothing to report is a table that holds exactly the log, no more and no
    fewer.
    """
    raise NotImplementedError("stage 9: implement audit()")
