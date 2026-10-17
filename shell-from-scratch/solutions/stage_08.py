"""Shell From Scratch — stage 8: Lists, conditions and the rules of `set -e`.

The solution. A line's lists are run in order; `&&` and `||` are decided by the
left side's status before the right side runs; `;` runs whatever comes next; `&`
starts a job that is recorded and never waited for. Every status the line records
carries the kind that says whether `errexit` may stop on it, and the four operators
are the whole of the short-circuit.

Two boundaries are worth naming before the code. The shell's own state is the
caller's dict and is read and mutated in place — `set -o errexit` has to change the
flag this loop is reading, `exit` has to be visible to the caller, and a `cd` that
is the whole command has to move the shell. And the in-process path is taken only
for a sole simple command with no `&`: a builtin inside a pipeline is a child's
command, and a background list is the promise that the thing is not this shell.
"""

from machine import MachineError

import rules
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07

LISTS_KEYS = ("statuses", "status", "stopped", "skipped", "error")

STATUS_KINDS = ("plain", "condition", "and-or-left", "negated",
                "pipeline-but-last", "while-condition", "if-condition")

#: `condition_of`'s three kinds: the grammar has no `if` and no `while`, so the
#: kind is an input rather than something a parse could produce.
_CONDITION_KINDS = ("condition", "if-condition", "while-condition")

#: The four operators that join one list to the previous one.
_CONNECTORS = ("&&", "||", ";", "&")

#: The builtins stage 7 refuses because another stage owns them; §4.8 is where the
#: first word is turned into the call, so the line can carry a `wait`, a `kill` or
#: a `trap` like any other command.
_ROUTED = ("kill", "trap", "wait")

#: The two kinds of command that run in the shell's own process: stage 7's builtins
#: and the ones whose owner this stage calls instead.
_NEGATION = "!"

_STATE_KEYS = ("variables", "exported", "jobs", "flags", "exit")


def run_lists(machine, lists, state):
    """Run a parsed line's lists and answer the line's own record."""
    rows = _lists_of(lists)
    shell = _state_of(state)
    leaving = shell["exit"]
    if leaving is not None:
        return _record((), leaving, True, 0)
    errexit = shell["flags"]["errexit"]
    statuses = ()
    skipped = 0
    live = rules.EXIT_OK
    for index, item in enumerate(rows):
        pipelines, connector = item
        if connector == "&&" and live != rules.EXIT_OK:
            skipped += _commands_in(pipelines)
            continue
        if connector == "||" and live == rules.EXIT_OK:
            skipped += _commands_in(pipelines)
            continue
        following = rows[index + 1][1] if index + 1 < len(rows) else None
        for position, pipeline in enumerate(pipelines):
            last = position + 1 == len(pipelines)
            kind = _kind_of(pipeline, following if last else "&&")
            if _background(pipeline):
                live, made = _launch(machine, shell, pipeline)
            else:
                live, made = _execute(machine, shell, pipeline, kind)
            statuses = statuses + made
            if shell["exit"] is not None:
                return _record(statuses, shell["exit"], True, skipped)
            if errexit and live != rules.EXIT_OK and not exempt(kind):
                return _record(statuses, live, True, skipped)
    return _record(statuses, live, False, skipped)


def exempt(kind):
    """Whether a status of `kind` is one `errexit` may not stop on."""
    if not isinstance(kind, str) or kind not in STATUS_KINDS:
        raise MachineError("not a status kind: %r" % (kind,))
    return kind in rules.ERREXIT_EXEMPTIONS


def condition_of(machine, condition):
    """Run a condition and answer what it answered, with its kind recorded."""
    kind, pipelines = _condition_of(condition)
    shell = _blank_state()
    statuses = ()
    status = rules.EXIT_OK
    for position, pipeline in enumerate(pipelines):
        last = position + 1 == len(pipelines)
        status, made = _execute(machine, shell, pipeline,
                                kind if last else "pipeline-but-last")
        statuses = statuses + made
    return _record(statuses, status, False, 0)


# --- the line's rule ------------------------------------------------------

def _kind_of(pipeline, connector):
    """The kind a pipeline's status is recorded under: `!` first, then position."""
    words = pipeline[0]["words"]
    if words and words[0] == _NEGATION:
        return "negated"
    if connector in ("&&", "||"):
        return "and-or-left"
    return "plain"


def _execute(machine, shell, pipeline, kind):
    """Run one foreground pipeline; answer (status, rows).

    The rows are what the pipeline answered: a `!`'s negation is the pipeline's
    own answer, so the last command's row — the one the kind belongs to —
    carries the negated status, and any earlier command of the pipeline keeps
    the status it itself answered (§4.8: the kind rides the pipeline's answer).
    """
    runnable = _without_negation(pipeline)
    negated = _negated(pipeline)
    if len(runnable) == 1:
        made = _in_shell(machine, shell, runnable[0], kind)
        if made is not None:
            status, rows = made
            answer = _negate(status, pipeline)
            return answer, (_row(answer, kind, _text_of(runnable[0])),)
    plan = stage_03.plan(machine, runnable, shell["variables"])
    run = stage_04.run_pipeline(machine, plan)
    waits = tuple(run["waited"])
    rows = ()
    for offset, command in enumerate(runnable):
        answer = waits[offset] if offset < len(waits) else run["status"]
        if offset + 1 == len(runnable):
            answer = _negate(answer, pipeline) if negated else answer
        rows = rows + (_row(answer, "pipeline-but-last" if offset + 1 < len(runnable)
                            else kind, _text_of(command)),)
    return _negate(run["status"], pipeline), rows


def _in_shell(machine, shell, command, kind):
    """Run a sole simple command in this process, or answer None to fork it.

    A builtin whose owner is another stage is routed by its first word (§4.8's
    rule, so a `wait` after an `&&` is the same `wait`); a stage 7 builtin runs
    where §4.7 says it must; a command that is nothing but an assignment sets a
    shell variable and is never exported. Everything else — a program, a command
    with redirections, a pipeline of more than one command — is answered None and
    goes to the plan.
    """
    if command["redirects"]:
        return None
    words = _expanded(machine, shell, command)
    if words is None:
        return rules.EXIT_FAILURE, (_row(rules.EXIT_FAILURE, kind,
                                         _text_of(command)),)
    assignment = command["assignment"]
    # §7 row 10: the word is kept in `words` as written, so `bare` is decided
    # from the line's own word and not from what §4.2 expanded it to — an
    # `X=$Y` on a line of its own is nothing but an assignment, whatever the
    # expansion put in the word.
    bare = not words or (assignment is not None
                         and command["words"] == (assignment,))
    if bare:
        if assignment is None:
            return None
        status = _assign(machine, shell, assignment)
        return status, (_row(status, kind, _text_of(command)),)
    if words[0] not in _ROUTED and not stage_07.is_builtin(words[0]):
        return None
    if command["assignment"] is not None:
        status = _assign(machine, shell, command["assignment"])
        if status != rules.EXIT_OK:
            return status, (_row(status, kind, _text_of(command)),)
    status = _owned(machine, shell, words[0], words[1:])
    return status, (_row(status, kind, _text_of(command)),)


def _owned(machine, shell, name, argv):
    """Call the stage that owns a builtin stage 7 refuses; answer its status."""
    if name not in _ROUTED:
        return stage_07.run_builtin(machine, name, tuple(argv), shell)["status"]
    if name == "wait":
        return stage_05.wait_for(machine, shell["jobs"],
                                 argv[0] if argv else None)["status"]
    if not argv:
        return rules.EXIT_BAD_USAGE
    if name == "kill":
        return stage_06.run_kill(machine, tuple(argv), shell["jobs"])["status"]
    action = argv[0]
    for spoken in argv[1:]:
        shell["traps"] = shell["traps"] + (stage_06.trap(machine, spoken,
                                                         action),)
    return rules.EXIT_OK


def _launch(machine, shell, pipeline):
    """Start a `&` list as a job without waiting; answer (status, rows)."""
    plan = stage_03.plan(machine, pipeline, shell["variables"])
    if plan["error"] is not None:
        status = _status_of(plan["error"])
        return status, _rows_for(pipeline, status, "plain")
    pid = stage_05.background(machine, plan)
    shell["jobs"] = shell["jobs"] + (_job_row(shell, pid, pipeline),)
    return rules.EXIT_OK, _rows_for(pipeline, rules.EXIT_OK, "plain")


# --- the rows, and the numbers in them ------------------------------------

def _record(statuses, status, stopped, skipped):
    """The line's own record, in `LISTS_KEYS` order."""
    return {"statuses": tuple(statuses), "status": status, "stopped": stopped,
            "skipped": skipped, "error": None}


def _row(status, kind, command):
    """One command's status, its kind and the text the shell was given."""
    return {"status": status, "kind": kind, "command": command}


def _rows_for(pipeline, status, kind):
    """A row per command of a pipeline that never ran: the pipeline's status."""
    rows = ()
    for offset, command in enumerate(pipeline):
        rows = rows + (_row(status, "pipeline-but-last"
                            if offset + 1 < len(pipeline) else kind,
                            _text_of(command)),)
    return rows


def _text_of(command):
    """A command as the line wrote it: its words, joined."""
    return " ".join(command["words"])


def _pipeline_text(pipeline):
    """A pipeline as the line wrote it."""
    return " | ".join(_text_of(command) for command in pipeline)


def _status_of(error):
    """The status a plan's own error is a shell's status for."""
    if isinstance(error, str):
        kind = error
    elif isinstance(error, dict):
        kind = error.get("kind")
    else:
        kind = None
    if kind == "unknown-program":
        return rules.EXIT_NOT_FOUND
    return rules.EXIT_FAILURE


def _commands_in(pipelines):
    """How many commands a list holds, which is what a short-circuit skipped."""
    total = 0
    for pipeline in pipelines:
        total += len(pipeline)
    return total


def _negated(pipeline):
    """Whether the pipeline was written with `!` in front of it."""
    words = pipeline[0]["words"]
    return bool(words) and words[0] == _NEGATION


def _without_negation(pipeline):
    """The pipeline with a leading `!` taken off, ready to be planned."""
    first = pipeline[0]
    if not _negated(pipeline):
        return pipeline
    head = {"words": tuple(first["words"][1:]),
            "redirects": tuple(first["redirects"]),
            "assignment": first["assignment"],
            "background": first["background"]}
    return (head,) + tuple(pipeline[1:])


def _negate(status, pipeline):
    """`0` and `rules.EXIT_FAILURE` the other way round under a `!`."""
    if not _negated(pipeline):
        return status
    if status == rules.EXIT_OK:
        return rules.EXIT_FAILURE
    return rules.EXIT_OK


def _background(pipeline):
    """Whether the list this pipeline belongs to was ended by `&`."""
    return bool(pipeline[-1]["background"])


def _job_row(shell, pid, pipeline):
    """The row the shell keeps for a job it has just started."""
    number = 1
    for row in shell["jobs"]:
        if row["job"] >= number:
            number = row["job"] + 1
    return {"job": number, "pid": pid, "state": "running", "status": None,
            "command": _pipeline_text(pipeline)}


# --- the commands that do not fork ----------------------------------------

def _expanded(machine, shell, command):
    """A command's words after §4.2, or None when an expansion failed."""
    words = ()
    for word in command["words"]:
        answer = stage_02.expand(machine, word, shell)
        if answer["error"] is not None:
            return None
        words = words + tuple(answer["words"])
    return words


def _substituted(machine, text, variables):
    """§4.2's parameter step on an assignment's value, once; None if it refused."""
    answer = stage_02.substitute(machine, text, variables)
    if isinstance(answer, str):
        return answer
    if not isinstance(answer, dict):
        return None
    if answer.get("error") is not None:
        return None
    if answer.get("text") is not None:
        return answer["text"]
    return "".join(answer.get("words", ()))


def _assign(machine, shell, text):
    """Set a shell variable from `NAME=value`: set, and never exported.

    The status is the value's: an assignment whose value cannot be expanded under
    `nounset` — or a command that is not an assignment at all — answers
    `rules.EXIT_FAILURE` and leaves the table alone.
    """
    name, separator, value = text.partition(rules.ASSIGNMENT)
    if not separator:
        return rules.EXIT_FAILURE
    substituted = _substituted(machine, value, shell)
    if substituted is None:
        return rules.EXIT_FAILURE
    shell["variables"][name] = substituted
    return rules.EXIT_OK


def _blank_state():
    """A shell of its own, for a condition that must not move the caller's."""
    return {"variables": {}, "exported": (), "traps": (), "jobs": (),
            "flags": {"errexit": False, "nounset": False}, "cwd": None,
            "exit": None, "args": (), "stdin": b""}


# --- the shapes a caller can get wrong ------------------------------------

def _lists_of(lists):
    """The parsed line, checked: a tuple of `(pipelines, connector)` pairs."""
    if not isinstance(lists, (tuple, list)):
        raise MachineError("the line's lists are not a tuple: %r" % (lists,))
    rows = []
    for item in lists:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise MachineError("a list is not (pipelines, connector): %r" % (item,))
        pipelines, connector = item
        if connector is not None and connector not in _CONNECTORS:
            raise MachineError("not a connector: %r" % (connector,))
        rows.append((_pipelines_of(pipelines), connector))
    return tuple(rows)


def _pipelines_of(pipelines):
    """A list's pipelines, or a bare pipeline read as a list of one."""
    if not isinstance(pipelines, (tuple, list)) or not pipelines:
        raise MachineError("a list has no pipelines: %r" % (pipelines,))
    if isinstance(pipelines[0], dict):
        return (_pipeline_of(pipelines),)
    return tuple(_pipeline_of(pipeline) for pipeline in pipelines)


def _pipeline_of(pipeline):
    """A pipeline's commands, checked."""
    if not isinstance(pipeline, (tuple, list)) or not pipeline:
        raise MachineError("a pipeline has no commands: %r" % (pipeline,))
    return tuple(_command(command) for command in pipeline)


def _command(command):
    """One `COMMAND_KEYS` record, checked and copied."""
    if not isinstance(command, dict):
        raise MachineError("not a command: %r" % (command,))
    words = command.get("words")
    if not isinstance(words, (tuple, list)):
        raise MachineError("a command has no words: %r" % (command,))
    for word in words:
        if not isinstance(word, str):
            raise MachineError("not a word: %r" % (word,))
    assignment = command.get("assignment")
    if assignment is not None and not isinstance(assignment, str):
        raise MachineError("not an assignment: %r" % (assignment,))
    redirects = command.get("redirects") or ()
    if not isinstance(redirects, (tuple, list)):
        raise MachineError("not a redirection set: %r" % (redirects,))
    return {"words": tuple(words), "redirects": tuple(redirects),
            "assignment": assignment,
            "background": bool(command.get("background"))}


def _state_of(state):
    """The shell's own record, checked, and handed back to be mutated in place."""
    if not isinstance(state, dict):
        raise MachineError("the shell's state is not a record: %r" % (state,))
    for key in _STATE_KEYS:
        if key not in state:
            raise MachineError("the shell's state has no %r: %r" % (key, state))
    for key in ("variables", "flags"):
        if not isinstance(state[key], dict):
            raise MachineError("state[%r] is not a record: %r" % (key, state[key]))
    for key in ("exported", "jobs"):
        if not isinstance(state[key], (tuple, list)):
            raise MachineError("state[%r] is not a table: %r" % (key, state[key]))
    if "errexit" not in state["flags"]:
        raise MachineError("the shell's flags have no 'errexit': %r"
                           % (state["flags"],))
    leaving = state["exit"]
    if leaving is not None and not isinstance(leaving, int):
        raise MachineError("state['exit'] is not a status: %r" % (leaving,))
    return state


def _condition_of(condition):
    """The condition's kind and the pipelines to run, from either shape."""
    if isinstance(condition, dict):
        kind = condition.get("kind")
        if kind not in _CONDITION_KINDS:
            raise MachineError("not a condition kind: %r" % (kind,))
        return kind, _pipelines_of(condition.get("pipelines"))
    return "condition", _pipelines_of(condition)
