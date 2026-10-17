"""Shell From Scratch — stage 4: The process tree: fork, exec, wait and the status.

The stage that turns a plan into processes and then takes the processes back. One
child per command, in pipeline order, born with the plan's descriptor table; then the
shell waits for every one of them, because a process that has exited and not been
waited for is still in the machine's table. The two readings the stage exists for are
`pipeline_status` — a pipeline answers with its **last** command's status, never with
the first failure — and the machine's own proof that nothing was left behind:
`reapable()` empty and `stats()["wait"]` equal to the number of children.

A deadlock is data. `cat` with no input at the end of a pipe blocks forever, the
machine notices that nothing runnable is left and records it, and `wait` answers the
deadlock instead of hanging; the run reports it with `rules.EXIT_FAILURE` rather than
raising, and only the children that actually exited appear in `waited`. A command
whose program does not exist answers `EXIT_NOT_FOUND` and one that exists but is not a
program the machine can become answers `EXIT_CANNOT_EXECUTE`; both are returned, both
still have a pid, and neither raises.


DESIGN DECISION — Why is the pipeline's status the last command's, whatever the others answered?
Because that is the rule the shell's own `$?` implements: `false | true` is 0
and `true | false` is 1, and every summary other than "the last one" — first
failure, worst failure, a sum — is a different rule someone invented. The
check pins it with both orders, because a stage that implemented "first
non-zero" passes every happy-path test and fails exactly one.

DESIGN DECISION — Why must every child be reaped, and why does the run prove it?
Because a zombie is a leak the machine can see: `reapable()` lists it and
`stats()["wait"]` misses it. So `collect` waits for every pid, and the check
asserts both — a pipeline whose status is right but that leaves a zombie is
wrong, which is the whole point of grading the run and not just the number.

DESIGN DECISION — Why is a deadlock data rather than an exception?
Because the machine has already recorded what happened — `deadlocks()` holds
the pids and the fds — and a shell that turned that into a raise would lose
the record's own answer. The run reports `EXIT_FAILURE` with the children
that did exit in `waited`, which is what a real shell does when a pipeline
cannot finish: it says what it knows and carries on.

DESIGN DECISION — Why does a missing program answer a pid with status 127 instead of refusing?
Because the pipeline's arithmetic is the same either way: the child is born,
exits with 127, and is reaped like any other child. Raising would make the
caller handle a special case that the status already expresses — and 126
versus 127 (found but not executable against not found at all) is a
distinction the machine's own filesystem makes, so the stage passes it
through rather than flattening it.
    RUN_KEYS                    the four fields of a run, in order
    run_pipeline(m, plan)       -> RUN_KEYS, the whole run
    spawn_command(m, row)       -> int, the child's pid
    collect(m, pids)            -> the statuses, in pid order
    pipeline_status(statuses)   -> int, the last command's

TODO: implement `pipeline_status`, `collect`, `spawn_command`, `run_pipeline`
in this file.
"""

import rules
from machine import MachineError
from programs import PROGRAM_NAMES

RUN_KEYS = ('pids', 'status', 'waited', 'deadlock')

_EXIT_OK = rules.EXIT_OK

_EXIT_FAILURE = rules.EXIT_FAILURE

_EXIT_CANNOT_EXECUTE = rules.EXIT_CANNOT_EXECUTE

_EXIT_NOT_FOUND = rules.EXIT_NOT_FOUND

_STDIO = (0, 1, 2)

_EXEC_BITS = 73

_NOT_FOUND_ERRORS = ('unknown-program',)


def pipeline_status(statuses):
    """The status a pipeline of `statuses` answers with: its last command's.

    `statuses` is a sequence of statuses in pipeline order, and the answer is the
    last of them — never the first non-zero, never the largest, never a sum — which
    is the shell's own rule and not a summary. A pipeline with no status at all (no
    command ran, so nothing answered) is `rules.EXIT_OK`."""
    raise NotImplementedError("stage 4: implement pipeline_status()")


def collect(machine, pids):
    """Wait for every pid in `pids` and answer their statuses, in pid order.

    The answer is the tuple of the statuses the machine recorded, in the order the
    pids were given, and every pid has been reaped by the time this returns: the
    machine's `reapable()` no longer lists any of them, and `stats()["wait"]` has
    moved once per pid. A pid that has already exited is still waited for, so that
    its status is read from the machine rather than assumed.

    A pipeline that deadlocks is data: when the machine records a deadlock, waiting
    for the pids that are blocked on each other can never finish, so the pids that
    did exit are answered and the rest are left to the caller (`run_pipeline` reads
    the deadlock off the machine and reports it). An entry of `pids` that is not a
    small non-negative int, or a pid the machine never knew, raises `MachineError`
    naming the offender."""
    raise NotImplementedError("stage 4: implement collect()")


def spawn_command(machine, row):
    """Spawn one command of a plan and answer its child's pid.

    `row` is one of a plan's command rows — `{"argv", "program", "fds",
    "redirects"}` — and the child is born with exactly the descriptor table the
    plan built for it: every number in `fds` is opened or copied into the child
    before it is allowed to run, so a pipeline's reader holds its end of the pipe
    as soon as the shell has finished setting the table up. The pid is the child's,
    in the shell's own process table.

    A command whose program does not exist is `EXIT_NOT_FOUND` and one that exists
    but cannot be executed is `EXIT_CANNOT_EXECUTE`; neither raises, and both still
    answer a pid — a child that exits with that status — so the pipeline's
    arithmetic and the reaping are the same as for a command that worked. A `row`
    that is not a record with the plan's fields, or whose `argv` is not a tuple of
    strings, raises `MachineError` naming the offender."""
    raise NotImplementedError("stage 4: implement spawn_command()")


def run_pipeline(machine, plan):
    """Run a plan's pipeline and answer the `RUN_KEYS` record of the run.

    Every command in `plan["commands"]` gets one child, spawned in pipeline order,
    and only then is anything waited for — so the whole table is live before the
    first command can finish and the pipeline's processes can meet on their pipes.
    `pids` is those children's pids in the same order, `waited` is what they
    answered in that order, `status` is the *last* of them (`pipeline_status`), and
    `deadlock` says whether the machine recorded a deadlock while this pipeline ran
    — in which case the status is `rules.EXIT_FAILURE` and `waited` holds only the
    children that did exit.

    When the plan already carries an error, nothing is spawned and nothing is
    waited for: the answer is the status that error is worth (127 for a program
    that does not exist, 1 otherwise), an empty `pids` and `waited`, and
    `deadlock` false. A `plan` that is not a `PLAN_KEYS` record raises
    `MachineError` naming the offender; the pipeline's own bad news is data."""
    raise NotImplementedError("stage 4: implement run_pipeline()")


def _statuses_of(statuses, what):
    """The statuses of `statuses` as a tuple, or the mistake named."""
    raise NotImplementedError("stage 4: implement _statuses_of()")


def _pid_of(pid, what):
    """The pid `pid`, or the mistake named: a count, never a bool or a string."""
    raise NotImplementedError("stage 4: implement _pid_of()")


def _row_of(row):
    """`(argv, program, fds)` of one command row, or the mistake named."""
    raise NotImplementedError("stage 4: implement _row_of()")


def _plan_of(plan):
    """`(commands, error)` of a plan record, or the mistake named."""
    raise NotImplementedError("stage 4: implement _plan_of()")


def _error_status(error):
    """The status a plan's own error is worth: 127 only for a missing program."""
    raise NotImplementedError("stage 4: implement _error_status()")


def _resolution(machine, program):
    """`None` if `program` can be executed, else 126 (found) or 127 (not).

    The world's own programs need no path; anything else has to be a file the
    machine holds whose mode says it may be executed. A name the machine has never
    heard of is not found at all, which is the distinction a user reads as "typo"
    against "permission"."""
    raise NotImplementedError("stage 4: implement _resolution()")


def _install(machine, pid, fds):
    """Give the child every descriptor the plan's table names, in number order.

    A `pipe` number is handed the shell's own end (`give`, which transfers it); a
    `file` number is opened for the child and moved onto its number with `dup2`, and
    two numbers of one command that name the same file share a single open (which is
    what the plan's `2>&1` reading means); a `terminal` number is already the child's
    own standard descriptor, so the shell says nothing."""
    raise NotImplementedError("stage 4: implement _install()")
