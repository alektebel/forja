"""Shell From Scratch — stage 7: The builtins that must not fork.

A shell is a process, and a handful of the words it knows are commands of *that
process*: `cd` changes its working directory, `export` changes its environment,
`shift` moves its positional parameters, `set` changes its own flags, `read` consumes
its input, `exit` ends it, and `:` does nothing whatsoever. Every other word becomes a
child. This stage is that boundary, and it is the only stage whose answer is a status
*and* a change: a state builtin runs in the shell's own process, so the machine is
never asked for a process at all — `machine.stats()["spawn"]` does not move across a
single one of these calls, which is the fact the whole stage is built on.

Every call answers a `BUILTIN_KEYS` row: the word, the status, the *kind* of state
the call wrote, and the bytes it wrote to the shell's stdout. The kind names the
state the call owns — `"cwd"` for `cd`, `"env"` for `export` and `unset`,
`"variables"` for `shift`, `read` and a bare `NAME=value` word, `"options"` for
`set`, `"exit"` for `exit`, `"unchanged"` for `:` and for every call that wrote
nothing at all. The state the call wrote belongs to the caller's record, which this
stage mutates in place: `variables`, `exported`, `flags`, `cwd`, `exit` and `args`
are the shell's own memory, `machine.cwd()` and `machine.env()` are the machine's own
answer key for the two builtins that reach it, and `stdin` is the front of the shell's
own input, which is what `read` consumes and the only way `read` can answer at all.
"""

import rules
from machine import MachineError

BUILTIN_KEYS = ("name", "status", "state", "output")

BUILTIN_STATES = ("unchanged", "cwd", "env", "variables", "options", "exit")

#: The letters a variable's name is made of. Two strings rather than the `str`
#: methods, because `"é".isalpha()` is true and a shell's name is ASCII.
_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"

#: What separates the fields of a line: the two bytes a shell splits on.
_BLANKS = (b" ", b"\t")

#: The bytes a builtin answers when it wrote nothing at all to the shell's stdout.
_NOTHING = b""

#: The usage line of every builtin this stage answers, as a tuple of pairs so the
#: module holds no mutable state.
_USAGE = ((":", ": [arguments]"),
          ("cd", "cd [directory]"),
          ("exit", "exit [status]"),
          ("export", "export [NAME[=value]]..."),
          ("read", "read NAME..."),
          ("set", "set [-o option | +o option]"),
          ("shift", "shift [n]"),
          ("unset", "unset NAME..."))

#: The options this shell owns: their `rules` names and the single letter `set`
#: accepts for each, so `set -o errexit` and `set -e` are the one flag.
_OPTIONS = (("errexit", "e"), ("nounset", "u"))

#: The words `rules.BUILTINS` holds that this stage may not run, because the shell
#: owns them and another stage does: the signal stage's two, and the job table's one.
#: `is_builtin` answers true for all three all the same — whether a word is a builtin
#: and whether this stage may run it are two different questions.
_ELSEWHERE = (("trap", "stage 6"), ("kill", "stage 6"), ("wait", "stage 5"))


# --- the shapes a caller can get wrong -----------------------------------


def _asked(name):
    """The name `name`, or the refusal naming what was handed over instead."""
    if not isinstance(name, str):
        raise MachineError("stage 7: a builtin's name is a string, and %r is not"
                           % (name,))
    return name


def _arguments(argv):
    """The words `argv` holds, or the refusal naming the argument that is not one."""
    if isinstance(argv, str) or not isinstance(argv, (tuple, list)):
        raise MachineError("stage 7: a builtin's arguments are a tuple of words, and "
                           "%r is not" % (argv,))
    for word in argv:
        if not isinstance(word, str):
            raise MachineError("stage 7: a builtin's arguments are words, and %r is not "
                               "a word" % (word,))
    return tuple(argv)


def _memory(state):
    """The shell's own record, which this stage writes into and never rebuilds.

    The record is the caller's: `SHELL_KEYS` names what a session carries in it, and
    every key of it is optional here, because a builtin is answerable with no session
    under it at all. A record that is not a mapping is the caller's mistake.
    """
    if not isinstance(state, dict):
        raise MachineError("stage 7: the shell's state is a mapping, and %r is not"
                           % (state,))
    return state


def _variables(memory):
    """The shell's own variables, created when the record has none yet."""
    if not isinstance(memory.get("variables"), dict):
        memory["variables"] = {}
    return memory["variables"]


def _lookup(memory, name):
    """The value the shell's own variables hold for `name`, or None."""
    kept = memory.get("variables")
    if not isinstance(kept, dict):
        return None
    return kept.get(name)


def _exported(memory):
    """The names the shell has exported, as a sorted tuple."""
    return tuple(sorted(set(memory.get("exported") or ())))


def _mark_exported(memory, name):
    """Record `name` as exported."""
    memory["exported"] = tuple(sorted(set(_exported(memory)) | {name}))


def _unmark_exported(memory, name):
    """Forget that `name` was ever exported."""
    memory["exported"] = tuple(kept for kept in _exported(memory) if kept != name)


def _flags(memory):
    """The shell's own flags, created when the record has none yet."""
    if not isinstance(memory.get("flags"), dict):
        memory["flags"] = {}
    return memory["flags"]


def _flag_of(memory, name):
    """True when the shell's own flags say `name` is on."""
    kept = memory.get("flags")
    if not isinstance(kept, dict):
        return False
    return bool(kept.get(name))


def _args(memory):
    """The shell's positional parameters, as a tuple."""
    return tuple(memory.get("args") or ())


def _stdin(memory):
    """The bytes the shell has not yet read, or the refusal naming what they are not.

    The machine's own `read` is a process's descriptor read and the shell's own
    process has no pid to hand it, so the shell's input is the caller's: the bytes it
    has not yet handed over. Anything but bytes is a caller's mistake.
    """
    raw = memory.get("stdin", b"")
    if not isinstance(raw, bytes):
        raise MachineError("stage 7: the shell's own input is bytes, and %r is not"
                           % (raw,))
    return raw


# --- the answer, and the words a builtin's arguments are -----------------


def _answer(name, status, kind, output=_NOTHING):
    """The `BUILTIN_KEYS` row one call answers, in the contract's field order."""
    return {"name": name, "status": status, "state": kind, "output": output}


def _usage(name):
    """The usage line of `name` as bytes, or nothing at all for a word with none."""
    for word, line in _USAGE:
        if word == name:
            return ("usage: %s\n" % (line,)).encode("utf-8")
    return _NOTHING


def _bad_usage(name):
    """The answer a builtin gives when it was called wrongly: its usage, nothing written."""
    return _answer(name, rules.EXIT_BAD_USAGE, "unchanged", _usage(name))


def _is_name(word):
    """True for a word a shell will take as a variable's name.

    A letter or `_` first, then letters, digits or `_`, and no longer than
    `rules.LIMITS["var_name"]` — the policy's own limit, so a name over it is not a
    name rather than a name to be truncated.
    """
    if not word or len(word) > rules.LIMITS["var_name"]:
        return False
    if word[0] not in _ALPHA and word[0] != "_":
        return False
    for char in word[1:]:
        if char not in _ALPHA and char not in _DIGITS and char != "_":
            return False
    return True


def _assignment(word):
    """The `(name, value)` a `NAME=value` word carries, or None when it carries none.

    A word with no `=`, or an `=` whose left side is not a name a shell would take, is
    not an assignment at all: `1x=2` is a word a shell cannot find, and so is `=2`.
    """
    where = word.find("=")
    if where <= 0:
        return None
    head = word[:where]
    if not _is_name(head):
        return None
    return head, word[where + 1:]


def _unsigned(word):
    """The count a bare run of digits spells, or None — `shift`'s own argument."""
    if not word:
        return None
    for char in word:
        if char not in _DIGITS:
            return None
    return int(word)


def _signed(word):
    """The integer a run of digits spells, with or without a leading `-`, or None."""
    if word.startswith("-"):
        rest = _unsigned(word[1:])
        return None if rest is None else -rest
    return _unsigned(word)


def _absolute(machine, word):
    """`word` as the machine's own absolute spelling of a directory.

    §2.1 makes the machine's paths absolute strings and the machine the only
    filesystem there is, so the shell's own arithmetic is what turns a bare name or a
    `..` into one: the word is joined to `machine.cwd()` and its `.` and `..` are
    resolved against it, with a `..` at the root staying at the root and an empty word
    naming the working directory itself.
    """
    if word.startswith("/"):
        whole = word
    else:
        here = machine.cwd()
        whole = here.rstrip("/") + "/" + word
    parts = []
    for part in whole.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def _owned(word, letter):
    """The option `word` names — by its `rules` name, or by `set`'s own letter — or None."""
    for name, initial in _OPTIONS:
        if word == name or (letter and word == initial):
            return name
    return None


def _option_of(words):
    """The option a `set` call names, as `(name, on)`, and `(None, False)` for a bare `-o`.

    `None` means the words are not an option this shell owns at all — an unknown
    option, an unknown letter, or a word after a letter flag — which is the caller's
    `EXIT_BAD_USAGE`. A bare `-o` or `+o` asks for the options instead of setting one.
    """
    if not words or len(words) > 2:
        return None
    first = words[0]
    if first in ("-o", "+o"):
        if len(words) == 1:
            return (None, False)
        name = _owned(words[1], False)
        if name is None:
            return None
        return (name, first == "-o")
    if len(first) == 2 and first[0] in "-+":
        if len(words) == 2:
            return None
        name = _owned(first[1], True)
        if name is None:
            return None
        return (name, first[0] == "-")
    return None


def _first_line(raw):
    """The first line of `raw` and the bytes after it, the newline consumed with the line."""
    where = raw.find(b"\n")
    if where < 0:
        return raw, b""
    return raw[:where], raw[where + 1:]


def _fields(line):
    """The `(offset, word)` of every whitespace-separated field of a line of bytes."""
    fields = []
    place = 0
    while place < len(line):
        while place < len(line) and line[place:place + 1] in _BLANKS:
            place = place + 1
        if place >= len(line):
            break
        start = place
        while place < len(line) and line[place:place + 1] not in _BLANKS:
            place = place + 1
        fields.append((start, line[start:place]))
    return fields


def _environment(machine):
    """The machine's own environment as the `NAME=value` lines `export` writes."""
    return b"".join((line + "\n").encode("utf-8") for line in machine.env())


def _variables_as_bytes(memory):
    """The shell's own variables as `NAME=value` lines, sorted by name."""
    kept = memory.get("variables")
    if not isinstance(kept, dict):
        return _NOTHING
    return b"".join(("%s=%s\n" % (name, kept[name])).encode("utf-8")
                    for name in sorted(kept))


def _flags_as_bytes(memory):
    """The flags this shell owns as `NAME on`/`NAME off` lines, in `rules` name order."""
    return b"".join(("%s %s\n" % (name, "on" if _flag_of(memory, name) else "off"))
                    .encode("utf-8") for name, _initial in _OPTIONS)


# --- the builtins themselves, each in the shell's own process ------------


def _colon():
    """`:` — the builtin that answers 0 with its arguments ignored and nothing written."""
    return _answer(":", rules.EXIT_OK, "unchanged")


def _cd(machine, words, memory):
    """`cd` — the shell's own working directory, changed in this process or not at all.

    With no argument it goes to the shell's own `HOME` and then to the machine's, and
    a word that does not name a directory is `EXIT_FAILURE` with the working directory
    left exactly where it was: `machine.chdir` is asked only once a directory is known
    to be one, so a `cd` to a file never half-happens.
    """
    if len(words) > 1:
        return _bad_usage("cd")
    if words:
        where = words[0]
    else:
        where = _lookup(memory, "HOME")
        if where is None:
            where = machine.getenv("HOME")
    if not isinstance(where, str):
        return _answer("cd", rules.EXIT_FAILURE, "unchanged")
    place = _absolute(machine, where)
    if not machine.is_dir(place):
        return _answer("cd", rules.EXIT_FAILURE, "unchanged")
    machine.chdir(place)
    memory["cwd"] = place
    return _answer("cd", rules.EXIT_OK, "cwd")


def _exit(words, memory):
    """`exit` — the status the shell was told to leave with, masked into a status.

    `machine.exit` takes a process's status in `0..255` and refuses anything else, and
    the shell's own process is not in the machine's table, so `exit` is the shell's own
    intent: `n & rules.LIMITS["status"]`, which is why `exit 256` leaves with zero and
    `exit -1` with 255. With no argument the status is `rules.EXIT_OK` — the shell's
    own last status is the caller's, and the caller says it by passing one.
    """
    if len(words) > 1:
        return _bad_usage("exit")
    status = rules.EXIT_OK
    if words:
        status = _signed(words[0])
        if status is None:
            return _bad_usage("exit")
    memory["exit"] = status & rules.LIMITS["status"]
    return _answer("exit", memory["exit"], "exit")


def _export(machine, words, memory):
    """`export` — a shell variable that is also in the machine's own environment.

    `export NAME=value` both sets the variable and exports it; `export NAME` exports
    one the shell already holds, and marks one it does not. With no argument the
    machine's own environment is written to the shell's stdout. A word that is not a
    name is `EXIT_BAD_USAGE`, and nothing at all is exported when one word is wrong:
    the call is checked before the first variable is set.
    """
    if not words:
        return _answer("export", rules.EXIT_OK, "unchanged", _environment(machine))
    wanted = []
    for word in words:
        pair = _assignment(word)
        if pair is None:
            if not _is_name(word):
                return _bad_usage("export")
            pair = (word, None)
        wanted.append(pair)
    variables = _variables(memory)
    for name, value in wanted:
        if value is not None:
            variables[name] = value
        held = variables.get(name)
        if held is not None:
            machine.setenv(name, held)
        _mark_exported(memory, name)
    return _answer("export", rules.EXIT_OK, "env")


def _unset(machine, words, memory):
    """`unset` — the shell's variable and the machine's environment, both without it.

    Removing a name the shell never set is not a failure: there is nothing to remove.
    The machine is asked only for a name it actually holds, so a word that never
    reached the environment costs the machine nothing at all.
    """
    if not words:
        return _answer("unset", rules.EXIT_OK, "unchanged")
    for name in words:
        if not _is_name(name):
            return _bad_usage("unset")
    variables = _variables(memory)
    for name in words:
        variables.pop(name, None)
        _unmark_exported(memory, name)
        if machine.getenv(name) is not None:
            machine.unsetenv(name)
    return _answer("unset", rules.EXIT_OK, "env")


def _set(words, memory):
    """`set` — the shell's own flags, and its own variables when asked for them.

    `set` with no words writes the shell's variables as `NAME=value` lines; `set -o`
    writes the flags it owns as `NAME on`/`NAME off` lines; `set -o errexit`,
    `set +o errexit`, `set -e` and `set +e` are the four spellings of the one flag.
    An option this shell does not own, an unknown letter and three words are all
    `EXIT_BAD_USAGE`, and a flag is written only once the words are known to be one:
    a refused call changes no flag.
    """
    if not words:
        return _answer("set", rules.EXIT_OK, "unchanged", _variables_as_bytes(memory))
    option = _option_of(words)
    if option is None:
        return _bad_usage("set")
    name, on = option
    if name is None:
        return _answer("set", rules.EXIT_OK, "unchanged", _flags_as_bytes(memory))
    _flags(memory)[name] = on
    return _answer("set", rules.EXIT_OK, "options")


def _shift(words, memory):
    """`shift` — the shell's positional parameters, moved down or refused.

    One word by default, and a count past the end is `EXIT_FAILURE` with the
    parameters left exactly where they were, which is the failure a shell reports and
    carries on from rather than a crash. The count is a bare run of digits: `shift -1`
    and `shift 1 2` are `EXIT_BAD_USAGE`, because neither is a count.
    """
    if len(words) > 1:
        return _bad_usage("shift")
    count = 1
    if words:
        count = _unsigned(words[0])
        if count is None:
            return _bad_usage("shift")
    args = _args(memory)
    if count > len(args):
        return _answer("shift", rules.EXIT_FAILURE, "unchanged")
    memory["args"] = tuple(args[count:])
    return _answer("shift", rules.EXIT_OK, "variables")


def _read(words, memory):
    """`read` — one line of the shell's own input, split into the names it was given.

    The names are filled in order and the *last* name is given the rest of the line
    verbatim, so the spacing inside it survives; a name past the line's last field is
    the empty word. The newline is consumed with the line and what follows is written
    back under the same key. An empty input is the end of input — `EXIT_FAILURE`, with
    the variables the shell already held left alone — and there is nothing to read
    without at least one name.
    """
    if not words:
        return _bad_usage("read")
    for name in words:
        if not _is_name(name):
            return _bad_usage("read")
    raw = _stdin(memory)
    if not raw:
        return _answer("read", rules.EXIT_FAILURE, "unchanged")
    line, rest = _first_line(raw)
    fields = _fields(line)
    variables = _variables(memory)
    for place, name in enumerate(words):
        if place >= len(fields):
            variables[name] = ""
            continue
        field_at, field = fields[place]
        if place == len(words) - 1:
            field = line[field_at:]
        variables[name] = field.decode("utf-8", "replace")
    memory["stdin"] = rest
    return _answer("read", rules.EXIT_OK, "variables")


def _assign(word, pair, memory):
    """A bare `NAME=value` command word: a shell variable, and nothing exported.

    This is the other half of `export`: the word sets the shell's own variable and
    deliberately leaves the machine's environment alone, which is the difference
    between the two a check reads off `machine.getenv`.
    """
    name, value = pair
    _variables(memory)[name] = value
    return _answer(word, rules.EXIT_OK, "variables")


# --- the surface ---------------------------------------------------------


def is_builtin(name):
    """Whether `name` is one of the words this shell answers itself.

    True exactly for the words of `rules.BUILTINS` and false for every other word,
    including a program's name and the empty word — `trap`, `kill` and `wait`
    included, because the shell owns those three words even though this stage may not
    run them.
    `name` is a word: one that is not a string raises `machine.MachineError` naming it,
    because whether a word is a builtin is not a question a non-word can be asked.
    """
    return _asked(name) in rules.BUILTINS


def run_builtin(machine, name, argv, state):
    """Run one builtin in the shell's own process and answer the `BUILTIN_KEYS` row.

    `argv` is the tuple of words after the builtin's name; `state` is the shell's own
    record — `SHELL_KEYS`: `variables`, `exported`, `traps`, `jobs`, `flags`, `cwd`,
    `exit`, `args` and `stdin` — and this call writes into that mapping in place,
    because that mapping *is* the shell's process memory. `cd` sets `cwd` and calls
    `machine.chdir`; `export` and `unset` set `variables` and `exported` and call
    `machine.setenv`/`machine.unsetenv`; `set` sets `flags`; `shift` sets `args`;
    `read` sets `variables` and consumes the front of `stdin`; `exit` sets `exit` to
    `n & rules.LIMITS["status"]`; `:` writes nothing; and a bare `NAME=value` word sets
    a variable that is deliberately not exported.

    The answer's `state` is the kind of state the call wrote — one of `BUILTIN_STATES`
    — and its `output` the bytes the call wrote to the shell's stdout, which is the
    usage line for a call made wrongly. Nothing here spawns, forks or waits: a state
    builtin that ran in a child would change nothing, which is the whole law of this
    stage.

    `trap`, `kill` and `wait` are refused with `machine.MachineError` naming them and the
    stage that owns their table, because the shell's traps and its signals are stage
    6's and its job table is stage 5's — and `is_builtin` still answers true for all
    three. A word this stage can neither run as a builtin nor read as a
    `NAME=value` assignment is refused the same way. A shape that is a caller's
    mistake — a name that is not a string, an `argv` that is not a tuple of words, a
    `state` that is not a mapping, a `stdin` that is not bytes — raises
    `machine.MachineError` naming the offender.
    """
    name = _asked(name)
    for word, owner in _ELSEWHERE:
        if word == name:
            raise MachineError("stage 7: %r is a builtin of the shell and %s owns it, so "
                               "run_builtin refuses it" % (name, owner))
    words = _arguments(argv)
    memory = _memory(state)
    if name == ":":
        return _colon()
    if name == "cd":
        return _cd(machine, words, memory)
    if name == "exit":
        return _exit(words, memory)
    if name == "export":
        return _export(machine, words, memory)
    if name == "read":
        return _read(words, memory)
    if name == "set":
        return _set(words, memory)
    if name == "shift":
        return _shift(words, memory)
    if name == "unset":
        return _unset(machine, words, memory)
    pair = _assignment(name)
    if pair is not None:
        return _assign(name, pair, memory)
    raise MachineError("stage 7: %r is not a builtin of this shell and not a "
                       "NAME=value word" % (name,))
