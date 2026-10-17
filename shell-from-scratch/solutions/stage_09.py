"""Shell From Scratch — stage 9: The session, replayed byte for byte.

A session is the whole course at once: lines of text in, one record out, and that
record has to be the world's own expected record byte for byte and number for
number. `run_session` owns no step of its own — it does not tokenise, expand,
plan, fork, wait, trap or decide `set -e` — it owns the *shell*: the state that
survives from one line to the next, the record that says what happened, and the
one rule that makes the record checkable, that the world already holds the answer.

    the machine is the world: the session calls its accessors and answers
    a line is parse -> expand -> plan -> run -> record, in that order, always
    a session is those five steps once per line, with the state carried between
    the record is the same keys the world's own fixtures are written in

The surface, and the state the lines travel in:

    SESSION_KEYS = ("name", "stdout", "status", "statuses", "children",
                    "signals", "jobs", "deadlocks")

    SHELL_KEYS = ("variables", "exported", "traps", "jobs", "flags", "cwd",
                  "exit", "args", "stdin")

    run_session(machine, script) -> SESSION_KEYS

`script` is a record with `name` and `lines`; `SESSION_KEYS` is exactly
`scripts.session(name)["expected"]`, so the acceptance is a comparison with the
world's own answer key rather than a judgement call. The `SHELL_KEYS` mapping is
built by `run_session` and handed down to the stages that read or mutate it in
place: `state["variables"]` is what `expand` is given, `state["flags"]` is where
`set -o` writes, `state["jobs"]` is the job table, `state["traps"]` is §4.6's
table, and `state["cwd"]` is where `cd` left the shell.
"""

import machine as world
import rules
import stage_01
import stage_05
import stage_06
import stage_08

SESSION_KEYS = ("name", "stdout", "status", "statuses", "children", "signals",
                "jobs", "deadlocks")

SHELL_KEYS = ("variables", "exported", "traps", "jobs", "flags", "cwd", "exit",
              "args", "stdin")

#: A line the shell cannot read at all is reported with the usage status and does
#: not end the session: a parse error is a shell outcome that is data (§3).
_PARSE_STATUS = rules.EXIT_BAD_USAGE


def _script_of(script):
    """The name and the lines of a session record, or the refusal naming what is wrong.

    A session is a mapping with a string `name` and a sequence of string `lines`;
    anything else is a caller's mistake and raises before the machine is touched.
    """
    if not isinstance(script, dict):
        raise world.MachineError("stage 9: a session is a mapping, and %r is not"
                                 % (script,))
    for key in ("name", "lines"):
        if key not in script:
            raise world.MachineError("stage 9: the session has no %r field" % (key,))
    name = script["name"]
    if not isinstance(name, str):
        raise world.MachineError("stage 9: a session's name is a string, and %r is not"
                                 % (name,))
    lines = script["lines"]
    if isinstance(lines, str) or not isinstance(lines, (tuple, list)):
        raise world.MachineError("stage 9: a session's lines are a sequence of "
                                 "strings, and %r is not" % (lines,))
    for line in lines:
        if not isinstance(line, str):
            raise world.MachineError("stage 9: %r is not a line of a session" % (line,))
    return name, tuple(lines)


def _state_of(machine):
    """A fresh shell state for one session, and the only mutable thing in this module.

    The law forbids module-level mutable state, so the state is born in the call
    that owns the session: that is why two runs of one session cannot leak into
    each other — the second run builds its own.
    """
    return {"variables": {}, "exported": (), "traps": (), "jobs": (),
            "flags": {"errexit": False, "nounset": False},
            "cwd": machine.cwd(), "exit": None, "args": (), "stdin": b""}


def _mark(machine):
    """Where the machine's own evidence stood first: transcript, spawns, deadlocks, stdout.

    The record's `children`, `signals`, `deadlocks` and `stdout` are the machine's
    own, measured from here, so a session answers for what it did and not for what
    the machine already held when it was handed over.
    """
    stats = machine.stats()
    return (len(machine.transcript()), stats["spawn"], stats["deadlocks"],
            len(machine.terminal()))


def _spawned(machine, marks):
    """How many processes the session spawned, from the machine's own ledger."""
    return machine.stats()["spawn"] - marks[1]


def _deadlocks(machine, marks):
    """How many deadlocks the machine recorded while the session ran."""
    return machine.stats()["deadlocks"] - marks[2]


def _stdout(machine, marks):
    """The bytes the session's own lines put on the terminal."""
    return machine.terminal()[marks[3]:]


def _signals(machine, marks):
    """The names the session sent, in order, from the machine's own transcript.

    Every door the machine opens is recorded with its call and its arguments, so
    the signals a session sent are a fact the machine already holds: this stage
    reads them rather than remembering its own sends, which is why a session that
    sent nothing answers `()`.
    """
    sent = []
    for entry in machine.transcript()[marks[0]:]:
        if entry["call"] == "signal":
            sent.append(entry["args"][-1])
    return tuple(sent)


def _boundary(machine, state):
    """Fire the pending traps at a command boundary; the last one's status, or `None`.

    §4.6: the traps fire at a command boundary, never in the middle of a pipeline,
    once each, and the status of the last trap to run becomes the shell's own —
    which is why this answers the last row's status rather than the command's.
    """
    rows = stage_06.run_traps(machine, state["traps"])
    if not rows:
        return None
    return rows[-1]["status"]


def run_session(machine, script):
    """One whole session's transcript, against the machine's own evidence.

    `script` is a record with `name` and `lines`; the lines are driven through
    §4.1 to §4.8 in order, carrying one shell state, and the answer is a
    `SESSION_KEYS` record: `stdout` the bytes the terminal holds at the end,
    `status` the session's own, `statuses` every command's status in order as
    `(index, status, kind)`, `children` the processes the session spawned,
    `signals` the names it sent in order, `jobs` the job table's rows at the end
    and `deadlocks` what the machine recorded.

    The session's own status is the last line's status, the status that stopped
    it, or `rules.EXIT_OK` for a script with no lines and no statuses. A shape
    that cannot be a session — not a mapping, no `name`, no `lines`, a line that
    is not a string — raises `world.MachineError` naming the offender; a parse
    error, a failing command or a deadlock is data in the record and not an
    exception.
    """
    name, lines = _script_of(script)
    state = _state_of(machine)
    marks = _mark(machine)
    statuses = []
    status = rules.EXIT_OK
    for line in lines:
        parsed = stage_01.parse(line)
        if parsed["error"] is not None:
            status = _PARSE_STATUS
            continue
        ran = stage_08.run_lists(machine, parsed["lists"], state)
        for row in ran["statuses"]:
            statuses.append((len(statuses), row["status"], row["kind"]))
        status = ran["status"]
        fired = _boundary(machine, state)
        if fired is not None:
            status = fired
        if state["exit"] is not None:
            status = state["exit"]
            break
        if ran["stopped"]:
            break
    jobs = stage_05.jobs(machine, state["jobs"])
    return {"name": name,
            "stdout": _stdout(machine, marks),
            "status": status if lines else rules.EXIT_OK,
            "statuses": tuple(statuses),
            "children": _spawned(machine, marks),
            "signals": _signals(machine, marks),
            "jobs": tuple(jobs),
            "deadlocks": _deadlocks(machine, marks)}
