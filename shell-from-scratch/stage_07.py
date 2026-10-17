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


DESIGN DECISION — Why must a state builtin run in the shell's own process, and why is that
provable?
Because `cd` in a child changes a child's directory and nothing else — which
is why a first implementation so often "works" on the happy path and fails
the session later. The proof is the machine's own ledger: `stats()["spawn"]
does not move across the call. A check that read the source could be fooled;
a check that reads the ledger cannot.

DESIGN DECISION — Why does `run_builtin` mutate the caller's state in place instead of
answering a new state record?
Because the state *is* the shell's process memory: a record answered back
would be a value the caller has to reassign at every call site, and one
forgotten reassignment is a silent fork of the shell's own memory. Mutating
in place makes the builtin's effect visible through every alias the session
holds — the same reason §4.8's condition runs against a copy and a command
runs against the original.

DESIGN DECISION — Why are `trap`, `kill` and `wait` builtins of the shell but refused by this
stage?
Because ownership is the discipline: the tables those three read and write
belong to stage 6 (signals, traps) and stage 5 (jobs), and a stage that ran
them here would need those tables as parameters — which is how two stages end
up with two readings of one table. `is_builtin` still answers true, because
the *shell* owns the words; `run_builtin` refuses, because this stage does not
own the state.

DESIGN DECISION — Why is `exit` masked with `LIMITS["status"]` instead of refused?
Because `exit 256` is a user typing a number the shell accepts and wraps, not
a caller passing a wrong type: the machine's own `exit` refuses outside
0..255, and the shell's job is to translate the user's intent into what the
machine takes. `n & 255` is that translation — the same one a real shell
does — and the check pins both spellings (`exit 256` is 0, `exit -1` is 255).
    BUILTIN_KEYS    the four fields of one builtin answer, in order
    BUILTIN_STATES  the six kinds of state a builtin can write
    is_builtin(name) -> bool
    run_builtin(m, name, argv, state) -> BUILTIN_KEYS

TODO: implement `is_builtin`, `run_builtin` in this file.
"""

import rules
from machine import MachineError

BUILTIN_KEYS = ('name', 'status', 'state', 'output')

BUILTIN_STATES = ('unchanged', 'cwd', 'env', 'variables', 'options', 'exit')

_ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

_DIGITS = '0123456789'

_BLANKS = (b' ', b'\t')

_NOTHING = b''

_USAGE = ((':', ': [arguments]'), ('cd', 'cd [directory]'), ('exit', 'exit [status]'), ('export', 'export [NAME[=value]]...'), ('read', 'read NAME...'), ('set', 'set [-o option | +o option]'), ('shift', 'shift [n]'), ('unset', 'unset NAME...'))

_OPTIONS = (('errexit', 'e'), ('nounset', 'u'))

_ELSEWHERE = (('trap', 'stage 6'), ('kill', 'stage 6'), ('wait', 'stage 5'))


def _asked(name):
    """The name `name`, or the refusal naming what was handed over instead."""
    raise NotImplementedError("stage 7: implement _asked()")


def _arguments(argv):
    """The words `argv` holds, or the refusal naming the argument that is not one."""
    raise NotImplementedError("stage 7: implement _arguments()")


def _memory(state):
    """The shell's own record, which this stage writes into and never rebuilds.

    The record is the caller's: `SHELL_KEYS` names what a session carries in it, and
    every key of it is optional here, because a builtin is answerable with no session
    under it at all. A record that is not a mapping is the caller's mistake."""
    raise NotImplementedError("stage 7: implement _memory()")


def _variables(memory):
    """The shell's own variables, created when the record has none yet."""
    raise NotImplementedError("stage 7: implement _variables()")


def _lookup(memory, name):
    """The value the shell's own variables hold for `name`, or None."""
    raise NotImplementedError("stage 7: implement _lookup()")


def _exported(memory):
    """The names the shell has exported, as a sorted tuple."""
    raise NotImplementedError("stage 7: implement _exported()")


def _mark_exported(memory, name):
    """Record `name` as exported."""
    raise NotImplementedError("stage 7: implement _mark_exported()")


def _unmark_exported(memory, name):
    """Forget that `name` was ever exported."""
    raise NotImplementedError("stage 7: implement _unmark_exported()")


def _flags(memory):
    """The shell's own flags, created when the record has none yet."""
    raise NotImplementedError("stage 7: implement _flags()")


def _flag_of(memory, name):
    """True when the shell's own flags say `name` is on."""
    raise NotImplementedError("stage 7: implement _flag_of()")


def _args(memory):
    """The shell's positional parameters, as a tuple."""
    raise NotImplementedError("stage 7: implement _args()")


def _stdin(memory):
    """The bytes the shell has not yet read, or the refusal naming what they are not.

    The machine's own `read` is a process's descriptor read and the shell's own
    process has no pid to hand it, so the shell's input is the caller's: the bytes it
    has not yet handed over. Anything but bytes is a caller's mistake."""
    raise NotImplementedError("stage 7: implement _stdin()")


def _answer(name, status, kind, output):
    """The `BUILTIN_KEYS` row one call answers, in the contract's field order."""
    raise NotImplementedError("stage 7: implement _answer()")


def _usage(name):
    """The usage line of `name` as bytes, or nothing at all for a word with none."""
    raise NotImplementedError("stage 7: implement _usage()")


def _bad_usage(name):
    """The answer a builtin gives when it was called wrongly: its usage, nothing written."""
    raise NotImplementedError("stage 7: implement _bad_usage()")


def _is_name(word):
    """True for a word a shell will take as a variable's name.

    A letter or `_` first, then letters, digits or `_`, and no longer than
    `rules.LIMITS["var_name"]` — the policy's own limit, so a name over it is not a
    name rather than a name to be truncated."""
    raise NotImplementedError("stage 7: implement _is_name()")


def _assignment(word):
    """The `(name, value)` a `NAME=value` word carries, or None when it carries none.

    A word with no `=`, or an `=` whose left side is not a name a shell would take, is
    not an assignment at all: `1x=2` is a word a shell cannot find, and so is `=2`."""
    raise NotImplementedError("stage 7: implement _assignment()")


def _unsigned(word):
    """The count a bare run of digits spells, or None — `shift`'s own argument."""
    raise NotImplementedError("stage 7: implement _unsigned()")


def _signed(word):
    """The integer a run of digits spells, with or without a leading `-`, or None."""
    raise NotImplementedError("stage 7: implement _signed()")


def _absolute(machine, word):
    """`word` as the machine's own absolute spelling of a directory.

    §2.1 makes the machine's paths absolute strings and the machine the only
    filesystem there is, so the shell's own arithmetic is what turns a bare name or a
    `..` into one: the word is joined to `machine.cwd()` and its `.` and `..` are
    resolved against it, with a `..` at the root staying at the root and an empty word
    naming the working directory itself."""
    raise NotImplementedError("stage 7: implement _absolute()")


def _owned(word, letter):
    """The option `word` names — by its `rules` name, or by `set`'s own letter — or None."""
    raise NotImplementedError("stage 7: implement _owned()")


def _option_of(words):
    """The option a `set` call names, as `(name, on)`, and `(None, False)` for a bare `-o`.

    `None` means the words are not an option this shell owns at all — an unknown
    option, an unknown letter, or a word after a letter flag — which is the caller's
    `EXIT_BAD_USAGE`. A bare `-o` or `+o` asks for the options instead of setting one."""
    raise NotImplementedError("stage 7: implement _option_of()")


def _first_line(raw):
    """The first line of `raw` and the bytes after it, the newline consumed with the line."""
    raise NotImplementedError("stage 7: implement _first_line()")


def _fields(line):
    """The `(offset, word)` of every whitespace-separated field of a line of bytes."""
    raise NotImplementedError("stage 7: implement _fields()")


def _environment(machine):
    """The machine's own environment as the `NAME=value` lines `export` writes."""
    raise NotImplementedError("stage 7: implement _environment()")


def _variables_as_bytes(memory):
    """The shell's own variables as `NAME=value` lines, sorted by name."""
    raise NotImplementedError("stage 7: implement _variables_as_bytes()")


def _flags_as_bytes(memory):
    """The flags this shell owns as `NAME on`/`NAME off` lines, in `rules` name order."""
    raise NotImplementedError("stage 7: implement _flags_as_bytes()")


def _colon():
    """`:` — the builtin that answers 0 with its arguments ignored and nothing written."""
    raise NotImplementedError("stage 7: implement _colon()")


def _cd(machine, words, memory):
    """`cd` — the shell's own working directory, changed in this process or not at all.

    With no argument it goes to the shell's own `HOME` and then to the machine's, and
    a word that does not name a directory is `EXIT_FAILURE` with the working directory
    left exactly where it was: `machine.chdir` is asked only once a directory is known
    to be one, so a `cd` to a file never half-happens."""
    raise NotImplementedError("stage 7: implement _cd()")


def _exit(words, memory):
    """`exit` — the status the shell was told to leave with, masked into a status.

    `machine.exit` takes a process's status in `0..255` and refuses anything else, and
    the shell's own process is not in the machine's table, so `exit` is the shell's own
    intent: `n & rules.LIMITS["status"]`, which is why `exit 256` leaves with zero and
    `exit -1` with 255. With no argument the status is `rules.EXIT_OK` — the shell's
    own last status is the caller's, and the caller says it by passing one."""
    raise NotImplementedError("stage 7: implement _exit()")


def _export(machine, words, memory):
    """`export` — a shell variable that is also in the machine's own environment.

    `export NAME=value` both sets the variable and exports it; `export NAME` exports
    one the shell already holds, and marks one it does not. With no argument the
    machine's own environment is written to the shell's stdout. A word that is not a
    name is `EXIT_BAD_USAGE`, and nothing at all is exported when one word is wrong:
    the call is checked before the first variable is set."""
    raise NotImplementedError("stage 7: implement _export()")


def _unset(machine, words, memory):
    """`unset` — the shell's variable and the machine's environment, both without it.

    Removing a name the shell never set is not a failure: there is nothing to remove.
    The machine is asked only for a name it actually holds, so a word that never
    reached the environment costs the machine nothing at all."""
    raise NotImplementedError("stage 7: implement _unset()")


def _set(words, memory):
    """`set` — the shell's own flags, and its own variables when asked for them.

    `set` with no words writes the shell's variables as `NAME=value` lines; `set -o`
    writes the flags it owns as `NAME on`/`NAME off` lines; `set -o errexit`,
    `set +o errexit`, `set -e` and `set +e` are the four spellings of the one flag.
    An option this shell does not own, an unknown letter and three words are all
    `EXIT_BAD_USAGE`, and a flag is written only once the words are known to be one:
    a refused call changes no flag."""
    raise NotImplementedError("stage 7: implement _set()")


def _shift(words, memory):
    """`shift` — the shell's positional parameters, moved down or refused.

    One word by default, and a count past the end is `EXIT_FAILURE` with the
    parameters left exactly where they were, which is the failure a shell reports and
    carries on from rather than a crash. The count is a bare run of digits: `shift -1`
    and `shift 1 2` are `EXIT_BAD_USAGE`, because neither is a count."""
    raise NotImplementedError("stage 7: implement _shift()")


def _read(words, memory):
    """`read` — one line of the shell's own input, split into the names it was given.

    The names are filled in order and the *last* name is given the rest of the line
    verbatim, so the spacing inside it survives; a name past the line's last field is
    the empty word. The newline is consumed with the line and what follows is written
    back under the same key. An empty input is the end of input — `EXIT_FAILURE`, with
    the variables the shell already held left alone — and there is nothing to read
    without at least one name."""
    raise NotImplementedError("stage 7: implement _read()")


def _assign(word, pair, memory):
    """A bare `NAME=value` command word: a shell variable, and nothing exported.

    This is the other half of `export`: the word sets the shell's own variable and
    deliberately leaves the machine's environment alone, which is the difference
    between the two a check reads off `machine.getenv`."""
    raise NotImplementedError("stage 7: implement _assign()")


def is_builtin(name):
    """Whether `name` is one of the words this shell answers itself.

    True exactly for the words of `rules.BUILTINS` and false for every other word,
    including a program's name and the empty word — `trap`, `kill` and `wait`
    included, because the shell owns those three words even though this stage may not
    run them.
    `name` is a word: one that is not a string raises `machine.MachineError` naming it,
    because whether a word is a builtin is not a question a non-word can be asked."""
    raise NotImplementedError("stage 7: implement is_builtin()")


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
    `machine.MachineError` naming the offender."""
    raise NotImplementedError("stage 7: implement run_builtin()")
