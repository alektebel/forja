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


DESIGN DECISION — Why does `run_session` own no step of the pipeline it drives?
Because composition is the stage's whole job: parse, expand, plan, run, trap
and `set -e` are already built and checked, and a session that re-implemented
any of them could disagree with the stage that owns the step while passing
every fixture the owning stage wrote. So this stage owns the *shell* — the
state that survives between lines, the record, and the order — and nothing
else.

DESIGN DECISION — Why is the acceptance a comparison against the world's own expected record
rather than a set of assertions?
Because the fixtures are the answer key: `scripts.session(name)["expected"]
has the bytes, the statuses, the children, the signals, the jobs and the
deadlocks, and "byte for byte" is a comparison, not a judgement call. A
session that answers extra keys or drops one fails the same comparison a
wrong status fails — which is the discipline the whole course is held to.

DESIGN DECISION — Why is the shell's state born inside `run_session` rather than at module
level?
Because the law forbids module-level mutable state, and the reason is not
ceremony: two runs of one session must not leak into each other, and the
check runs each fixture twice. A state born in the call is a state that dies
with the call — the same reason `stage_10`'s replay builds its own.

DESIGN DECISION — Why are `children`, `signals` and `deadlocks` read off the machine's own
ledger rather than counted by the session?
Because the machine is the record: it counted the spawns, wrote the signal
sends into its transcript, and recorded the deadlocks — and a session that
counted its own would be grading its own homework. Measuring from a mark
taken before the first line also makes the answer about *this session* and
not about whatever the machine did before it was handed over.
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

    SESSION_KEYS  the eight fields of a session record, in order
    SHELL_KEYS    the nine keys of the shell's own state
    run_session(m, script) -> SESSION_KEYS

TODO: implement `run_session` in this file.
"""

import machine as world
import rules
import stage_01
import stage_05
import stage_06
import stage_08

SESSION_KEYS = ('name', 'stdout', 'status', 'statuses', 'children', 'signals', 'jobs', 'deadlocks')

SHELL_KEYS = ('variables', 'exported', 'traps', 'jobs', 'flags', 'cwd', 'exit', 'args', 'stdin')

_PARSE_STATUS = rules.EXIT_BAD_USAGE


def _script_of(script):
    """The name and the lines of a session record, or the refusal naming what is wrong.

    A session is a mapping with a string `name` and a sequence of string `lines`;
    anything else is a caller's mistake and raises before the machine is touched."""
    raise NotImplementedError("stage 9: implement _script_of()")


def _state_of(machine):
    """A fresh shell state for one session, and the only mutable thing in this module.

    The law forbids module-level mutable state, so the state is born in the call
    that owns the session: that is why two runs of one session cannot leak into
    each other — the second run builds its own."""
    raise NotImplementedError("stage 9: implement _state_of()")


def _mark(machine):
    """Where the machine's own evidence stood first: transcript, spawns, deadlocks, stdout.

    The record's `children`, `signals`, `deadlocks` and `stdout` are the machine's
    own, measured from here, so a session answers for what it did and not for what
    the machine already held when it was handed over."""
    raise NotImplementedError("stage 9: implement _mark()")


def _spawned(machine, marks):
    """How many processes the session spawned, from the machine's own ledger."""
    raise NotImplementedError("stage 9: implement _spawned()")


def _deadlocks(machine, marks):
    """How many deadlocks the machine recorded while the session ran."""
    raise NotImplementedError("stage 9: implement _deadlocks()")


def _stdout(machine, marks):
    """The bytes the session's own lines put on the terminal."""
    raise NotImplementedError("stage 9: implement _stdout()")


def _signals(machine, marks):
    """The names the session sent, in order, from the machine's own transcript.

    Every door the machine opens is recorded with its call and its arguments, so
    the signals a session sent are a fact the machine already holds: this stage
    reads them rather than remembering its own sends, which is why a session that
    sent nothing answers `()`."""
    raise NotImplementedError("stage 9: implement _signals()")


def _boundary(machine, state):
    """Fire the pending traps at a command boundary; the last one's status, or `None`.

    §4.6: the traps fire at a command boundary, never in the middle of a pipeline,
    once each, and the status of the last trap to run becomes the shell's own —
    which is why this answers the last row's status rather than the command's."""
    raise NotImplementedError("stage 9: implement _boundary()")


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
    exception."""
    raise NotImplementedError("stage 9: implement run_session()")
