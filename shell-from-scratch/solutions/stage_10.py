"""Shell From Scratch — stage 10: Exit codes, and the audit of a session's statuses.

Nine stages turned a line of text into processes and a status. This one asks the
question a user actually asks: *why* was that status that number? A bare `1` is not a
diagnosis. `127` and `126` are two different kingdoms — the first says no such command
exists, the second says the command is there and may not be run — and a shell that
prints either one as "it failed" has thrown away the only fact that would have told
the user whether to fix a typo or a permission. `128 + n` is not a status at all: it is
a signal wearing a status's clothes, and `143` is `TERM` and nothing else. A trap's
status is the shell's own, not the command's (`§4.6`), and a job nobody waited for has
no status yet — only a promise.

So the audit is an *explanation* of a session, one row per step:

    AUDIT_KEYS = ("session", "steps", "verdict", "reasons")

    AUDIT_REASONS = ("status-from-last-pipeline", "errexit-exempt-condition",
                     "errexit-exempt-and-or-left", "errexit-exempt-negated",
                     "not-found-127", "cannot-execute-126", "redirection-failed",
                     "signalled-128-plus-n", "trap-status", "job-not-waited",
                     "deadlock-reported")

    VERDICTS = ("holds", "differs", "incomplete")

    audit(machine, session, options) -> AUDIT_KEYS

`steps` is one `{"index", "command", "status", "reason"}` row per step the replay ran,
`reasons` is the distinct reasons the session used in `AUDIT_REASONS` order, and
`verdict` compares the replayed record against the world's own expected record:
`holds`, `differs` — the first differing key is then named in `steps`' last row —
or `incomplete` when the machine could not finish the session at all.

DESIGN DECISION — why is every reason decided from the evidence rather than from the
fixture's expected record?
Because a diagnostic that agrees with the answer key is not a diagnostic. The world's
own `scripts.session(name)["expected"]` is the session's *verdict*, and it is the one
thing this stage may not read while explaining a step: the reasons come from the plan
this stage builds, the kind the replay recorded, and the machine's own transcript, and
the expected record is used once, at the end, as the thing the replayed record is
compared to. That is why a check can hand this stage an expected record that is
deliberately wrong and still demand the same eleven reasons: an audit that read the
answer would change its story with it.

DESIGN DECISION — why are 127 and 126 two reasons, and why is `128 + n` never read as a
plain status?
Because they are three kinds of bad news and a user acts differently on each.
`not-found-127` is a missing program: the line named something the machine has never
heard of, and the plan says so before anything is spawned. `cannot-execute-126` is a
program the machine *has* — a file at that path that is not a program the machine can
become — and `machine.exists` is what tells the two apart, because a planner that
answered "no such program" for both would make the distinction invisible at exactly the
moment it matters. `128 + n` is neither: the process was killed by the machine, and the
status is `rules.SIGNAL_STATUS_BASE` plus `rules.SIGNAL_NUMBERS[name]`. The one command
whose status is an arbitrary number a user chose is `exit`, which is why `exit 143` is
a plain status and a reaped `143` is `TERM`.

DESIGN DECISION — why does a trap's status carry its own reason, and why is a background
job's row a reason and not a status?
Because both are cases where the number a user sees is *not* the command's. `§4.6` says
the status of the last trap to run becomes the shell's own, so a boundary a trap fired
at has a status the command never produced; the audit records the trap's own row and
names that reason, which is the only way the record does not lie about where the number
came from. A job started with `&` is the mirror image: the shell did not wait, so there
is no status to report yet, and `job-not-waited` says exactly that rather than
pretending the `0` the shell carries is the command's verdict.

DESIGN DECISION — why does this stage replay the session itself instead of calling stage
9's `run_session`?
Because `options` is an input to the replay — `options["errexit"]` turns `set -e` on for
a session whose own lines never say so — and `run_session(machine, script)` has nowhere
to carry it. An audit also has to see every step *as it ran*: the plan for the step, the
kind the line recorded, the boundary a trap fired at, the tick the machine stopped
making progress on. A composed record has thrown all of that away by the time it comes
back. So the loop of `§3` is written once more here, with the evidence kept, and the
record it builds is the same `SESSION_KEYS` record stage 9 builds — which is what makes
the verdict a comparison rather than a judgement.

DESIGN DECISION — why is `incomplete` a verdict of its own rather than a `differs`?
Because "the machine could not finish this session" and "the machine finished it and the
answer is different" are different facts about a run. When the scheduler records a
deadlock — every runnable process blocked and no signal able to free one — the session
never reached its last line, so comparing its record against the expected one would be
comparing a partial run against a whole one and calling the difference a defect. The
deadlock is the machine's own report (`machine.deadlocks()`), so the verdict is decided
from the machine and not from the shape of the record.

The replay keeps three pieces of evidence for every step, and never a fourth: the plan
for the command, the kind the line recorded, and the machine's own transcript. The plan
is re-derived for the commands of each line as the line runs, the kind comes back in
`stage_08`'s own status rows, and the transcript is where the signals a session sent
come from — so a reason is a fact about the run, not a table lookup on a number.
"""

from machine import MachineError

import programs
import rules
import scripts
import stage_01
import stage_02
import stage_03
import stage_05
import stage_06
import stage_07
import stage_08
import stage_09

AUDIT_KEYS = ("session", "steps", "verdict", "reasons")

AUDIT_REASONS = ("status-from-last-pipeline", "errexit-exempt-condition",
                 "errexit-exempt-and-or-left", "errexit-exempt-negated",
                 "not-found-127", "cannot-execute-126", "redirection-failed",
                 "signalled-128-plus-n", "trap-status", "job-not-waited",
                 "deadlock-reported")

VERDICTS = ("holds", "differs", "incomplete")

#: A line the shell cannot read at all is reported with the usage status: `§3`'s
#: parse error is data, exactly as stage 9 reads it.
_PARSE_STATUS = rules.EXIT_BAD_USAGE

#: The option names `options` may carry. An audit that silently ignored a name it
#: did not know would report a run it did not perform. `condition` is the tuple of
#: line texts the caller says a condition ran — `§4.1`'s grammar has no `if` or
#: `while`, so no line records a condition's kind, and the audit believes the
#: caller's word for those lines and no others.
_OPTIONS = ("errexit", "condition")

#: The best news a status can be and the reason that holds when no other rule does.
_PLAIN = "status-from-last-pipeline"

#: The three kinds `§4.8` records for a condition, all exempt for the same reason.
_CONDITIONS = ("condition", "if-condition", "while-condition")

#: The signal numbers, for the one arithmetic that turns a status back into a signal.
_NUMBERS = tuple(sorted(rules.SIGNAL_NUMBERS.values()))

#: The order the replayed record's keys are compared in, which is the order a
#: `differs` verdict names its first difference in.
_RECORD_KEYS = stage_09.SESSION_KEYS

def audit(machine, session, options):
    """Replay one fixture session and explain every step's status.

    `session` is the *name* of a fixture in `scripts.names()` — or a session record
    of the same shape — and `options` is a record of audit options: `errexit` turns
    `set -e` on for the whole replay, whether or not the session's own lines ever
    say so, and any other name raises `MachineError` naming it. A session shape
    that cannot be replayed, and a name no fixture answers to, raise the same way,
    before the machine is touched.

    The answer is an `AUDIT_KEYS` record. `steps` is one
    `{"index", "command", "status", "reason"}` row per step the replay ran, in
    order: for a command, the status the line recorded and the reason it was that
    number, and for a trap that fired at a boundary, its own row carrying
    `trap-status`. Every reason is chosen by the first rule in `AUDIT_REASONS`'
    order that matches the evidence — the plan for the step, the kind the replay
    recorded, the machine's own transcript — and never from the fixture's expected
    record.

    `reasons` is the distinct reasons the session used, in `AUDIT_REASONS` order.
    `verdict` is `incomplete` when the machine recorded a deadlock while the replay
    ran (it could not finish the session), `differs` when it ran to the end and the
    replayed record is not the world's own expected one — the first differing key
    is then named in the last step row's `command` — and `holds` when the two agree.
    """
    script = _session_of(session)
    name, lines = _lines_of(script)
    flags = _options(options)
    conditions = tuple(flags.get("condition") or ())
    state = _state_of(machine, flags)
    marks = _mark(machine)
    steps = []
    statuses = []
    status = rules.EXIT_OK
    for line in lines:
        parsed = stage_01.parse(line)
        if parsed["error"] is not None:
            status = _PARSE_STATUS
            continue
        evidence = _evidence(machine, parsed["lists"], state)
        before = machine.stats()["deadlocks"]
        ran = stage_08.run_lists(machine, parsed["lists"], state)
        _steps_for(machine, steps, statuses, ran, evidence,
                   machine.stats()["deadlocks"] > before,
                   conditions if line in conditions else ())
        fired = stage_06.run_traps(machine, state["traps"])
        for row in fired:
            steps.append({"index": len(steps), "command": "trap " + str(row["name"]),
                          "status": row["status"], "reason": "trap-status"})
        status = fired[-1]["status"] if fired else ran["status"]
        if state["exit"] is not None:
            status = state["exit"]
            break
        if ran["stopped"]:
            break
    record = _record(machine, marks, name, lines, status, statuses, state)
    verdict, steps = _verdict(script.get("expected"), record,
                              _deadlocks(machine, marks) > 0, steps)
    return {"session": name, "steps": tuple(steps), "verdict": verdict,
            "reasons": _reasons(steps)}


def _steps_for(machine, steps, statuses, ran, evidence, blocked, conditions=()):
    """One step per command the line ran, with the plan's evidence beside it.

    The statuses the line recorded are `stage_08`'s own rows, and the evidence is
    this stage's plan for the same commands; the two are lined up by
    `_aligned`. The line's last row is the one a deadlock is charged to: it is
    the pipeline the machine stopped making progress on, and the one whose status
    the line answered with. The record's own `statuses` grow here too, as the
    `(index, status, kind)` triples `§4.9` pins — the kinds the replay itself
    recorded, because the caller's word about a condition is an audit's *reading*
    and not the run's.

    `conditions` is the tuple of command texts the caller says ran as a
    condition: a row whose command is one of them is *explained* as
    `errexit-exempt-condition` whatever kind the run recorded, and nothing else
    about it changes.
    """
    rows = ran["statuses"]
    plans = _aligned(evidence, rows)
    for position, row in enumerate(rows):
        believed = "condition" if _text(row.get("command")) in conditions \
            else row.get("kind")
        steps.append({"index": len(steps), "command": _text(row.get("command")),
                      "status": row["status"],
                      "reason": _reason(machine, dict(row, kind=believed),
                                        plans[position],
                                        blocked and position == len(rows) - 1)})
        statuses.append((len(statuses), row["status"], row["kind"]))


def _reason(machine, row, plan, deadlock):
    """Why the step's status was the number it was: the first rule that matches.

    The rules are `AUDIT_REASONS` in order. The first of them — a status that is
    simply its pipeline's last command's — is the rule that holds when nothing else
    explains the number, so it is answered last and reported first: every other
    rule is a predicate on the evidence, the recorded kind and the number itself,
    and a step that matches none of them is the plain case. A command the plan
    refused is asked of `_kingdom`, which is where the number and the machine's own
    filesystem have to agree about which of the two refusals it was.
    """
    kind = row.get("kind")
    status = row.get("status")
    program = plan["argv"][0] if plan["argv"] else None
    if kind in _CONDITIONS:
        return "errexit-exempt-condition"
    if kind == "and-or-left":
        return "errexit-exempt-and-or-left"
    if kind == "negated":
        return "errexit-exempt-negated"
    kingdom = _kingdom(machine, program)
    if kingdom is not None:
        return kingdom
    if status == rules.EXIT_NOT_FOUND:
        return "not-found-127"
    if status == rules.EXIT_CANNOT_EXECUTE:
        return "cannot-execute-126"
    if plan["error"] is not None:
        return "redirection-failed"
    if _signalled(program, status):
        return "signalled-128-plus-n"
    if plan["background"]:
        return "job-not-waited"
    if deadlock:
        return "deadlock-reported"
    return _PLAIN


def _kingdom(machine, program):
    """Which kingdom a command the machine cannot run belongs to, or `None`.

    `not-found-127` is "no such command": the machine's own filesystem holds nothing
    at that name, so there is nothing to execute and the line's words named a typo.
    `cannot-execute-126` is "found, but not executable": the file is there and it is
    not a program the machine can become. A program the world holds needs no path
    and a builtin is this shell's own word rather than a child's program, so both
    are `None` — the two kingdoms are for everything else, and `machine.exists` is
    the door that tells them apart.
    """
    if not isinstance(program, str):
        return None
    if program in programs.PROGRAM_NAMES or stage_07.is_builtin(program):
        return None
    if machine.exists(program):
        return "cannot-execute-126"
    return "not-found-127"


def _signalled(program, status):
    """Whether a status is a signal's `128 + n` rather than a command's own number.

    A process the machine killed answers the base plus the signal's number, and a
    shell that read that as an exit code has lost the only fact that makes `143`
    mean `TERM`. The one command whose status is a number a user picked is `exit`,
    which is why `exit 143` is a plain status and a reaped `143` is not.
    """
    if program == "exit" or isinstance(status, bool) or not isinstance(status, int):
        return False
    if status < rules.SIGNAL_STATUS_BASE:
        return False
    return status - rules.SIGNAL_STATUS_BASE in _NUMBERS


def _reasons(steps):
    """The distinct reasons the session used, in `AUDIT_REASONS` order."""
    used = []
    for reason in AUDIT_REASONS:
        for step in steps:
            if step["reason"] == reason:
                used.append(reason)
                break
    return tuple(used)


# --- the plan's own evidence, per command of a line -----------------------

def _evidence(machine, lists, state):
    """One plan row per command of a parsed line, in the order the line runs them.

    The evidence is what `§4.10` says a reason may be decided from, and nothing
    here runs: `redirects_of` expands the words and walks the redirections left to
    right without making a pipe, storing a here-document or spawning a child. The
    words as written are kept beside the expanded argv so the two sequences — the
    plan's commands and the statuses the line recorded — can be lined up later,
    because a short-circuited list leaves holes in the second and not in the first.
    """
    rows = []
    for pipelines, _ in lists:
        for pipeline in pipelines:
            for command in pipeline:
                refused = stage_03.redirects_of(machine, command, state)["error"]
                rows.append({"text": " ".join(command["words"]),
                             "argv": _argv_of(machine, command, state),
                             "error": refused if refused else None,
                             "background": bool(command.get("background"))})
    return tuple(rows)


def _argv_of(machine, command, state):
    """A command's expanded words, in order, from `§4.2`'s own expansion.

    This is the same call `stage_03` makes when it plans the command, so the argv
    the evidence carries is the argv the plan would have run — and a word whose
    expansion is an error contributes no word, exactly as expansion says.
    """
    words = []
    for word in command["words"]:
        record = stage_02.expand(machine, word, state)
        if record["error"] is None:
            words.extend(record["words"])
    return tuple(words)


def _aligned(evidence, rows):
    """Which plan row each recorded status row belongs to.

    The line runs its commands in order, so the recorded rows are the plan's own
    commands minus the ones a short-circuit never ran: a row is matched to the
    first unconsumed plan row whose words are the ones the replay wrote for it, and
    a row whose words match none of them — a refused command is written as the
    pipeline it was, not as the words it named — keeps the next unconsumed plan
    row, because the two sequences are still one sequence with holes in it.
    """
    plans = []
    cursor = 0
    for row in rows:
        text = _text(row.get("command"))
        chosen = cursor
        for index in range(cursor, len(evidence)):
            if evidence[index]["text"] == text:
                chosen = index
                break
        if chosen >= len(evidence):
            plans.append(_no_plan())
            continue
        plans.append(evidence[chosen])
        cursor = chosen + 1
    return tuple(plans)


def _no_plan():
    """The evidence of a step no plan of this line accounts for."""
    return {"text": "", "argv": (), "error": None, "background": False}


def _text(value):
    """A recorded step's command as one line of text, whatever the replay wrote.

    `stage_08` records the command it ran; a command that could not be planned is
    written as the pipeline it was, which this stage reads as the words that
    pipeline named. Anything else is named as it stands, so every step has a
    command to print.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)):
        words = []
        for command in value:
            if isinstance(command, dict) and "words" in command:
                words.extend(command["words"])
            else:
                words.append(str(command))
        return " ".join(words)
    return "" if value is None else str(value)


# --- the record, and the verdict it earns ---------------------------------

def _record(machine, marks, name, lines, status, statuses, state):
    """The replay's own `SESSION_KEYS` record, from the machine's evidence.

    Every field is measured from the mark taken before the first line and not from
    what the machine already held: `children` and `deadlocks` are the ledger's own
    deltas, `signals` is read back out of the transcript, and `stdout` is the bytes
    the terminal did not have before. A script with no lines has no status to
    report and answers `EXIT_OK`, which is `§4.9`'s empty case.
    """
    return {"name": name,
            "stdout": _stdout(machine, marks),
            "status": status if lines else rules.EXIT_OK,
            "statuses": tuple(statuses),
            "children": _spawned(machine, marks),
            "signals": _signals(machine, marks),
            "jobs": tuple(stage_05.jobs(machine, state["jobs"])),
            "deadlocks": _deadlocks(machine, marks)}


def _verdict(expected, record, blocked, steps):
    """The verdict the replay earned, and the steps it leaves behind.

    The deadlock comes first because the machine's own report outranks the
    comparison: a session the scheduler could not finish is `incomplete` however
    much of its record agrees with the answer key. Otherwise the two records are
    compared key by key in `SESSION_KEYS` order, and the first key they disagree on
    is named in the last step row's `command` — the contract's way of saying which
    key a `differs` verdict is about, since the record has no key of its own.
    """
    named = list(steps)
    if blocked:
        return "incomplete", named
    key = _difference(expected, record)
    if key is None:
        return "holds", named
    if named:
        last = named[-1]
        named[-1] = {"index": last["index"], "command": key,
                     "status": last["status"], "reason": last["reason"]}
    return "differs", named


def _difference(expected, record):
    """The first `SESSION_KEYS` key the two records disagree on, or `None`.

    A record that is not a mapping at all cannot agree about anything, so its first
    key is the first difference: the comparison never raises on the answer key,
    because a wrong answer key is what a `differs` verdict is *for*.
    """
    if not isinstance(expected, dict):
        return _RECORD_KEYS[0]
    for key in _RECORD_KEYS:
        if key not in expected or expected[key] != record[key]:
            return key
    return None


# --- the machine's own evidence -------------------------------------------

def _mark(machine):
    """Where the machine's evidence stood first: transcript, spawns, deadlocks, stdout.

    The record's `children`, `signals`, `deadlocks` and `stdout` are the machine's
    own, measured from here, so a replay answers for what it did and not for what
    the machine already held when it was handed over.
    """
    stats = machine.stats()
    return (len(machine.transcript()), stats["spawn"], stats["deadlocks"],
            len(machine.terminal()))


def _spawned(machine, marks):
    """How many processes the replay spawned, from the machine's own ledger."""
    return machine.stats()["spawn"] - marks[1]


def _deadlocks(machine, marks):
    """How many deadlocks the machine recorded while the replay ran."""
    return machine.stats()["deadlocks"] - marks[2]


def _stdout(machine, marks):
    """The bytes the replay's own lines put on the terminal."""
    return machine.terminal()[marks[3]:]


def _signals(machine, marks):
    """The names the replay sent, in order, from the machine's own transcript."""
    sent = []
    for entry in machine.transcript()[marks[0]:]:
        if entry["call"] == "signal":
            sent.append(entry["args"][-1])
    return tuple(sent)


# --- the caller's own shapes ----------------------------------------------

def _session_of(session):
    """The world's own record for a session, from its name or from itself.

    A name is looked up in the world's fixtures — `scripts.session(name)`, which
    carries the lines to replay and the expected record to compare against — and a
    record is taken as it stands. A name no fixture answers to is a caller's
    mistake and raises, naming it, before anything is replayed.
    """
    if isinstance(session, str):
        try:
            script = scripts.session(session)
        except Exception:                                    # noqa: BLE001
            script = None
        if not isinstance(script, dict):
            raise MachineError("stage 10: no fixture session is named %r" % (session,))
        return script
    if isinstance(session, dict):
        return session
    raise MachineError("stage 10: a session is a name or a session record, and %r is "
                       "neither" % (session,))


def _lines_of(script):
    """A session's name and lines, or the refusal naming what cannot be a session."""
    name = script.get("name")
    lines = script.get("lines")
    if not isinstance(name, str):
        raise MachineError("stage 10: a session's name is a string, and %r is not"
                           % (name,))
    if isinstance(lines, str) or not isinstance(lines, (tuple, list)):
        raise MachineError("stage 10: a session's lines are a sequence of strings, "
                           "and %r is not" % (lines,))
    for line in lines:
        if not isinstance(line, str):
            raise MachineError("stage 10: %r is not a line of a session" % (line,))
    return name, tuple(lines)


def _options(options):
    """The audit's own options, validated by name before the replay starts.

    The audit has exactly one option, and a name it does not know raises rather
    than being ignored: an audit that quietly dropped an option would report a run
    it did not perform, and the record would look right while being a different
    run's.
    """
    flags = {"errexit": False}
    if options is None:
        return flags
    if not isinstance(options, dict):
        raise MachineError("stage 10: options is a mapping, and %r is not" % (options,))
    for key in options:
        if key not in _OPTIONS:
            raise MachineError("stage 10: %r is not an option of an audit, which knows "
                               "%s" % (key, ", ".join(_OPTIONS)))
        flags[key] = options[key]
    return flags


def _state_of(machine, flags):
    """A fresh shell state for one replay, carrying the audit's own flags.

    The state is born in the call that owns the replay, which is both the law
    (there is no module-level mutable state) and the reason two audits of one
    session cannot leak into each other. `errexit` comes from `options` and not
    from the session's own lines, which is what makes an option the session never
    uses still honoured.
    """
    return {"variables": {}, "exported": (), "traps": (), "jobs": (),
            "flags": {"errexit": flags["errexit"], "nounset": False},
            "cwd": machine.cwd(), "exit": None, "args": (), "stdin": b""}
