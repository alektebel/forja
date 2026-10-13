"""Orchestration From Scratch — stage 3: The wave is not the schedule.

The second question about the graph: which of its nodes may start *now*. Stage 1
said what a subtask is, stage 2 says what order the dependencies force, and this
stage says what a run has done about it — the graph is the plan, `states` is what
has happened so far, and the two together are what a dispatcher asks at every
tick. The answer is each node's own dependencies and nothing else: not the wave
the plan put it in, not the sibling that was dispatched beside it, not the branch
that is running slow.

DESIGN DECISION — why does `runnable` not use the graph's waves?
    Because a wave is a fact about the *plan* and a schedule is a fact about the
    *run*. A node's wave is the longest chain of dependencies that ends in it, a
    number the plan fixes and the same at every tick; what may run now depends on
    what has finished. A node waits for its own dependencies and for nothing
    else: on a diamond whose two branches were dispatched together, the fast
    branch's successor is runnable the moment that branch is `ok`, even while
    its slow sibling is still `running`. The plausible wrong answer — filter the
    states table by wave index and run the lowest wave that is not entirely `ok`
    — cannot be told from this one on a chain, where every wave holds a single
    node and every wave's dependency is the wave before, and it is wrong on a
    diamond: it holds the fast branch's work behind the slow branch's ticks.
    `graphs["diamond"]`, `render` cut to one tick and `index` stretched to five,
    is what tells the two apart, because the wave rule costs the run exactly the
    four ticks the fast branch saved.

DESIGN DECISION — what is a node's state when the `states` table does not spell
it?
    `pending`. A run begins with an empty table — nothing has been dispatched and
    nothing has finished — so a scheduler that demanded every id be present would
    make the caller materialise the whole graph before the first tick, and the
    first tick is exactly when "everything is pending" is the answer. A missing
    key and the string `"pending"` are therefore the same state, and a table that
    spells only what has happened is a complete description of the run.

DESIGN DECISION — which statuses count as done?
    Only `ok`. `running` is a node in flight, not a dependency satisfied;
    `awaiting` is a node waiting on a person, not on work; and `failed` and
    `skipped` are what stage 6 propagates — a dependent of a failed node is a
    node that must *not* run, which is the failure this course exists to prevent.
    The tempting shortcut is to read "not pending" as done, and it is the worst
    of them: a node is `running` from the tick it is dispatched, so the shortcut
    would unlock every child the instant its parent started, and the child would
    be handed a result that does not exist yet.

DESIGN DECISION — why does `dispatchable` take the first ids in sorted order
when more nodes are runnable than there are slots?
    Because the schedule must be a function of the graph and of the table, and
    of nothing else. `runnable` returns ids sorted, so a prefix is the one choice
    that cannot depend on the order a dict was built in, on which node was
    dispatched last, or on how the caller happened to iterate. Round-robin,
    most-slack-first, or whichever node the plan wrote first would let two
    identical runs choose different nodes — and the last stage of this course is
    a run whose record two runs must reproduce byte for byte.

DESIGN DECISION — why is a call with `running` above `limit` a refusal, and not
an empty answer?
    Because this stage is the only writer of the in-flight count: `dispatchable`
    is what hands a node out, so `running` counts what a previous call returned,
    and a caller that reports four in flight under a cap of two has lost track of
    the run. Answering `()` would look like a saturated scheduler — a legitimate
    state, and the only state this stage answers with nothing while nodes are
    ready — and would hide the disagreement for the rest of the run. `running ==
    limit` is that legitimate saturation and does return `()`; a cap of zero is
    refused too, because a run with no capacity ever dispatches nothing, which is
    a caller nobody meant to be blocked rather than a schedule.

DESIGN DECISION — where is the effect gate?
    Not here. This stage answers what may be considered now; whether the world
    may change is stage 7's question, and it is asked with a fact this stage does
    not carry — whether the effect node's approval has been asked and answered.
    So an `effect=True` node whose dependencies are `ok` is dispatchable here,
    exactly like any other node, and the gate that stops it is hung on top by the
    stage that owns approvals. A scheduler that quietly refused effect nodes
    would put half the gate in each stage: a plan whose approver has already said
    yes would stall with nothing in the record saying why.
"""

from collections.abc import Mapping

from stage_01 import OrchestrationError

#: The statuses a node may be in — this stage's whole vocabulary, and the one
#: every stage after it spells a state with: `pending` (not dispatched),
#: `running` (dispatched, not back), `awaiting` (an approval was asked and has
#: not been answered), `ok`, `failed`, `skipped`.
_STATES = ("pending", "running", "awaiting", "ok", "failed", "skipped")

#: What a node is when the table does not say: a fresh run's state, so that a
#: caller may spell only what has happened.
_PENDING = "pending"

#: The one status that lets a dependent start. `running` is not it, and neither
#: is `awaiting`, nor `failed`, nor `skipped`.
_OK = "ok"


def _require_mapping(source, what):
    """A graph and a states table are mappings of id to value; a list, a string
    or `None` is not one, and the refusal says which of them it got."""
    if not isinstance(source, Mapping):
        raise OrchestrationError("%s is a %s, not a mapping"
                                 % (what, type(source).__name__))
    return source


def _require_ids(mapping, what):
    """The keys of a graph and of a states table are node ids, and an id is a
    string: a name a plan writes, a refusal prints and a record reports."""
    odd = sorted(repr(key) for key in mapping if not isinstance(key, str))
    if odd:
        raise OrchestrationError("%s: a node id is a string, and %s is not"
                                 % (what, odd[0]))
    return mapping


def _ids(mapping):
    """The ids of a graph or of a states table, in the one order this stage reads
    them in: sorted, so that two spellings of a table are one table, the schedule
    cannot depend on how a dict was built, and a refusal names the same offender
    first."""
    return sorted(mapping)


def _require_graph(graph):
    """The plan this stage walks: a mapping of node id to a *parsed* subtask. A
    raw plan — the dicts `graphs.pick` hands around — is stage 1's to validate,
    and a graph whose values are not records is refused here by name, because a
    scheduler that walks a raw plan is reading a shape nobody validated."""
    _require_ids(_require_mapping(graph, "a graph"), "the graph")
    for node_id in _ids(graph):
        if not hasattr(graph[node_id], "depends"):
            raise OrchestrationError(
                "graph[%r] is %r, not a subtask: stage_01.parse_graph() is what "
                "validates a plan" % (node_id, graph[node_id]))
    return graph


def _table(graph, states):
    """The states table, checked once: every id a node of the graph, every
    status one of the six. What this refuses is a table that would otherwise
    *read* as a state nobody wrote — an id the graph does not have, so a
    finished node looks pending, or a status that is a typo for `ok` (`"done"`,
    `"Okay"`), which would leave a finished node blocking its children for the
    rest of the run with nothing in the table saying why."""
    _require_ids(_require_mapping(states, "a states table"), "the states table")
    table = {}
    for node_id in _ids(states):
        if node_id not in graph:
            raise OrchestrationError(
                "states names %r, which is not a node of the graph" % (node_id,))
        status = states[node_id]
        if status not in _STATES:
            raise OrchestrationError(
                "node %r is %r, which is not one of %r"
                % (node_id, status, _STATES))
        table[node_id] = status
    return table


def _status(table, node_id):
    """A node's status: what the table says, or `pending` when it says nothing.
    The table is read, never written: the caller's own record of the run is not
    this stage's to edit."""
    return table.get(node_id, _PENDING)


def _ready(graph, table, node_id):
    """The one question this stage asks about a node: is every one of *its own*
    dependencies `ok`? Its wave is not the question — a wave is a fact about the
    plan and this is a fact about the run — and neither is the sibling that was
    dispatched beside it, nor how many ticks are left."""
    return all(_status(table, dependency) == _OK
               for dependency in graph[node_id].depends)


def runnable(graph, states):
    """Every node that may start now: the `pending` ones whose every dependency
    is `ok`, sorted by id.

    `pending` is what a node is when `states` does not mention it, so an empty
    table answers with the graph's roots. `ok` is the only status that lets a
    dependent start: `running` is a node in flight, `awaiting` is a node waiting
    on a person, and `failed` and `skipped` are stage 6's to propagate, not this
    stage's to run past.
    """
    _require_graph(graph)
    table = _table(graph, states)
    ready = []
    for node_id in _ids(graph):
        if _status(table, node_id) == _PENDING:
            if _ready(graph, table, node_id):
                ready.append(node_id)
    return tuple(ready)


def _count(value, what):
    """A count the cap arithmetic spends: a real int, not negative, and not the
    flag `True`, since `isinstance(True, int)` is true and `running=True` says
    nothing about how many nodes are in flight."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrchestrationError(
            "dispatchable(): %s=%r is not an int count" % (what, value))
    if value < 0:
        raise OrchestrationError(
            "dispatchable(): %s=%r is negative" % (what, value))
    return value


def dispatchable(graph, states, *, running, limit):
    """The first `limit - running` ids of `runnable(graph, states)`, and never
    anything else.

    The two counts are keyword-only: this is the call that decides what a run
    does next, and `dispatchable(graph, states, 2, 4)` says which of the two is
    the cap only to the person who wrote it. A cap of zero, a negative count and
    a `running` above `limit` are refused, naming the number at fault; the one
    case answered with an empty tuple while nodes are ready is a full scheduler
    (`running == limit`).
    """
    running = _count(running, "running")
    limit = _count(limit, "limit")
    if limit < 1:
        raise OrchestrationError(
            "dispatchable(): limit=%d is not a cap: a run with no capacity "
            "dispatches nothing, ever" % (limit,))
    if running > limit:
        raise OrchestrationError(
            "dispatchable(): running=%d exceeds limit=%d: the caller and the "
            "scheduler disagree about how many nodes are in flight"
            % (running, limit))
    ready = runnable(graph, states)
    return ready[:limit - running]
