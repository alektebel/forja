"""Shell From Scratch — stage 6: Signals, traps, and what a signal does to a job.

A signal is the one thing a shell has to carry both ways: it decides what to send, and
it decides what a signal that arrived means. The machine keeps the first half — a
signal is a name, the numbers are `rules.SIGNAL_NUMBERS`, and the default action is the
machine's own: `INT`, `QUIT` and `TERM` kill, `STOP` stops, `CONT` resumes, and a
process that died of a signal answers `128 + n`, which is why `status_of` exists at
all. The shell keeps the second half: a trap is a row in the shell's own table, and
`run_traps` is where the shell's status stops being the command's and becomes the last
trap's.

Nothing about a trap is the machine's. The machine delivers a signal and records what
the process did about it; the shell decides whether a signal it received means "run
this command" (`trap ... CMD`), "do what you would have done anyway" (`""`, the
signal's default) or "never see this again" (`"-"`). `STOP` and `CONT` are not
trappable at all: they are the machine's own words for a job's state, and a shell that
let a trap swallow a `CONT` would have a job nobody could restart.

    TRAP_KEYS                                 the three fields of one trap, in order
    STATUS_KEYS                               the four fields of a signal's consequence
    TRAPPABLE                                 the signals a shell may trap
    status_of(name)                           -> int, the status a signal answers with
    deliver(machine, pid, name)               -> STATUS_KEYS, what the machine recorded
    trap(machine, name, action)               -> one TRAP_KEYS row, armed
    run_traps(machine, table)                 -> the rows it ran, in signal-number order
    run_kill(machine, argv, table)            -> STATUS_KEYS, the signal it sent

The trap table is the shell's own: a tuple of `TRAP_KEYS` rows, read and mutated in
place by `run_traps`. A row is *due* when its action is a real command (not `""`, not
`"-"`) and it has not fired yet; firing it runs the action, marks the row, and resets
it to the signal's default — unless the action was the `trap` builtin naming its own
signal, which is what "a trap that set itself again" means and the only way it fires a
second time.
"""

import programs
import rules
import stage_05
from machine import MachineError

TRAP_KEYS = ("name", "action", "fired")

STATUS_KEYS = ("pid", "status", "signalled", "signal")

TRAPPABLE = ("HUP", "INT", "QUIT", "TERM", "CHLD")

_DEFAULT = ""
_IGNORE = "-"
_ANSWERED = ("exited", "waited")


def status_of(name):
    """The status a process that died of `name` answers with: `128 + number`.

    The whole of a shell's understanding of a signal's status is this one sum:
    `INT` is 2 and a process that died of it answered 130, `TERM` is 15 and it
    answered 143, and a reader that treats 143 as a plain exit code has lost the
    one fact that makes it a signal. The numbers are the world's
    (`rules.SIGNAL_NUMBERS`) and the base is the policy's
    (`rules.SIGNAL_STATUS_BASE`), so no number is written twice.

    A name that is not one of `rules.SIGNAL_NAMES` raises `MachineError` naming
    it — including a lower-case spelling of a signal that exists, because a
    signal's name is the machine's own word for it.
    """
    if not isinstance(name, str) or name not in rules.SIGNAL_NAMES:
        raise MachineError("status_of: %r is not a signal; the signals are %s"
                           % (name, _spoken(rules.SIGNAL_NAMES)))
    return rules.SIGNAL_STATUS_BASE + rules.SIGNAL_NUMBERS[name]


def deliver(machine, pid, name):
    """Send `name` to `pid` and answer what the machine did about it.

    The signal is sent through the machine's own door and the machine is given
    the one tick it needs to deliver it — a signal is delivered at a step
    boundary and nowhere else — so the row that comes back is the signal's
    *consequence* and not its intent:

    * a process that died of *that* signal answers `status_of(name)` with
      `signalled` true and `signal` naming the signal; the machine's own
      `status(pid)` is that same number, and a stage that answered anything else
      would disagree with the process it is describing;
    * a process that signal stopped — and that was not already stopped — answers
      `rules.EXIT_OK` with `signalled` false and `signal` naming what stopped it,
      because a stop is the machine's word for a job that is still there;
    * one that had already answered — `exited` or `waited` — answers its own
      status with `signalled` false and no signal at all: the shell is told what
      the process did, not what the shell asked for;
    * anything else answers `rules.EXIT_OK` with neither a signal nor a kill to
      report, because nothing happened: a signal that leaves the process running
      (`CHLD`, or a `CONT` that resumed it), one that leaves it where it already
      was, and a program that happened to finish during the tick are all rows
      whose status is the process's own and not the signal's.

    A pid the machine does not hold and a name that is not a signal are the
    caller's mistakes and raise `MachineError` naming the offender.
    """
    number = status_of(name)
    was = machine.state(pid)
    if was in _ANSWERED:
        return {"pid": pid, "status": machine.status(pid),
                "signalled": False, "signal": None}
    machine.signal(pid, name)
    machine.advance()
    state = machine.state(pid)
    if state == "stopped" and was != "stopped":
        return {"pid": pid, "status": rules.EXIT_OK,
                "signalled": False, "signal": name}
    if state in _ANSWERED:
        if machine.status(pid) == number:
            return {"pid": pid, "status": number, "signalled": True, "signal": name}
        return {"pid": pid, "status": machine.status(pid),
                "signalled": False, "signal": None}
    return {"pid": pid, "status": rules.EXIT_OK,
            "signalled": False, "signal": None}


def trap(machine, name, action):
    """The shell's table row for `name`, with `action` as the signal's handler.

    `action` is a command line to run when the signal fires, `""` for the
    signal's own default disposition (which is what the row falls back to once it
    has fired) and `"-"` for a signal the shell has decided never to see again.
    The whole of a trap is this row — the shell remembers nothing about a trap
    that is not in the `action` field, so this function asks the machine nothing
    and leaves the world exactly where it found it; the caller stores the row it
    answers in the shell's own table.

    `STOP` and `CONT` may not be trapped, which is why `TRAPPABLE` and not
    `SIGNAL_NAMES` is the list this reads: they are the machine's own words for a
    job's state, and a trap on `CONT` would be a job nobody could restart. Any
    other name, or an action that is not a string, raises `MachineError` naming
    the offender.
    """
    if not isinstance(name, str) or name not in TRAPPABLE:
        raise MachineError("trap: %r is not a trappable signal; a shell may trap %s"
                           % (name, _spoken(TRAPPABLE)))
    if not isinstance(action, str):
        raise MachineError("trap: the action %r is not a string" % (action,))
    return {"name": name, "action": action, "fired": False}


def run_traps(machine, table):
    """Fire the traps the shell owes a run, in signal-number order, once each.

    A trap is due when its row's action is a real command — not `""`, which is
    the signal's default, and not `"-"`, which is a signal the shell never wants
    to see — and the row has not fired yet. The table is the shell's own tuple of
    `TRAP_KEYS` rows, read and mutated in place: a row that fires comes back
    reset to its default (`action` `""`, `fired` true) so that it does not fire
    again, unless its action was the shell's own `trap` builtin naming that same
    signal, in which case the row keeps the action it re-armed itself with and
    stays due for the next boundary.

    What comes back is the rows it ran, in the order it ran them: `{"name",
    "status", "output"}` each, the status the action answered and the bytes it
    printed on the shell's own stdout. **The shell's own status is the last
    row's** — with two traps due at once it is the trap that ran last that the
    shell carries, and that trap's status, not the status of whatever command
    the boundary just finished. An empty answer means nothing was due and the
    command's own status survives.

    A table that is not a sequence of rows, a row that carries anything but
    `TRAP_KEYS`, a name that is not trappable and an action that is not a string
    all raise `MachineError` naming the offender. A trap never fires in the
    middle of a pipeline: this is called at a command boundary and the caller
    owns where that boundary is.
    """
    rows = _table(table)
    fired = []
    for row in _due(rows):
        status, output, again = _act(machine, rows, row["name"], row["action"])
        if again is None:
            row["action"] = _DEFAULT
            row["fired"] = True
        else:
            row["action"] = again
            row["fired"] = False
        fired.append({"name": row["name"], "status": status, "output": output})
    return tuple(fired)


def run_kill(machine, argv, table):
    """The `kill` builtin: send a signal to a job or a pid and answer its row.

    `argv` is the words after `kill`, already expanded: an optional signal as
    `-NAME` or `-NUMBER` (the number is looked up in `rules.SIGNAL_NUMBERS`, so
    `kill -2` and `kill -INT` are the same word), defaulting to `TERM`, and one
    target. The target is resolved through stage 5's own `resolve`, so `%1`,
    `%+`, `%-` and a plain pid all mean what §4.5 says they mean; the signal is
    then sent through the machine by `deliver`, which is also where the
    `STATUS_KEYS` row comes from.

    `STOP` and `CONT` may be sent — they are the machine's own job control, not a
    trap — and so may any other signal in `rules.SIGNAL_NAMES`. A usage error
    (no target, more than one, or a word that is not a signal) is the caller's
    mistake and raises `MachineError` naming the offending word, because a
    `STATUS_KEYS` row has nowhere to carry a complaint.
    """
    words = _words(argv)
    name = "TERM"
    if words and words[0].startswith("-"):
        name = _requested(words[0][1:])
        words = words[1:]
    if len(words) != 1:
        raise MachineError("kill: the usage is `kill [-SIGNAL] pid|%%job`, and %s "
                           "names no single target" % (_spoken(words) or "nothing",))
    return deliver(machine, stage_05.resolve(table, words[0]), name)


def _spoken(words):
    """The words as one spaced sentence, for a refusal that has to name them."""
    return ", ".join(repr(word) for word in words)


def _table(table):
    """The shell's trap table, validated once and answered as a tuple of rows."""
    if not isinstance(table, (tuple, list)):
        raise MachineError("run_traps: %r is not a trap table; the table is a tuple "
                           "of %s rows" % (table, _spoken(TRAP_KEYS)))
    rows = []
    for row in table:
        if not isinstance(row, dict) or sorted(row) != sorted(TRAP_KEYS):
            raise MachineError("run_traps: %r is not a trap row; a row carries %s"
                               % (row, _spoken(TRAP_KEYS)))
        name = row["name"]
        if not isinstance(name, str) or name not in TRAPPABLE:
            raise MachineError("run_traps: %r is not a trappable signal; a shell may "
                               "trap %s (the row %r)"
                               % (name, _spoken(TRAPPABLE), row))
        if not isinstance(row["action"], str):
            raise MachineError("run_traps: the action %r is not a string (the row %r)"
                               % (row["action"], row))
        if not isinstance(row["fired"], bool):
            raise MachineError("run_traps: the fired flag %r is not a bool (the row %r)"
                               % (row["fired"], row))
        rows.append(row)
    return tuple(rows)


def _due(rows):
    """The rows the shell owes a run at this boundary, in signal-number order."""
    owed = [row for row in rows
            if row["action"] not in (_DEFAULT, _IGNORE) and not row["fired"]]
    return tuple(sorted(owed, key=_number))


def _number(row):
    """The number of a row's signal, which is the order two traps run in."""
    return rules.SIGNAL_NUMBERS[row["name"]]


def _act(machine, rows, name, action):
    """One trap's action: the status it answered, what it printed, and what it re-armed."""
    words = tuple(action.split())
    if words and words[0] == "trap":
        return rules.EXIT_OK, b"", _arm(rows, name, words[1:])
    if not words or words[0] not in programs.PROGRAM_NAMES:
        return rules.EXIT_NOT_FOUND, b"", None
    return _run(machine, words)


def _run(machine, words):
    """Run one program as the shell's own child, and answer its status and its output."""
    before = machine.terminal()
    answer = machine.wait(machine.spawn(words))
    after = machine.terminal()
    return answer["status"], after[len(before):], None


def _arm(rows, name, args):
    """The `trap` builtin, run as a trap's own action: arm, reset or ignore a signal.

    A trap whose action is the shell's own `trap` command is a trap that sets
    itself again, and that is the only way one fires twice: the words are the
    builtin's operands, the action comes first and the signals after it, and
    quoting inside an action is §4.1's business rather than a re-lexing here. It
    can only arm signals the table already holds a row for — the table is the
    caller's tuple and a trap cannot add to a sequence it does not own — so a
    `trap` naming a signal nobody armed changes nothing but the shell's status.
    """
    if len(args) < 2:
        raise MachineError("trap: the builtin takes an action and a signal, and %r "
                           "names one of them" % ("trap " + " ".join(args),))
    action = args[0]
    if action in ('""', "''"):
        action = _DEFAULT
    targets = args[1:]
    for target in targets:
        if target not in TRAPPABLE:
            raise MachineError("trap: %r is not a trappable signal; a shell may trap %s"
                               % (target, _spoken(TRAPPABLE)))
    for row in rows:
        if row["name"] in targets:
            row["action"] = action
            row["fired"] = False
    if name in targets and action not in (_DEFAULT, _IGNORE):
        return action
    return None


def _words(argv):
    """`argv` as a tuple of words, or the refusal naming what is not one."""
    if isinstance(argv, (str, bytes)) or not isinstance(argv, (tuple, list)):
        raise MachineError("kill: %r is not an argv; kill takes a sequence of words"
                           % (argv,))
    for word in argv:
        if not isinstance(word, str):
            raise MachineError("kill: %r is not a word" % (word,))
    return tuple(argv)


def _requested(text):
    """The signal `text` names, by name or by number, or the refusal naming it."""
    if text in rules.SIGNAL_NAMES:
        return text
    for name in rules.SIGNAL_NAMES:
        if text == str(rules.SIGNAL_NUMBERS[name]):
            return name
    raise MachineError("kill: %r is not a signal; the signals are %s"
                       % ("-" + text, _spoken(rules.SIGNAL_NAMES)))
