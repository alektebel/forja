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


DESIGN DECISION — Why is the whole descriptor table built before anything runs?
Because a redirection that cannot be made must cost nothing: no pipe made, no
here-document stored, no child spawned, and the answer an error with empty
table and zero cost. A plan that built as it went would have already spent
pipes when it discovered the refusal — and then either leaked them or had to
unmake them. Two passes make the promise mechanical: the first validates
purely, the second spends.

DESIGN DECISION — Why do redirections apply left to right, and why is `cmd >f 2>&1` different
from `cmd 2>&1 >f`?
Because each redirection reads the table as it stands: `>f` points fd 1 at the
file, so the `2>&1` that follows copies the file into fd 2 — both go to `f`.
Swapped, `2>&1` copies the terminal into fd 2 *first*, and the `>f` that follows
moves only fd 1. The order is the meaning; a plan that applied them in any
other order would answer a question the user did not write.

DESIGN DECISION — Why does the plan know a pipeline's byte counts and step cost before running?
Because cost is arithmetic over the world's own data — `programs.program(name)
["steps"]` per command, and a writer's output a function of its argv — and a
number the plan can assert is a number a check can hold the run to. It is also
the difference between planning and guessing: `cost_of` asks the program table,
not the machine, so its ledger does not move — planning spends nothing.

DESIGN DECISION — Why does a leading assignment word leave the plan's argv?
Because `X=1 env` runs `env`, not `X=1 env`: the assignment is the shell's
variable table's business (§4.7), and the child's argv is what the child
execs. But the word is not hidden — the parse kept it in `words` — and a
command that is *nothing but* the assignment is `empty-pipeline` here,
because it is not a pipeline command at all.
    PLAN_KEYS      the five fields of a plan, in order
    PLAN_ERRORS    the five ways a pipeline refuses to be planned
    plan(m, pipeline, vars)            -> PLAN_KEYS, the whole table
    redirects_of(m, command, vars)     -> {"fds", "redirects", "error"}
    cost_of(m, names)                  -> int, the machine steps

TODO: implement `plan`, `redirects_of`, `cost_of` in this file.
"""

import programs
import stage_02
from machine import SCALE
from machine import MachineError

PLAN_KEYS = ('commands', 'pipes', 'redirects', 'steps', 'error')

PLAN_ERRORS = ('bad-fd', 'not-a-file', 'ambiguous-redirect', 'unknown-program', 'empty-pipeline')

_STANDARD = (0, 1, 2)

_TERMINAL = 'terminal'

_KINDS = ('>', '>>', '<', '<<', '2>', '2>&1')

_READING = ('<',)

_SILENT = ('false', 'tick')


def _error(kind, target, detail):
    """The plan's refusal: the kind, the offender and a sentence naming what was expected."""
    raise NotImplementedError("stage 3: implement _error()")


def _empty(error):
    """What a refused plan answers: no table, no pipe, no record, and no cost."""
    raise NotImplementedError("stage 3: implement _empty()")


def _commands_of(pipeline):
    """The pipeline's commands in order, or the refusal naming what is not one."""
    raise NotImplementedError("stage 3: implement _commands_of()")


def _words_of(command, index):
    """The words of one command, as written, or the refusal naming the wrong one."""
    raise NotImplementedError("stage 3: implement _words_of()")


def _redirects_of(command, index):
    """The redirection records of one command, or the refusal naming the wrong one."""
    raise NotImplementedError("stage 3: implement _redirects_of()")


def _expanded(machine, words, variables):
    """Every word's expansion in order: one word may become several, or none at all.

    The expansion is §4.2's, called once per word as written and never again on its
    own result, and a word whose expansion is an error contributes no word — which is
    how a command whose words all expand to nothing reaches `empty-pipeline`."""
    raise NotImplementedError("stage 3: implement _expanded()")


def _fd_number(value):
    """A descriptor number, or None when it is not a small non-negative int."""
    raise NotImplementedError("stage 3: implement _fd_number()")


def _fd_of(record, kind):
    """The number a redirection names, or the number its kind implies."""
    raise NotImplementedError("stage 3: implement _fd_of()")


def _one_word(machine, record, variables):
    """A redirection's target expanded to exactly one word, or the refusal saying why.

    The answer is `(word, None)` or `(None, error)`: a target that expands to no word
    (an unset variable, §4.2) or to several (a split, §4.2) names no one file, and
    that is `ambiguous-redirect` and not a guess."""
    raise NotImplementedError("stage 3: implement _one_word()")


def _applied_table(machine, command, variables, index, ends, store):
    """One command's descriptor table: the standard numbers, the pipes, then the redirections.

    `ends` is `(read_fd, write_fd)` when the command sits in a pipeline and `None`
    when it stands alone; the pipeline is installed *before* the command's own
    redirections are walked left to right, which is the order a shell must use and
    the reason `2>&1` copies the pipe in one case and the terminal in the other.
    `store` is false in the pure pass that validates the plan and true in the pass
    that has already spent its pipes, so a plan that cannot be made writes nothing.

    The answer is `(table, None)` — the table's `fds` and its applied `redirects` — or
    `(None, error)`; a caller's shape mistake raises `machine.MachineError`."""
    raise NotImplementedError("stage 3: implement _applied_table()")


def _carried(machine, name, argv, incoming):
    """The bytes the machine will carry out of a command, as the plan can know them.

    A writer's own output is a function of its argv (`echo`, `pwd`, `env`) or of
    nothing at all (`false`, `tick`), so the plan knows it exactly; a program that
    transforms its input (`cat`, `grep`, `head`, `sort`, `wc`) carries at most the
    bytes it read, and the shell's own standard input holds nothing the plan has put
    there — so a reader at the head of a pipeline carries nothing."""
    raise NotImplementedError("stage 3: implement _carried()")


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
    which is why `echo x 2>&1 >f | cat` sends its error to the pipe."""
    raise NotImplementedError("stage 3: implement plan()")


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
    raise `machine.MachineError` naming the offender."""
    raise NotImplementedError("stage 3: implement redirects_of()")


def cost_of(machine, names):
    """The machine steps a pipeline of `names` will take, summed from the programs.

    Each name is asked of `programs.program` and its own `steps` added, so the answer
    is the machine's number and not an approximation, and an empty pipeline costs
    nothing. A name the machine holds no program for, a name that is not a string and
    a sequence that is neither a list nor a tuple of names raise `machine.MachineError`
    naming the offender. The machine's ledger does not move across this call: the cost
    is arithmetic over the world's own program data and not a door."""
    raise NotImplementedError("stage 3: implement cost_of()")
