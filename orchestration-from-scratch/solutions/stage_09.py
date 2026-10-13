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

The reasoning above is this file's; the stubs it names are implemented below.
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


def _checked(fields, where):
    """The six fields of one line, refused with the offending field named, and
    returned in `EVENT_KEYS` order.

    One writer and one reader share this: `record` builds a line with it and
    `report` checks the lines it was handed with it, so no rule about the
    record's shape can hold in one place and not in the other.
    """
    tick, node, kind, actor, status, tokens = fields
    if kind not in _VERDICTS:
        raise RecordError("%s names the kind %r: the record's kinds are %r"
                          % (where, kind, _KINDS))
    if status not in _VERDICTS[kind]:
        raise RecordError("%s is a %r line and says %r: a %r line says one of %r"
                          % (where, kind, status, kind, _VERDICTS[kind]))
    if kind in _RUN_KINDS:
        if node is not None:
            raise RecordError("%s is a %r line, which is the run's and names no "
                              "node: it names %r" % (where, kind, node))
    elif not isinstance(node, str) or not node.strip():
        raise RecordError("%s is a %r line and must name the node it is about: "
                          "got %r" % (where, kind, node))
    for value, name in ((tick, "tick"), (tokens, "tokens")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RecordError("%s: a line's %s must be an int >= 0, got %r"
                              % (where, name, value))
    if not isinstance(actor, str) or not actor.strip():
        raise RecordError("%s must name its actor, got %r" % (where, actor))
    return dict(zip(EVENT_KEYS, (tick, node, kind, actor, status, tokens)))


def record(tick, node, kind, actor, status, tokens=0):
    """One entry of the record: the six `EVENT_KEYS` fields, frozen, and no text.

    A kind the record does not have, a status that kind cannot say, a `done`
    line that names a node, a node-level line that names none, a tick or a token
    count that is not an int (a `bool` is a flag, not the count 1) and an actor
    that is not a name are all refused, naming the offender.
    """
    line = _checked((tick, node, kind, actor, status, tokens), "a record line")
    return types.MappingProxyType(line)


def _line(entry, index):
    """One line the report was handed, as a mapping of exactly `EVENT_KEYS`.

    A line that carries a key the record does not have is refused here, and it
    is refused *first*, because the key a line must never carry is the prompt,
    the result or the reason: the record is the thing that gets kept, and that
    text is the privacy failure this stage exists to prevent.
    """
    where = "the record's line at index %d" % (index,)
    if not isinstance(entry, Mapping):
        raise RecordError("%s is not a mapping: got %r"
                          % (where, type(entry).__name__))
    carried, wanted = set(entry), set(EVENT_KEYS)
    extra = sorted(carried - wanted, key=repr)
    if extra:
        raise RecordError(
            "%s carries the key %r, and a line carries exactly %r: the prompt, "
            "the result or the reason of a decision is the text a record must "
            "never keep" % (where, extra[0], EVENT_KEYS))
    missing = sorted(wanted - carried)
    if missing:
        raise RecordError("%s does not carry %r: a line carries exactly %r"
                          % (where, missing[0], EVENT_KEYS))
    return _checked(tuple(entry[key] for key in EVENT_KEYS), where)

def _levels(graph):
    """How many levels the graph's dependencies force, counted here.

    The walk places every node whose dependencies are all already placed, one
    level per round, so a node whose dependencies live two levels apart lands
    where the slower one puts it. A graph that never becomes placeable has no
    levels at all, and that is refused by naming a node that is still waiting:
    the report numbers the plan it was handed and trusts no number it did not
    count, so a plan it cannot level is not one it can report on.
    """
    waiting = {node_id: set(graph[node_id].depends) for node_id in graph}
    placed, level = set(), 0
    while waiting:
        ready = sorted(node_id for node_id, waits in waiting.items()
                       if waits <= placed)
        if not ready:
            raise RecordError("the plan cannot be levelled: %r waits for a "
                              "dependency that never finishes, so the plan has a "
                              "cycle" % (sorted(waiting)[0],))
        for node_id in ready:
            del waiting[node_id]
        placed.update(ready)
        level += 1
    return level


def _state_of(node_id, named, last):
    """The state the record's last word leaves a node in, or `pending`."""
    if node_id not in named:
        return "pending"
    return _DECIDED[last[node_id]]


def _claims(nodes, states, named, last, record, ticks, tokens):
    """The run's own account — its states and its two totals — against the record.

    The two totals first, because they are the purest form of the mistake: a
    report handed `ticks=9` for a record whose last line is at tick 6 must not
    print nine. Then the states, node by node: the state a run claims for a node
    is the state the record's last word on that node leaves it in, and `pending`
    for a node no line names — with one exception, because the effect node a gate
    stops waits for its answer without a line of its own and may be `awaiting`
    while the record does not name it at all.
    """
    for name, claim, counted in (("ticks", ticks, record["ticks"]),
                                 ("tokens", tokens, record["tokens"])):
        if claim != counted:
            raise RecordError("the run says its %s is %r and the record counts "
                              "%r: a report is counted from the record, never "
                              "told" % (name, claim, counted))
    if not isinstance(states, Mapping):
        raise RecordError("the run's states are a mapping of node id to a state, "
                          "got %r" % (type(states).__name__,))
    plan = set(nodes)
    for node_id in sorted(states):
        if node_id not in plan:
            raise RecordError("the run's states name the node %r, which the plan "
                              "does not have: the plan is %r"
                              % (node_id, nodes))
    for node_id in nodes:
        claim = states.get(node_id, "pending")
        if claim not in _STATES:
            raise RecordError("the run's state for %r is %r: a node of a run is "
                              "one of %r" % (node_id, claim, _STATES))
        decided = _state_of(node_id, named, last)
        if claim == decided or (claim == "awaiting" and node_id not in named):
            continue
        raise RecordError(
            "the run's states call %r %r and the record's last word on it leaves "
            "it %r: the two accounts of one run must agree"
            % (node_id, claim, decided))


def report(graph, events, states, *, ticks, tokens):
    """The run's report: every `RUN_KEYS` key, counted from the record.

    Each counter is the number of *nodes* the record leaves in a place, not the
    number of lines: a node reviewed, rejected and dispatched again is one node
    dispatched and one reviewed. `ticks` is the highest tick the record names and
    `tokens` is the sum of what its lines cost, and both are recomputed here and
    compared against the totals the run handed in — a claim the record
    contradicts is refused, naming the key and the pair. The states are checked
    the same way, node by node: what the run says a node is must be what the
    record's last word on it leaves it (a node the record never names is
    `pending`, and the effect a gate stops may wait as `awaiting`), so a report
    cannot summarise a run whose two accounts of it disagree.
    """
    nodes = tuple(sorted(graph))
    lines = [_line(entry, index) for index, entry in enumerate(events)]
    named, last = set(), {}
    dispatched, reviewed, approved, rejected = set(), set(), set(), set()
    for index, entry in enumerate(lines):
        node_id = entry["node"]
        if node_id is None:
            continue
        if node_id not in graph:
            raise RecordError("the record's line at index %d names the node %r, "
                              "which the plan does not have: the plan's nodes "
                              "are %r" % (index, node_id, nodes))
        named.add(node_id)
        last[node_id] = (entry["kind"], entry["status"])
        if entry["kind"] == "dispatch":
            dispatched.add(node_id)
        elif entry["kind"] == "review":
            reviewed.add(node_id)
            if entry["status"] == "rework":
                rejected.add(node_id)
        elif entry["kind"] == "approval":
            if entry["status"] == "approve":
                approved.add(node_id)
            elif entry["status"] == "deny":
                rejected.add(node_id)
    outcomes = {"skipped": set(), "failed": set()}
    for node_id in sorted(named):
        state = _state_of(node_id, named, last)
        if state in outcomes:
            outcomes[state].add(node_id)
    record = {key: 0 for key in RUN_KEYS}
    record["graph"] = nodes
    record["nodes"] = len(nodes)
    record["waves"] = _levels(graph)
    record["dispatched"] = len(dispatched)
    record["reviewed"] = len(reviewed)
    record["approved"] = len(approved)
    record["rejected"] = len(rejected)
    record["skipped"] = len(outcomes["skipped"])
    record["failed"] = len(outcomes["failed"])
    record["ticks"] = max([entry["tick"] for entry in lines] or [0])
    record["tokens"] = sum(entry["tokens"] for entry in lines)
    _claims(nodes, states, named, last, record, ticks, tokens)
    return record
