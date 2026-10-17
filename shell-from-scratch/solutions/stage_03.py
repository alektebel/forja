"""Shell From Scratch — stage 3: The pipeline, the descriptor table and what a pipe costs.

A pipeline of *N* commands is *N* children and *N - 1* pipes, and every one of those
descriptors is decided before the first child exists: the words of each command are
expanded (§4.2), the pipes are made, and each command's redirections are walked left
to right over the table the pipes left behind. The order is the whole point of the
stage — `echo x >f 2>&1` sends both bytes to the file while `echo x 2>&1 >f` sends
the error wherever fd 1 pointed *before* the redirect — so the plan resolves a
duplication eagerly and the table a stage-4 spawn reads is already the table the
child gets.

Nothing here runs a command, and nothing here writes the machine except through the
calls this stage's own surface is defined to make: `machine.pipe()` once per gap and
`machine.store` once per here-document. Everything else is `machine.exists`,
`machine.is_dir` and the world's own program data, so a redirection that cannot be
made is a record with empty `commands`, `pipes` and `redirects` and a cost of zero
— it has asked for no pipe, no file and no child.
"""

import programs
import stage_02
from machine import SCALE
from machine import MachineError

PLAN_KEYS = ("commands", "pipes", "redirects", "steps", "error")

PLAN_ERRORS = ("bad-fd", "not-a-file", "ambiguous-redirect", "unknown-program",
               "empty-pipeline")

#: The three descriptors every command is born with, in the order a shell prints them.
_STANDARD = (0, 1, 2)

#: What the shell's own terminal is called in a descriptor table: the machine knows a
#: file, a pipe and the terminal, and only the first two have a target of their own.
_TERMINAL = "terminal"

#: Every redirection this stage knows, longest first — `2>&1` and `2>` are operators of
#: their own (§4.1), so a record's kind is one of these and never two of them.
_KINDS = (">", ">>", "<", "<<", "2>", "2>&1")

#: The kinds that read a file: every other kind either writes one or copies a
#: descriptor, and `<<` is the shell's own.
_READING = ("<",)

#: The programs whose standard output is empty whatever they are handed: every other
#: program either writes a size the plan can compute from its argv or carries what it
#: read, which is the split `bytes` is about.
_SILENT = ("false", "tick")


def _error(kind, target, detail):
    """The plan's refusal: the kind, the offender and a sentence naming what was expected."""
    return {"kind": kind, "target": target, "detail": detail}


def _empty(error):
    """What a refused plan answers: no table, no pipe, no record, and no cost."""
    return {"commands": (), "pipes": (), "redirects": (), "steps": 0, "error": error}


def _commands_of(pipeline):
    """The pipeline's commands in order, or the refusal naming what is not one."""
    if isinstance(pipeline, (str, bytes)) or not isinstance(pipeline, (list, tuple)):
        raise MachineError(
            "stage 3: %r is not a pipeline of command records" % (pipeline,))
    for index, command in enumerate(pipeline):
        if not isinstance(command, dict):
            raise MachineError("stage 3: command %d is %r, not a command record"
                               % (index, command))
    return tuple(pipeline)


def _words_of(command, index):
    """The words of one command, as written, or the refusal naming the wrong one."""
    words = command.get("words", ())
    if isinstance(words, (str, bytes)) or not isinstance(words, (list, tuple)):
        raise MachineError("stage 3: command %d carries %r for its words, not a "
                           "sequence of them" % (index, words))
    for word in words:
        if not isinstance(word, str):
            raise MachineError("stage 3: command %d carries the word %r, which is "
                               "not a string" % (index, word))
    return tuple(words)


def _redirects_of(command, index):
    """The redirection records of one command, or the refusal naming the wrong one."""
    redirects = command.get("redirects", ())
    if isinstance(redirects, (str, bytes)) or not isinstance(redirects, (list, tuple)):
        raise MachineError("stage 3: command %d carries %r for its redirects, not a "
                           "sequence of records" % (index, redirects))
    for redirect in redirects:
        if not isinstance(redirect, dict):
            raise MachineError("stage 3: command %d carries the redirection %r, which "
                               "is not a record" % (index, redirect))
        if redirect.get("kind") not in _KINDS:
            raise MachineError("stage 3: command %d carries %r, which is not a "
                               "redirection this shell knows"
                               % (index, redirect.get("kind")))
    return tuple(redirects)


def _expanded(machine, words, variables):
    """Every word's expansion in order: one word may become several, or none at all.

    The expansion is §4.2's, called once per word as written and never again on its
    own result, and a word whose expansion is an error contributes no word — which is
    how a command whose words all expand to nothing reaches `empty-pipeline`.
    """
    answer = []
    for word in words:
        record = stage_02.expand(machine, word, variables)
        if record["error"] is None:
            answer.extend(record["words"])
    return tuple(answer)


def _fd_number(value):
    """A descriptor number, or None when it is not a small non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value >= SCALE["fds"]:
        return None
    return value


def _fd_of(record, kind):
    """The number a redirection names, or the number its kind implies."""
    if kind in ("2>", "2>&1"):
        return 2
    number = record.get("fd")
    if number is None:
        return 0 if kind in _READING else 1
    return number


def _one_word(machine, record, variables):
    """A redirection's target expanded to exactly one word, or the refusal saying why.

    The answer is `(word, None)` or `(None, error)`: a target that expands to no word
    (an unset variable, §4.2) or to several (a split, §4.2) names no one file, and
    that is `ambiguous-redirect` and not a guess.
    """
    text = record.get("target")
    if not isinstance(text, str):
        raise MachineError("stage 3: the redirection's target %r is not a string"
                           % (text,))
    record_expanded = stage_02.expand(machine, text, variables)
    words = record_expanded["words"] if record_expanded["error"] is None else ()
    if len(words) != 1:
        return None, _error(
            "ambiguous-redirect", text,
            "stage 3: the redirection's target %r expands to %d words, and a "
            "redirection names exactly one" % (text, len(words)))
    return words[0], None


def _applied_table(machine, command, variables, index, ends, store):
    """One command's descriptor table: the standard numbers, the pipes, then the redirections.

    `ends` is `(read_fd, write_fd)` when the command sits in a pipeline and `None`
    when it stands alone; the pipeline is installed *before* the command's own
    redirections are walked left to right, which is the order a shell must use and
    the reason `2>&1` copies the pipe in one case and the terminal in the other.
    `store` is false in the pure pass that validates the plan and true in the pass
    that has already spent its pipes, so a plan that cannot be made writes nothing.

    The answer is `(table, None)` — the table's `fds` and its applied `redirects` — or
    `(None, error)`; a caller's shape mistake raises `machine.MachineError`.
    """
    redirects = _redirects_of(command, index)
    fds = dict((number, {"kind": _TERMINAL, "target": _TERMINAL, "append": False})
               for number in _STANDARD)
    if ends is not None:
        read_fd, write_fd = ends
        if read_fd is not None:
            fds[0] = {"kind": "pipe", "target": read_fd, "append": False}
        if write_fd is not None:
            fds[1] = {"kind": "pipe", "target": write_fd, "append": False}
    applied = []
    for order, record in enumerate(redirects):
        kind = record["kind"]
        number = _fd_number(_fd_of(record, kind))
        if number is None:
            return None, _error(
                "bad-fd", _fd_of(record, kind),
                "stage 3: %r is not a descriptor number this machine holds, which is "
                "a small non-negative int" % (_fd_of(record, kind),))
        if kind == "2>&1":
            fds[2] = dict(fds[1])
            applied.append({"kind": kind, "fd": 2, "target": 1, "append": False})
            continue
        if kind == "<<":
            body = record.get("target")
            if not isinstance(body, str):
                raise MachineError("stage 3: the here-document's body %r is not a "
                                   "string" % (body,))
            path = "/tmp/heredoc-%d-%d" % (index, order)
            if store:
                machine.store(path, body.encode())
            fds[number] = {"kind": "file", "target": path, "append": False}
            applied.append({"kind": kind, "fd": number, "target": path,
                            "append": False})
            continue
        target, refusal = _one_word(machine, record, variables)
        if refusal is not None:
            return None, refusal
        if not target:
            return None, _error("not-a-file", target,
                                "stage 3: a redirection whose target expands to "
                                "nothing names no file to open")
        there = machine.exists(target)
        if kind in _READING and not there:
            return None, _error("not-a-file", target,
                                "stage 3: %r cannot be read, because the machine "
                                "holds no such file" % (target,))
        if there and machine.is_dir(target):
            return None, _error("not-a-file", target,
                                "stage 3: %r cannot be opened as a file, because it "
                                "is a directory" % (target,))
        append = kind == ">>"
        fds[number] = {"kind": "file", "target": target, "append": append}
        applied.append({"kind": kind, "fd": number, "target": target,
                        "append": append})
    return {"fds": fds, "redirects": tuple(applied)}, None


def _carried(machine, name, argv, incoming):
    """The bytes the machine will carry out of a command, as the plan can know them.

    A writer's own output is a function of its argv (`echo`, `pwd`, `env`) or of
    nothing at all (`false`, `tick`), so the plan knows it exactly; a program that
    transforms its input (`cat`, `grep`, `head`, `sort`, `wc`) carries at most the
    bytes it read, and the shell's own standard input holds nothing the plan has put
    there — so a reader at the head of a pipeline carries nothing.
    """
    if name == "echo":
        return len(" ".join(argv[1:])) + 1
    if name == "pwd":
        return len(machine.cwd()) + 1
    if name == "env":
        return sum(len(line) + 1 for line in machine.env())
    if name in _SILENT:
        return 0
    return incoming


def plan(machine, pipeline, variables):
    """The descriptor table, the pipes and the cost of one pipeline — before it runs.

    `pipeline` is a tuple of `COMMAND_KEYS` records in command order (a parse's own
    pipeline, §4.1) and `variables` is the table §4.2 expands against. The answer is
    a `PLAN_KEYS` record: one row per command (`argv`, `program`, `fds`, `redirects`),
    `N - 1` pipe rows, every redirection flattened in the order it was applied, the
    pipeline's machine steps and an error or `None`.

    A command's `assignment` is §4.7's business and not this stage's, but a leading
    word that *is* that assignment is not part of the argv a child execs: the plan
    drops it, so `X=1 env` plans `env`. The variable itself is the shell's table and
    never reaches this record, and a command whose words hold nothing but the
    assignment is `empty-pipeline` here because it is not a pipeline command at all.

    The table is built in two passes. The first is pure: it expands every word, walks
    every redirection left to right over the standard numbers, and answers the first
    refusal it meets — `empty-pipeline`, `unknown-program`, `bad-fd`,
    `ambiguous-redirect` or `not-a-file` — with no pipe made, no file written and no
    child spawned. The second has already validated everything: it asks
    `machine.pipe()` once per gap between commands, stores each here-document's body,
    and installs the pipe ends *before* each command's own redirections are walked,
    which is why `echo x 2>&1 >f | cat` sends its error to the pipe.
    """
    commands = _commands_of(pipeline)
    if not commands:
        return _empty(_error("empty-pipeline", None,
                             "stage 3: a pipeline of no commands has no program to "
                             "run"))
    rows = []
    for index, command in enumerate(commands):
        argv = _expanded(machine, _words_of(command, index), variables)
        while argv and isinstance(argv[0], str) and "=" in argv[0] \
                and argv[0].split("=", 1)[0].isidentifier():
            argv = argv[1:]
        if not argv:
            return _empty(_error("empty-pipeline", index,
                                 "stage 3: command %d expands to no words, so it "
                                 "names no program" % (index,)))
        program = argv[0]
        if program not in programs.PROGRAM_NAMES:
            return _empty(_error("unknown-program", program,
                                 "stage 3: %r is not a program this machine holds"
                                 % (program,)))
        probe, refusal = _applied_table(machine, command, variables, index, None,
                                        False)
        if refusal is not None:
            return _empty(refusal)
        rows.append({"argv": argv, "program": program, "fds": probe["fds"],
                     "redirects": probe["redirects"]})
    steps = cost_of(machine, tuple(row["program"] for row in rows))
    pipes = []
    for _ in range(len(rows) - 1):
        read_fd, write_fd = machine.pipe()
        pipes.append({"read": read_fd, "write": write_fd, "bytes": 0})
    applied = []
    carried = 0
    for index, row in enumerate(rows):
        ends = None
        if len(pipes):
            ends = (pipes[index - 1]["read"] if index else None,
                    pipes[index]["write"] if index < len(pipes) else None)
        table, refusal = _applied_table(machine, commands[index], variables, index,
                                        ends, True)
        if refusal is not None:
            return _empty(refusal)
        row["fds"] = table["fds"]
        row["redirects"] = table["redirects"]
        for record in table["redirects"]:
            applied.append(dict(record, command=index))
        if index < len(pipes):
            carried = _carried(machine, row["program"], row["argv"], carried)
            pipes[index]["bytes"] = carried
    return {"commands": tuple(rows), "pipes": tuple(pipes),
            "redirects": tuple(applied), "steps": steps, "error": None}


def redirects_of(machine, command, variables):
    """One command's redirections, applied left to right, as a table and a record.

    The answer is `{"fds", "redirects", "error"}`: the descriptor table the
    redirections leave behind, starting from the three standard numbers on the
    terminal and with no pipeline in it, the records in the order they were applied
    (`{"kind", "fd", "target", "append"}`), and an error or `None` in the shape
    `plan` answers.

    `2>&1` copies fd 1's record into fd 2 as it stands at that point, so the order of
    two redirections is two different tables; `>` and `2>` write a file, `>>` appends
    to one, `<` reads one that must be there, and `<<` stores the here-document's body
    as a machine file the child can read. A redirection that cannot be made is an
    error and not an exception; a command that is not a record, a redirection that is
    not a record, a kind this shell does not know and a target that is not a string
    raise `machine.MachineError` naming the offender.
    """
    if not isinstance(command, dict):
        raise MachineError("stage 3: %r is not a command record" % (command,))
    table, refusal = _applied_table(machine, command, variables, 0, None, True)
    if refusal is not None:
        return {"fds": {}, "redirects": (), "error": refusal}
    return {"fds": table["fds"], "redirects": table["redirects"], "error": None}


def cost_of(machine, names):
    """The machine steps a pipeline of `names` will take, summed from the programs.

    Each name is asked of `programs.program` and its own `steps` added, so the answer
    is the machine's number and not an approximation, and an empty pipeline costs
    nothing. A name the machine holds no program for, a name that is not a string and
    a sequence that is neither a list nor a tuple of names raise `machine.MachineError`
    naming the offender. The machine's ledger does not move across this call: the cost
    is arithmetic over the world's own program data and not a door.
    """
    if isinstance(names, (str, bytes)) or not isinstance(names, (list, tuple)):
        raise MachineError("stage 3: %r is not a list of program names" % (names,))
    total = 0
    for name in names:
        if not isinstance(name, str):
            raise MachineError("stage 3: %r is not a string, and only a string names "
                               "a program" % (name,))
        if name not in programs.PROGRAM_NAMES:
            raise MachineError("stage 3: %r is not a program this machine holds"
                               % (name,))
        total += programs.program(name)["steps"]
    return total
