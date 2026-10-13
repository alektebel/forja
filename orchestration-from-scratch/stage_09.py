"""Orchestration From Scratch — stage 9: The record, and the report from it.

A run is over; what did it do? The answer is the record the run wrote, one line
per decision, counted — never a second tally kept beside it. Every stage since
the scheduler appends its own line: `dispatch` from the loop, `result` from the
worker, `review` from the reviewer, `approval` from the gate, `skip` from the
failure rule, `budget` from the budget, and the run's own `done`. The states a
run holds are the *present* — who is running, who was given up on — and the
record is the *history*; a report is that history counted, and it is the only
thing two runs of one plan are compared on, byte for byte.

So `record` is the one writer of the record and `report` is the one reader, and
a line carries the six fields that can be counted and no text at all: the
prompt, the result and the rejection's reason are the transcript, and a record
that keeps them is a record that has to be kept, shipped and redacted.

A line's seven kinds and what each may say: `dispatch` (`running`), `result`
(`ok`, `failed`, `died`), `review` (`accepted`, `rework`, `failed`), `approval`
(`awaiting`, `approve`, `deny`), `skip` and `budget` (`skipped`), and `done`
(`done` — the run's own line, which names no node). `report(graph, events,
states, *, ticks, tokens)` counts every number from those lines and refuses a
claim the record contradicts: what the run says a node is must be what the
record's last word on it leaves it, `ticks` must be the highest tick the record
names, and `tokens` the sum of what its lines cost.

DESIGN DECISION — why is every number in the report counted from the record
instead of read off the states the caller still has in hand?
    The states are right there, already a `{id: status}` mapping, and they are
    the wrong source: they say what is true *now*, while the report is about what
    happened. The two drift the first time a path sets a state and forgets the
    line (or writes the line and forgets the state), and the failure is silent —
    the report describes a run that never happened, and two runs that differed
    look identical when they are compared. One source of truth: the record is
    counted, the states are only checked.

DESIGN DECISION — why does a line carry the six `EVENT_KEYS` fields and no
prompt, result or reason?
    The text is what a run is *about*, and the record is what a run is *kept
    as*: every reason a reviewer gave, every prompt a node was handed and every
    result it returned would sit in the file a replay, a comparison and a
    post-mortem read, so that file becomes the run's transcript by accident —
    twice the size, all of it text nobody asked to keep, none of it countable.
    The six fields are the decisions, and each is a tick, a node, an actor, a
    status or a count. A record that cannot hold text cannot leak it.

DESIGN DECISION — why is `done` the run's own line and not a node's?
    Because a node's last word is already its own decision — a `result`, a
    failing `review`, a `skip` — and one more line saying the same thing is a
    second source of truth about one node. What no node can say is that the
    *run* is over, and that is the one thing a reader of a record needs in order
    to tell a finished run from a truncated one: `done` names no node, and a kind
    that names no node is the record's shape for "this is about the run".

DESIGN DECISION — why do the counters count nodes, so that a rework cannot
count twice?
    A rejected node is dispatched again, so the `dispatch` lines outnumber the
    nodes: three nodes and four dispatch lines is an ordinary chain with one
    rework in it. A tally that counted lines would report four nodes dispatched
    and make a node that took two tries look like two nodes that took one each —
    and the number that is supposed to say how much work the plan did would grow
    with every rejection the reviewer was right about. Every counter is a set of
    node ids; only `ticks` and `tokens` are sums, because only cost adds up.

DESIGN DECISION — why does `record` refuse a kind or a status it does not know?
    Being permissive looks harmless: a later stage adding a kind would not have
    to touch this file. The cost is a record that can carry anything, which is a
    record that nothing can count: an unknown line is invisible in every
    counter, so a typo (`suceeded`, or a `reject` where the review's word is
    `rework`) reads as a run in which nothing was ever rejected instead of as a
    bug. The refusal names the kind, the status and the ones this stage knows, so
    the mistake lands where the line is written instead of three stages later as
    a silence.

DESIGN DECISION — why does `report` refuse the claims it was handed instead of
trusting them or quietly preferring the record?
    `states`, `ticks` and `tokens` are the run's own account of itself, and the
    record is the other one; a report that *trusts* them is the declared-counter
    mistake exactly — the caller has the numbers in hand, so why count? — and a
    report that quietly prefers the record hides the drift that stage 10's
    byte-for-byte comparison exists to catch. Refusing names the node, the key
    and the pair of numbers the moment the two accounts disagree, which is the
    last point at which somebody can still tell which of the two lied.

TODO: implement `EVENT_KEYS`, `RUN_KEYS`, `record` and `report`.
"""

import types
from collections.abc import Mapping

from stage_01 import OrchestrationError

#: The six fields one entry of the record carries, in the order a reader meets
#: them: when the decision was taken, the node it is about, what kind of decision
#: it is, who took it, what it decided and what the call cost. There is no
#: seventh field, and in particular no field for text: a prompt, a result or a
#: reason in the record is the transcript, and the record is not the transcript.
EVENT_KEYS = ("tick", "node", "kind", "actor", "status", "tokens")

#: Every key a report carries, in the order it presents them: the plan it is
#: about (its node ids, sorted), the plan's size, the plan's levels, the six
#: counters, and the two totals. Always all eleven, zero-filled, so two runs are
#: comparable key by key and a reader that unpacks the report reads a field and
#: never a `KeyError`.
RUN_KEYS = ("graph", "nodes", "waves", "dispatched", "reviewed", "approved",
            "rejected", "skipped", "failed", "ticks", "tokens")


class RecordError(OrchestrationError):
    """A record this course refuses: a line with no shape, a line whose kind or
    status is not one of the seven, a claim the record contradicts.

    Derived from `OrchestrationError`, so one `except` still catches a broken
    graph and a broken record, and every message names the line, the node, the
    key or the pair of numbers at fault.
    """


#: The kinds of decision a run takes, in the order they happen. `dispatch` and
#: `result` are the loop and the worker, `review` is the reviewer, `approval` is
#: the gate, `skip` is the failure rule, `budget` is the budget refusing a call
#: before it is made, and `done` is the run's own last line.
_KINDS = ("dispatch", "result", "review", "approval", "skip", "budget", "done")

#: What each kind of line may say. A `dispatch` puts the node in the air; a
#: `result` is the worker's word (`died` is a node that did not make it, and the
#: run has one word for that: `failed`); a `review` is stage 5's three answers;
#: an `approval` is asked (`awaiting`) and then answered; a skipped node is a
#: node no line will ever dispatch, whoever stopped it; and `done` ends the run.
_VERDICTS = types.MappingProxyType({
    "dispatch": ("running",),
    "result": ("ok", "failed", "died"),
    "review": ("accepted", "rework", "failed"),
    "approval": ("awaiting", "approve", "deny"),
    "skip": ("skipped",),
    "budget": ("skipped",),
    "done": ("done",),
})

#: The kind that is the run's line and not a node's: it must name no node, and
#: every other kind must name the node it is about.
_RUN_KINDS = ("done",)

#: The six states a node of a run can be in, as §3 fixes them: a node that has
#: not started, one in the air, one whose answer is pending, and the three
#: endings.
_STATES = ("pending", "running", "awaiting", "ok", "failed", "skipped")

#: The state a line decides the node it names is in. A rework puts the node back
#: in the air; an approval answers the gate, so the node that was asked is `ok`
#: whether it approved or denied (the effect it stops is skipped, and that skip
#: is its own line); and a worker that died is a node that did not make it.
_DECIDED = types.MappingProxyType({
    ("dispatch", "running"): "running",
    ("result", "ok"): "ok",
    ("result", "failed"): "failed",
    ("result", "died"): "failed",
    ("review", "accepted"): "ok",
    ("review", "rework"): "running",
    ("review", "failed"): "failed",
    ("approval", "awaiting"): "awaiting",
    ("approval", "approve"): "ok",
    ("approval", "deny"): "ok",
    ("skip", "skipped"): "skipped",
    ("budget", "skipped"): "skipped",
})


def record(tick, node, kind, actor, status, tokens=0):
    """One entry of the record: the six `EVENT_KEYS` fields, frozen, and no text."""
    raise NotImplementedError("stage 9: implement record()")


def report(graph, events, states, *, ticks, tokens):
    """The run's report: every `RUN_KEYS` key, counted from the record."""
    raise NotImplementedError("stage 9: implement report()")
