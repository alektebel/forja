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
"""

import rules
from machine import MachineError
from programs import PROGRAM_NAMES

RUN_KEYS = ("pids", "status", "waited", "deadlock")

_EXIT_OK = rules.EXIT_OK
_EXIT_FAILURE = rules.EXIT_FAILURE
_EXIT_CANNOT_EXECUTE = rules.EXIT_CANNOT_EXECUTE
_EXIT_NOT_FOUND = rules.EXIT_NOT_FOUND

#: The descriptor numbers a command is born with, in the order a shell sets them up.
_STDIO = (0, 1, 2)

#: The mode bits that make a file something an `exec` can become.
_EXEC_BITS = 0o111

#: The plan errors that mean "the command is not there", and the status each is worth.
_NOT_FOUND_ERRORS = ("unknown-program",)


def pipeline_status(statuses):
    """The status a pipeline of `statuses` answers with: its last command's.

    `statuses` is a sequence of statuses in pipeline order, and the answer is the
    last of them — never the first non-zero, never the largest, never a sum — which
    is the shell's own rule and not a summary. A pipeline with no status at all (no
    command ran, so nothing answered) is `rules.EXIT_OK`.
    """
    rows = _statuses_of(statuses, "a pipeline's statuses")
    if not rows:
        return _EXIT_OK
    return rows[-1]


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
    naming the offender.
    """
    if not isinstance(pids, (tuple, list)):
        raise MachineError("collect: pids is %r, not a tuple of pids" % (pids,))
    for pid in pids:
        _pid_of(pid, "collect")
    before = len(machine.deadlocks())
    statuses = []
    for pid in pids:
        if len(machine.deadlocks()) > before:
            break
        row = machine.wait(pid)
        if not isinstance(row, dict) or not isinstance(row.get("status"), int):
            break
        if len(machine.deadlocks()) > before:
            break
        statuses.append(row["status"])
    return tuple(statuses)


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
    strings, raises `MachineError` naming the offender.
    """
    argv, program, fds = _row_of(row)
    failure = _resolution(machine, program)
    pid = machine.spawn(argv, argv0=program)
    # The descriptor table is handed over even for a command that cannot run: the
    # pipe's write end must die with the child, or a reader downstream of a command
    # that does not exist would wait for a writer that will never come.
    _install(machine, pid, fds)
    if failure is not None:
        machine.exit(pid, failure)
    return pid


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
    `MachineError` naming the offender; the pipeline's own bad news is data.
    """
    commands, error = _plan_of(plan)
    if error is not None:
        return {"pids": (), "status": _error_status(error), "waited": (),
                "deadlock": False}
    before = len(machine.deadlocks())
    pids = tuple(spawn_command(machine, command) for command in commands)
    waited = collect(machine, pids)
    deadlock = len(machine.deadlocks()) > before
    status = _EXIT_FAILURE if deadlock else pipeline_status(waited)
    return {"pids": pids, "status": status, "waited": waited, "deadlock": deadlock}


# --- the shapes a caller must get right (a mismatch raises) ---------------

def _statuses_of(statuses, what):
    """The statuses of `statuses` as a tuple, or the mistake named."""
    if not isinstance(statuses, (tuple, list)):
        raise MachineError("%s is %r, not a sequence of statuses" % (what, statuses))
    for status in statuses:
        if not isinstance(status, int):
            raise MachineError("%s holds %r, which is not a status" % (what, status))
    return tuple(statuses)


def _pid_of(pid, what):
    """The pid `pid`, or the mistake named: a count, never a bool or a string."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
        raise MachineError("%s: %r is not a pid" % (what, pid))
    return pid


def _row_of(row):
    """`(argv, program, fds)` of one command row, or the mistake named."""
    if not isinstance(row, dict):
        raise MachineError("spawn_command: %r is not a command row" % (row,))
    argv = row.get("argv")
    program = row.get("program")
    fds = row.get("fds")
    if not isinstance(argv, (tuple, list)) or not argv:
        raise MachineError("spawn_command: argv %r is not a tuple of words" % (argv,))
    for word in argv:
        if not isinstance(word, str):
            raise MachineError("spawn_command: the word %r is not a string" % (word,))
    if not isinstance(program, str) or not program:
        raise MachineError("spawn_command: program %r is not a name" % (program,))
    if not isinstance(fds, dict):
        raise MachineError("spawn_command: fds %r is not a descriptor table" % (fds,))
    for number in fds:
        if not isinstance(number, int) or isinstance(number, bool) or number < 0:
            raise MachineError("spawn_command: %r is not a descriptor number"
                               % (number,))
        spec = fds[number]
        if not isinstance(spec, dict) or not isinstance(spec.get("kind"), str) \
                or not isinstance(spec.get("target"), (str, int)):
            raise MachineError("spawn_command: fd %d is %r, not a descriptor record"
                               % (number, spec))
    return tuple(argv), program, fds


def _plan_of(plan):
    """`(commands, error)` of a plan record, or the mistake named."""
    if not isinstance(plan, dict):
        raise MachineError("run_pipeline: %r is not a plan" % (plan,))
    commands = plan.get("commands")
    if not isinstance(commands, (tuple, list)):
        raise MachineError("run_pipeline: commands %r is not a tuple of rows"
                           % (commands,))
    for row in commands:
        _row_of(row)
    return tuple(commands), plan.get("error")


def _error_status(error):
    """The status a plan's own error is worth: 127 only for a missing program."""
    kind = error.get("kind") if isinstance(error, dict) else error
    if kind in _NOT_FOUND_ERRORS:
        return _EXIT_NOT_FOUND
    return _EXIT_FAILURE


# --- the machine's side of the tree --------------------------------------

def _resolution(machine, program):
    """`None` if `program` can be executed, else 126 (found) or 127 (not).

    The world's own programs need no path; anything else has to be a file the
    machine holds whose mode says it may be executed. A name the machine has never
    heard of is not found at all, which is the distinction a user reads as "typo"
    against "permission".
    """
    name = program.rsplit("/", 1)[-1]
    if name in PROGRAM_NAMES and (program == name or machine.exists(program)):
        return None
    if machine.exists(program):
        return _EXIT_CANNOT_EXECUTE
    return _EXIT_NOT_FOUND


def _install(machine, pid, fds):
    """Give the child every descriptor the plan's table names, in number order.

    A `pipe` number is handed the shell's own end (`give`, which transfers it); a
    `file` number is opened for the child and moved onto its number with `dup2`, and
    two numbers of one command that name the same file share a single open (which is
    what the plan's `2>&1` reading means); a `terminal` number is already the child's
    own standard descriptor, so the shell says nothing.
    """
    opened = {}
    for number in sorted(fds):
        spec = fds[number]
        kind = spec["kind"]
        target = spec["target"]
        if kind == "terminal":
            continue
        if kind == "pipe":
            machine.give(pid, number, target)
            continue
        if kind == "file":
            mode = "append" if spec.get("append") else ("read" if number == 0
                                                        else "write")
            key = (target, mode)
            if key in opened:
                machine.dup2(pid, opened[key], number)
                continue
            source = machine.open(pid, target, mode)
            if source != number:
                machine.dup2(pid, source, number)
                machine.close(pid, source)
            opened[key] = number
            continue
        raise MachineError("spawn_command: fd %d has the kind %r, which is not a "
                           "descriptor this shell can make" % (number, kind))
