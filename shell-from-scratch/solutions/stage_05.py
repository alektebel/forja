"""Shell From Scratch — stage 5: The job table: background, stopped, and who waits for whom.

The solution follows the template's five decisions: a job is born through
`background`, which answers the last command's pid and never waits; the machine's
own process table is the shared truth of `running` and `stopped`, while a `done`
row is remembered by the caller; `jobs` reaps exactly the pids the machine says
have exited; `stop` and `resume` signal and advance one tick; and `resolve` reads
a job number out of the table or a pid out of the spec itself.
"""

from machine import MachineError

import stage_04
import rules


JOB_KEYS = ("job", "pid", "state", "status", "command")

JOB_STATES = ("running", "stopped", "done")

#: A wait the machine cannot finish is a deadlock, and a deadlock is data: the
#: status a shell reports for a child it will never reap is plain failure.
_DEADLOCK_STATUS = rules.EXIT_FAILURE

def _positive(number, what):
    """`number` as a small positive int, or a refusal naming it."""
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise MachineError("%s %r is not a positive integer" % (what, number))
    return number


def _plan_rows(plan):
    """The plan's command rows, validated, in plan order."""
    if not isinstance(plan, dict):
        raise MachineError("plan is not a record: %r" % (plan,))
    error = plan.get("error")
    if error is not None:
        raise MachineError("plan carries the error %r and cannot be spawned" % (error,))
    commands = plan.get("commands")
    if not isinstance(commands, (tuple, list)) or not commands:
        raise MachineError("plan's commands are not a non-empty sequence: %r"
                           % (commands,))
    rows = []
    for row in commands:
        if not isinstance(row, dict):
            raise MachineError("plan row is not a record: %r" % (row,))
        argv = row.get("argv")
        if not isinstance(argv, (tuple, list)) or not argv:
            raise MachineError("plan row carries no argv: %r" % (row,))
        for word in argv:
            if not isinstance(word, str):
                raise MachineError("plan row argv holds %r, which is not a word"
                                   % (word,))
        rows.append(row)
    return tuple(rows)


def _row_parts(row):
    """The four source fields of one job-table row, validated."""
    if not isinstance(row, dict):
        raise MachineError("job table row is not a record: %r" % (row,))
    for key in ("job", "pid", "command"):
        if key not in row:
            raise MachineError("job table row has no %r: %r" % (key, row))
    job = _positive(row["job"], "job number")
    pid = _positive(row["pid"], "pid")
    command = row["command"]
    if not isinstance(command, str):
        raise MachineError("job %r carries %r as a command, not a line"
                           % (job, command))
    state = row.get("state", JOB_STATES[0])
    if state not in JOB_STATES:
        raise MachineError("job %r carries the state %r" % (job, state))
    return job, pid, command, state


def _observe(machine, pid):
    """The state and status the machine itself holds for `pid`.

    Only an exited pid is waited for; a waited one already has its status, and a
    running or stopped one is never made to finish here.
    """
    state = machine.state(pid)
    if state == "running":
        return "running", None
    if state == "stopped":
        return "stopped", None
    if state == "waited":
        return "done", machine.status(pid)
    if state == "exited":
        return "done", machine.wait(pid)["status"]
    raise MachineError("pid %r is in the unknown machine state %r" % (pid, state))


def _numbered(table):
    """The table's `(job, pid)` pairs, validated and sorted by job number."""
    if not isinstance(table, (tuple, list)):
        raise MachineError("job table is not a sequence: %r" % (table,))
    pairs = []
    for row in table:
        if not isinstance(row, dict):
            raise MachineError("job table row is not a record: %r" % (row,))
        if "job" not in row or "pid" not in row:
            raise MachineError("job table row has no job and pid: %r" % (row,))
        pairs.append((_positive(row["job"], "job number"),
                      _positive(row["pid"], "pid")))
    pairs.sort()
    return tuple(pairs)


def background(machine, plan):
    """Start `plan` as a job and answer the last command's pid, without waiting."""
    pids = [stage_04.spawn_command(machine, row) for row in _plan_rows(plan)]
    return pids[-1]


def stop(machine, pid):
    """Stop the job `pid`, and advance the tick that delivers the signal."""
    _positive(pid, "pid")
    machine.signal(pid, "STOP")
    machine.advance(1)


def resume(machine, pid):
    """Resume the job `pid`, and advance the tick that delivers the signal."""
    _positive(pid, "pid")
    machine.signal(pid, "CONT")
    machine.advance(1)


def jobs(machine, table):
    """The table's rows, reaped where finished, in job-number order."""
    if not isinstance(table, (tuple, list)):
        raise MachineError("job table is not a sequence: %r" % (table,))
    rows = []
    for row in table:
        job, pid, command, state = _row_parts(row)
        if state == "done":
            status = row.get("status")
            if isinstance(status, bool) or not isinstance(status, int):
                raise MachineError("done job %r carries the status %r"
                                   % (job, status))
        else:
            state, status = _observe(machine, pid)
        rows.append({"job": job, "pid": pid, "state": state,
                     "status": status, "command": command})
    rows.sort(key=_job_of_row)
    return tuple(rows)


def _job_of_row(row):
    """The job number a row is sorted by."""
    return row["job"]


def resolve(table, spec):
    """The pid `spec` names in `table`, or a refusal naming `spec`."""
    pairs = _numbered(table)
    if isinstance(spec, bool):
        raise MachineError("job spec %r is not a pid" % (spec,))
    if isinstance(spec, int):
        if spec < 1:
            raise MachineError("job spec %r is not a pid" % (spec,))
        return spec
    if not isinstance(spec, str):
        raise MachineError("job spec %r is neither a job nor a pid" % (spec,))
    if spec.startswith("%"):
        return _resolve_name(pairs, spec)
    if not spec.isdigit() or int(spec) < 1:
        raise MachineError("job spec %r is neither a job nor a pid" % (spec,))
    return int(spec)


def _resolve_name(pairs, spec):
    """The pid a `%` job spec names, or a refusal naming the spec."""
    if spec == "%+":
        if not pairs:
            raise MachineError("job spec %r names no job: the table is empty"
                               % (spec,))
        return pairs[-1][1]
    if spec == "%-":
        if len(pairs) < 2:
            raise MachineError("job spec %r names no job: there is no previous job"
                               % (spec,))
        return pairs[-2][1]
    if spec[1:].isdigit():
        number = int(spec[1:])
        for job, pid in pairs:
            if job == number:
                return pid
    raise MachineError("job spec %r names no job in the table" % (spec,))


def _remembered_status(table, pid):
    """The status `pid` is remembered with when the table marks it done."""
    for row in table:
        if row.get("pid") == pid and row.get("state") == "done":
            status = row.get("status")
            if isinstance(status, bool) or not isinstance(status, int):
                raise MachineError("done job %r carries the status %r"
                                   % (row.get("job"), status))
            return status
    return None


def _wait_one(machine, table, pid):
    """The status row of one waited-for pid, remembered or reaped."""
    status = _remembered_status(table, pid)
    if status is not None:
        return {"pid": pid, "status": status, "signalled": False, "signal": None}
    reaped = machine.wait(pid)
    status = reaped["status"]
    if status is None:
        status = _DEADLOCK_STATUS
    return {"pid": reaped["pid"], "status": status,
            "signalled": reaped["signalled"], "signal": reaped["signal"]}


def wait_for(machine, table, spec=None):
    """Wait for the job `spec` names, or for every job in `table`."""
    pairs = _numbered(table)
    if spec is None:
        answers = [_wait_one(machine, table, pid) for job, pid in pairs]
        if not answers:
            return {"pid": None, "status": 0, "signalled": False, "signal": None}
        return answers[-1]
    return _wait_one(machine, table, resolve(table, spec))
