"""Shell From Scratch — stage 5: The job table: background, stopped, and who waits for whom.

A process the shell decided not to wait for is still the shell's business: it
has a number the user can name, a state the user can read, and a status nobody
knows yet. The job table is that bookkeeping — one row per pipeline the shell
started without waiting for it, keyed by the small number a job spec names, and
answered from the machine's own process table rather than remembered separately.

The two readings the stage exists for are the ones a `wait` and a `jobs` disagree
about: a `wait` on a job that is already done answers its status without touching
the machine, and a `jobs` listing reaps what has finished but never waits for a
running one. `stop` and `resume` are the shell's mirror of the machine's own
`STOP` and `CONT`, and `resolve` is what turns `%1`, `%+`, `%-` and a pid into
the pid the row holds.


DESIGN DECISION — Why is `background` the only way a job is born?
Because a job is a promise about *who waits*: a pipeline started with `&` is
recorded and never waited for, and every other pipeline is waited for before
the shell moves on. Letting any other call create rows would make "who has
been waited for" a property of the caller's discipline rather than of the
table — and the table is the shell's answer to `jobs`, `wait` and `kill` alike.

DESIGN DECISION — Why is the machine's own process table the truth for `running` and `stopped`
while a `done` row is remembered by the shell?
Because the machine knows what it killed, stopped and reaped, and the shell
should not keep a second opinion: `jobs` reads the state off the machine and
reaps what it says has exited. But a `done` job is a fact the machine has
already forgotten — its pid is gone from the table — so the shell remembers
the status, which is the one fact a `wait` on that job still owes the user.

DESIGN DECISION — Why does `jobs` reap finished jobs but never wait for running ones?
Because the two look similar and mean the opposite: reaping is collecting a
status that already exists, waiting is blocking until one does. A `jobs`
listing that blocked would stop the prompt on a long job; a listing that did
not reap would show zombies as running. The line between them is `machine.
reapable()` and it is the whole implementation.

DESIGN DECISION — Why does `resolve` raise on a spec it cannot read instead of answering a row?
Because `%1` is the user's word for a row, and a spec that names nothing is a
caller's mistake at the keyboard — the same kingdom as a pid that does not
exist. The rest of the stage answers data because the shell carries on from a
stopped job or a finished one; there is nothing to carry on from when the
spec names no row at all.
    JOB_KEYS       the five fields of one job row, in order
    JOB_STATES     the three states a job can be in
    background(m, plan)   -> int, the job's pid, no wait
    stop(m, pid)          -> the row, stopped
    resume(m, pid)        -> the row, running again
    jobs(m, table)        -> tuple[JOB_KEYS], reaped, in job order
    resolve(table, spec)  -> int, the pid the spec names
    wait_for(m, table, spec) -> STATUS_KEYS

TODO: implement `background`, `stop`, `resume`, `jobs`, `resolve`, `wait_for`
in this file.
"""

from machine import MachineError
import stage_04
import rules

JOB_KEYS = ('job', 'pid', 'state', 'status', 'command')

JOB_STATES = ('running', 'stopped', 'done')

_DEADLOCK_STATUS = rules.EXIT_FAILURE


def _positive(number, what):
    """`number` as a small positive int, or a refusal naming it."""
    raise NotImplementedError("stage 5: implement _positive()")


def _plan_rows(plan):
    """The plan's command rows, validated, in plan order."""
    raise NotImplementedError("stage 5: implement _plan_rows()")


def _row_parts(row):
    """The four source fields of one job-table row, validated."""
    raise NotImplementedError("stage 5: implement _row_parts()")


def _observe(machine, pid):
    """The state and status the machine itself holds for `pid`.

    Only an exited pid is waited for; a waited one already has its status, and a
    running or stopped one is never made to finish here."""
    raise NotImplementedError("stage 5: implement _observe()")


def _numbered(table):
    """The table's `(job, pid)` pairs, validated and sorted by job number."""
    raise NotImplementedError("stage 5: implement _numbered()")


def background(machine, plan):
    """Start `plan` as a job and answer the last command's pid, without waiting."""
    raise NotImplementedError("stage 5: implement background()")


def stop(machine, pid):
    """Stop the job `pid`, and advance the tick that delivers the signal."""
    raise NotImplementedError("stage 5: implement stop()")


def resume(machine, pid):
    """Resume the job `pid`, and advance the tick that delivers the signal."""
    raise NotImplementedError("stage 5: implement resume()")


def jobs(machine, table):
    """The table's rows, reaped where finished, in job-number order."""
    raise NotImplementedError("stage 5: implement jobs()")


def _job_of_row(row):
    """The job number a row is sorted by."""
    raise NotImplementedError("stage 5: implement _job_of_row()")


def resolve(table, spec):
    """The pid `spec` names in `table`, or a refusal naming `spec`."""
    raise NotImplementedError("stage 5: implement resolve()")


def _resolve_name(pairs, spec):
    """The pid a `%` job spec names, or a refusal naming the spec."""
    raise NotImplementedError("stage 5: implement _resolve_name()")


def _remembered_status(table, pid):
    """The status `pid` is remembered with when the table marks it done."""
    raise NotImplementedError("stage 5: implement _remembered_status()")


def _wait_one(machine, table, pid):
    """The status row of one waited-for pid, remembered or reaped."""
    raise NotImplementedError("stage 5: implement _wait_one()")


def wait_for(machine, table, spec):
    """Wait for the job `spec` names, or for every job in `table`."""
    raise NotImplementedError("stage 5: implement wait_for()")
