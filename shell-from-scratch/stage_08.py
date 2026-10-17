"""Shell From Scratch — stage 8: Lists, conditions and the rules of `set -e`.

A line is more than one pipeline: `&&`, `||`, `;` and `&` decide which of them
runs at all, and `errexit` decides whether a failure ends the line. This stage
runs a parsed line's lists in order — short-circuiting `&&` and `||` on the left
side's status, running `;` unconditionally, and starting a `&` list without
waiting for it — and records every status with the *kind* that says whether
`errexit` may stop on it.

The kinds are the whole of the `set -e` discipline: a condition's status, the
left side of an `&&`/`||`, a negated pipeline and a pipeline's every command but
the last are all exempt, and a plain failure is not. The stage also owns the one
routing rule the contract pins: a simple command whose first word is a builtin
this shell refuses (`trap`, `kill`, `wait`) goes to the stage that owns it, after
expansion, whatever shape the command sits in.


DESIGN DECISION — Why does every recorded status carry a *kind*, and why is the kind decided by
position rather than by the command?
Because `errexit` is a rule about *where* a failure happened, not *what*
failed: `false` in a condition never stops the shell, the same `false` on a
line alone always does. The kinds are the six positions the rule names, and
`exempt(kind)` is the whole of `set -e` — one function, six answers, no
special cases buried in the runner.

DESIGN DECISION — Why does a `!` negation rewrite the pipeline's last row's status instead of
keeping both numbers?
Because `$?` is one number: after `! false`, the shell's status is 0 and the
fact that the pipeline answered 1 is gone from the record. The kind `negated`
is what survives — it tells the audit *why* the status is 0 — and the
pipeline's own answer is deliberately not kept, because a status the shell
does not carry is a status no later rule can read.

DESIGN DECISION — Why is the in-process path taken only for a sole simple command with no `&`?
Because the two promises conflict otherwise: a state builtin must write the
shell's own memory (§4.7), but a builtin *inside a pipeline* is a child's
command by definition, and a background list is the promise that nothing
waits. The rule draws the line exactly where both promises can hold — one
command, foreground, no redirections — and everything else goes to the plan.

DESIGN DECISION — Why does the routing rule for `trap`, `kill` and `wait` live in this stage and
apply to the first word only?
Because a routing decision made anywhere else would be a special case per
composer, and two composers with two readings of `kill -INT %1` after `&&` is
exactly the disagreement the state record was pinned to prevent. First word
because that is what a simple command is: `echo kill` is not a kill. The rule
is blind to shape — inside a list, after `&&`, or the whole line all route
the same way.
    LISTS_KEYS    the five fields of a line's record, in order
    STATUS_KINDS  the six kinds a status can be recorded under
    run_lists(m, lists, state)  -> LISTS_KEYS
    exempt(kind)                -> bool, errexit may not stop on it
    condition_of(m, condition)  -> (status, kind)

TODO: implement `run_lists`, `exempt`, `condition_of` in this file.
"""

from machine import MachineError
import rules
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07

LISTS_KEYS = ('statuses', 'status', 'stopped', 'skipped', 'error')

STATUS_KINDS = ('plain', 'condition', 'and-or-left', 'negated', 'pipeline-but-last', 'while-condition', 'if-condition')

_CONDITION_KINDS = ('condition', 'if-condition', 'while-condition')

_CONNECTORS = ('&&', '||', ';', '&')

_ROUTED = ('kill', 'trap', 'wait')

_NEGATION = '!'

_STATE_KEYS = ('variables', 'exported', 'jobs', 'flags', 'exit')


def run_lists(machine, lists, state):
    """Run a parsed line's lists and answer the line's own record."""
    raise NotImplementedError("stage 8: implement run_lists()")


def exempt(kind):
    """Whether a status of `kind` is one `errexit` may not stop on."""
    raise NotImplementedError("stage 8: implement exempt()")


def condition_of(machine, condition):
    """Run a condition and answer what it answered, with its kind recorded."""
    raise NotImplementedError("stage 8: implement condition_of()")


def _kind_of(pipeline, connector):
    """The kind a pipeline's status is recorded under: `!` first, then position."""
    raise NotImplementedError("stage 8: implement _kind_of()")


def _execute(machine, shell, pipeline, kind):
    """Run one foreground pipeline; answer (status, rows).

    The rows are what the pipeline answered: a `!`'s negation is the pipeline's
    own answer, so the last command's row — the one the kind belongs to —
    carries the negated status, and any earlier command of the pipeline keeps
    the status it itself answered (§4.8: the kind rides the pipeline's answer)."""
    raise NotImplementedError("stage 8: implement _execute()")


def _in_shell(machine, shell, command, kind):
    """Run a sole simple command in this process, or answer None to fork it.

    A builtin whose owner is another stage is routed by its first word (§4.8's
    rule, so a `wait` after an `&&` is the same `wait`); a stage 7 builtin runs
    where §4.7 says it must; a command that is nothing but an assignment sets a
    shell variable and is never exported. Everything else — a program, a command
    with redirections, a pipeline of more than one command — is answered None and
    goes to the plan."""
    raise NotImplementedError("stage 8: implement _in_shell()")


def _owned(machine, shell, name, argv):
    """Call the stage that owns a builtin stage 7 refuses; answer its status."""
    raise NotImplementedError("stage 8: implement _owned()")


def _launch(machine, shell, pipeline):
    """Start a `&` list as a job without waiting; answer (status, rows)."""
    raise NotImplementedError("stage 8: implement _launch()")


def _record(statuses, status, stopped, skipped):
    """The line's own record, in `LISTS_KEYS` order."""
    raise NotImplementedError("stage 8: implement _record()")


def _row(status, kind, command):
    """One command's status, its kind and the text the shell was given."""
    raise NotImplementedError("stage 8: implement _row()")


def _rows_for(pipeline, status, kind):
    """A row per command of a pipeline that never ran: the pipeline's status."""
    raise NotImplementedError("stage 8: implement _rows_for()")


def _text_of(command):
    """A command as the line wrote it: its words, joined."""
    raise NotImplementedError("stage 8: implement _text_of()")


def _pipeline_text(pipeline):
    """A pipeline as the line wrote it."""
    raise NotImplementedError("stage 8: implement _pipeline_text()")


def _status_of(error):
    """The status a plan's own error is a shell's status for."""
    raise NotImplementedError("stage 8: implement _status_of()")


def _commands_in(pipelines):
    """How many commands a list holds, which is what a short-circuit skipped."""
    raise NotImplementedError("stage 8: implement _commands_in()")


def _negated(pipeline):
    """Whether the pipeline was written with `!` in front of it."""
    raise NotImplementedError("stage 8: implement _negated()")


def _without_negation(pipeline):
    """The pipeline with a leading `!` taken off, ready to be planned."""
    raise NotImplementedError("stage 8: implement _without_negation()")


def _negate(status, pipeline):
    """`0` and `rules.EXIT_FAILURE` the other way round under a `!`."""
    raise NotImplementedError("stage 8: implement _negate()")


def _background(pipeline):
    """Whether the list this pipeline belongs to was ended by `&`."""
    raise NotImplementedError("stage 8: implement _background()")


def _job_row(shell, pid, pipeline):
    """The row the shell keeps for a job it has just started."""
    raise NotImplementedError("stage 8: implement _job_row()")


def _expanded(machine, shell, command):
    """A command's words after §4.2, or None when an expansion failed."""
    raise NotImplementedError("stage 8: implement _expanded()")


def _substituted(machine, text, variables):
    """§4.2's parameter step on an assignment's value, once; None if it refused."""
    raise NotImplementedError("stage 8: implement _substituted()")


def _assign(machine, shell, text):
    """Set a shell variable from `NAME=value`: set, and never exported.

    The status is the value's: an assignment whose value cannot be expanded under
    `nounset` — or a command that is not an assignment at all — answers
    `rules.EXIT_FAILURE` and leaves the table alone."""
    raise NotImplementedError("stage 8: implement _assign()")


def _blank_state():
    """A shell of its own, for a condition that must not move the caller's."""
    raise NotImplementedError("stage 8: implement _blank_state()")


def _lists_of(lists):
    """The parsed line, checked: a tuple of `(pipelines, connector)` pairs."""
    raise NotImplementedError("stage 8: implement _lists_of()")


def _pipelines_of(pipelines):
    """A list's pipelines, or a bare pipeline read as a list of one."""
    raise NotImplementedError("stage 8: implement _pipelines_of()")


def _pipeline_of(pipeline):
    """A pipeline's commands, checked."""
    raise NotImplementedError("stage 8: implement _pipeline_of()")


def _command(command):
    """One `COMMAND_KEYS` record, checked and copied."""
    raise NotImplementedError("stage 8: implement _command()")


def _state_of(state):
    """The shell's own record, checked, and handed back to be mutated in place."""
    raise NotImplementedError("stage 8: implement _state_of()")


def _condition_of(condition):
    """The condition's kind and the pipelines to run, from either shape."""
    raise NotImplementedError("stage 8: implement _condition_of()")
