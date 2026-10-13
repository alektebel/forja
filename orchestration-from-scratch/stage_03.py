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

TODO: implement `runnable` and `dispatchable`.
"""

from collections.abc import Mapping

from stage_01 import OrchestrationError


def runnable(graph, states):
    """Every node that may start now: the `pending` ones whose every dependency
    is `ok`, sorted by id."""
    raise NotImplementedError("stage 3: implement runnable()")


def dispatchable(graph, states, *, running, limit):
    """The first `limit - running` ids of `runnable(graph, states)`, and never
    anything else."""
    raise NotImplementedError("stage 3: implement dispatchable()")
