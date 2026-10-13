"""Orchestration From Scratch — stage 10: Two runs, identical bytes.

The finished implementation. The reasoning — why the record is the run's only
truth, why an approval is asked and never dispatched, why the budget refusal is
a state, why a failure is carried and never caught, and why every collection the
loop walks is sorted — lives in the DESIGN DECISION blocks of `stage_10.py`.
"""

from collections.abc import Mapping

from agents import APPROVALS, Agent
from fleet import Clock

import stage_01
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07
import stage_08
import stage_09
from stage_01 import OrchestrationError

#: How many nodes a tick may put in the air when the caller does not say: four,
#: the cap the six-node fan of `graphs["wide"]` has to respect, so a run that
#: ignores the cap is visible on a fixture rather than only in an argument.
DEFAULT_LIMIT = 4

#: The actor of the run's own lines. `skip`, `budget` and `done` are the run's
#: decisions and not a node's: no agent made them, and a line that named an
#: agent for them would blame a worker for the policy that stopped it.
_RUN = "run"

#: The label of the node that answers an approval, as stage 7 fixes it.
_APPROVER = "approver"

#: The six states, spelled once: the run writes them into its table and stage 9
#: reads the same six words back out of the record.
_PENDING = "pending"
_RUNNING = "running"
_AWAITING = "awaiting"
_OK = "ok"
_FAILED = "failed"
_SKIPPED = "skipped"

#: The identifying text of stage 7's hold: the effect may not be dispatched
#: while its approval has not answered, and the run is the one place that turns
#: that refusal into a decision (hold the effect) instead of a traceback.
_HELD = "effect-before-approval"


def _require_count(value, what):
    """A count the run spends: a real int, not negative, and never the flag
    `True` — `isinstance(True, int)` is true and `limit=True` is not a cap."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrchestrationError("%s must be an int count, got %r" % (what, value))
    if value < 0:
        raise OrchestrationError("%s must be >= 0, got %r" % (what, value))
    return value


def _require_graph(graph):
    """The plan the run walks: stage 1's parsed mapping of id to subtask.

    A raw plan — the dicts `graphs.pick` hands around — is refused by naming the
    node, because every stage the loop calls reads `depends`, `ticks`, `tokens`
    and `effect` off the frozen record, and a run that walked a raw plan would
    be reading a shape nobody validated.
    """
    if not isinstance(graph, Mapping):
        raise OrchestrationError("run(): a graph must be a mapping of id to "
                                 "subtask, got %r" % (type(graph).__name__,))
    for node_id in sorted(graph, key=repr):
        if not isinstance(node_id, str):
            raise OrchestrationError("run(): a node id is a string, and %r is "
                                     "not" % (node_id,))
        node = graph[node_id]
        for field in stage_01.SUBTASK_KEYS:
            if not hasattr(node, field):
                raise OrchestrationError(
                    "run(): graph[%r] is %r, not a subtask: stage_01.parse_graph() "
                    "is what validates a plan" % (node_id, node))
    return graph


def _require_plan(graph):
    """The plan, checked before the loop starts: an order exists, and every
    effect has exactly one approval.

    Both are the graph's own business and both are refused *here*, before a
    tick is spent: a cycle has no schedule at all, and an effect whose approval
    is missing or doubled is a graph in which an effect can reach the world with
    nobody to stop it — the one defect this course exists to prevent, and not
    something to discover halfway through a run.
    """
    stage_02.validate_order(graph)
    for node_id in sorted(graph):
        if graph[node_id].effect:
            stage_07.needs_approval(graph, node_id)
    return graph


def _require_clock(clock):
    """J1's clock, injected or fresh: a run counts ticks and never reads one."""
    if clock is None:
        return Clock()
    if not isinstance(clock, Clock):
        raise OrchestrationError("run(): the clock must be a fleet.Clock, got %r: "
                                 "a run's ticks are counted, never timed"
                                 % (type(clock).__name__,))
    return clock


def _require_agents(table):
    """The actors: a mapping of the plan's agent labels to `agents.Agent`.

    A label the plan names and the mapping does not is refused when the node is
    called — not here, because a plan may name an actor for a node the run never
    reaches — but a mapping that is not one, or one holding something that is
    not an `Agent`, is refused before the first tick.
    """
    if not isinstance(table, Mapping):
        raise OrchestrationError("run(): `agents` must be a mapping of agent "
                                 "label to Agent, got %r" % (type(table).__name__,))
    for label in sorted(table, key=repr):
        if not isinstance(table[label], Agent):
            raise OrchestrationError("run(): agents[%r] is %r, not an "
                                     "agents.Agent" % (label, type(table[label]).__name__))
    return table


def _actor(table, node, override=None):
    """Who answers for `node`: the caller's `override` when it gave one, else
    the plan's own label.

    A label with no agent is the mistake a run meets most often, so it is
    refused by name — the node, its label and the labels the run does have —
    rather than as a `KeyError` three lines later.
    """
    if override is not None:
        return override
    try:
        actor = table[node.agent]
    except (KeyError, TypeError):
        raise OrchestrationError(
            "the node %r runs as %r, and the run has no agent for it: it has %r"
            % (node.id, node.agent, tuple(sorted(table, key=repr)))) from None
    if not isinstance(actor, Agent):
        raise OrchestrationError("agents[%r] is %r, not an agents.Agent: the "
                                 "node %r has nobody to call"
                                 % (node.agent, type(actor).__name__, node.id))
    return actor


def _label(actor, fallback):
    """The name a record keeps for a call: the agent's own label, so a record
    says who answered and not which slot it was found in."""
    label = getattr(actor, "label", None)
    return label if isinstance(label, str) and label.strip() else fallback


def _gated_effects(graph, gate_id):
    """Every effect node that waits for the approval `gate_id`, sorted.

    An approval is a dependency whose agent is the approver, as stage 7 fixes
    it, so which effects a gate node answers for is a function of the plan and
    not of the order the plan was written in.
    """
    if graph[gate_id].agent != _APPROVER:
        return ()
    effects = []
    for node_id in sorted(graph):
        node = graph[node_id]
        if node.effect and gate_id in node.depends:
            if stage_07.needs_approval(graph, node_id):
                effects.append(node_id)
    return tuple(effects)


def _file(work, tick, node_id, kind, actor, status, tokens=0):
    """One line of the record, written by stage 9's own writer: the run never
    builds a line itself, so the record's shape has one author."""
    work["events"].append(stage_09.record(tick, node_id, kind, actor, status, tokens))
    return work["events"][-1]


def _stopped(work, graph, node_id, status, tick):
    """`node_id` reaches `status`, and stage 6 carries it down the graph.

    The nodes stage 6 adds are filed as `skip` lines and *never dispatched*:
    that they were not run is the whole point, so a run that skipped them
    silently and a run that skipped them after running them would look the same
    in the states and in the report — which is exactly the difference the check
    has to be able to see.
    """
    work["statuses"][node_id] = status
    carried = stage_06.propagate(graph, work["statuses"], node_id, status)
    for other in sorted(graph):
        if carried[other] == _SKIPPED and work["statuses"][other] != _SKIPPED:
            work["statuses"][other] = _SKIPPED
            work["in_flight"].pop(other, None)
            _file(work, tick, other, "skip", _RUN, _SKIPPED)


def _skip(work, graph, node_id, tick):
    """The run decides `node_id` is not run: its own `skip` line, and then
    stage 6's carry to everything downstream of it."""
    _file(work, tick, node_id, "skip", _RUN, _SKIPPED)
    _stopped(work, graph, node_id, _SKIPPED, tick)


def _pay(work, graph, budget, node, tick):
    """Stage 8's rule, asked **before** the call: may the run pay for `node`?

    `None` is no budget at all and always pays. A refusal is a *state*: the run
    files the `budget` line, the node becomes `skipped` and stage 6 carries it
    down the graph — the run accounts for the work it did not do instead of
    dying on it. A refusal spends nothing, so its line costs nothing: the cost
    it refused lives in the refusal, and the report's `tokens` stays what the
    run actually spent.
    """
    if budget is None:
        return True
    if stage_08.affordable({"spent": work["spent"], "budget": budget}, node):
        return True
    _file(work, tick, node.id, "budget", _RUN, _SKIPPED)
    _stopped(work, graph, node.id, _SKIPPED, tick)
    return False


def _charge(work, budget, reply):
    """Stage 8's ledger after a call that happened: `spent` grows by exactly
    what the answer says the call cost.

    The run counts a `None` budget too — the report is recomputed from the
    record and the record has to add up — and it asks `affordable` only when a
    budget was given, so a `None` budget refuses nothing.
    """
    ledger = {"spent": work["spent"], "budget": 0 if budget is None else budget}
    work["spent"] = stage_08.spend(ledger, reply)
    return work["spent"]


def _handoff_table(work):
    """The states stage 4 renders a handoff from: a node's accepted result, and
    a bare status for every node that has none.

    Only an accepted result is a handoff — a node that was rejected, skipped or
    never run has no text to hand on, and inventing one (a draft, a reason, a
    count of attempts) is the mistake stage 4 exists to prevent.
    """
    table = {}
    for node_id in sorted(work["statuses"]):
        status = work["statuses"][node_id]
        if status == _OK and node_id in work["texts"]:
            table[node_id] = {"status": _OK, "text": work["texts"][node_id]}
        else:
            table[node_id] = status
    return table


def _dispatch(work, graph, agents, budget, node_id, tick, prompt):
    """One node into the air: the budget, the handoff, the call, the line.

    In that order, because that is the order the failures come in: a call the
    run cannot pay for never happens, and a node whose prompt was never rendered
    is a node the agent would re-invent the work for. The prompt is kept in the
    run's `handoffs`, so what a node was handed is recoverable from the run.
    """
    node = graph[node_id]
    if not _pay(work, graph, budget, node, tick):
        return False
    actor = _actor(agents, node)
    attempt = work["attempts"].get(node_id, 0) + 1
    reply = actor(prompt, attempt=attempt)
    _charge(work, budget, reply)
    work["attempts"][node_id] = attempt
    work["handoffs"][node_id] = prompt
    work["replies"][node_id] = reply
    _file(work, tick, node_id, "dispatch", node.agent, _RUNNING)
    work["statuses"][node_id] = _RUNNING
    work["in_flight"][node_id] = tick + node.ticks
    return True


def _land(work, graph, agents, budget, reviewer, node_id, tick):
    """A node's call is back: its result is accepted, rejected or (once the
    reworks are spent) failed.

    Without a reviewer the result is the worker's word and the node is `ok`.
    With one, stage 5 decides: an acceptance makes the result the handoff, a
    rework re-dispatches the node *at the same tick* with the reviewer's reason
    in its prompt (the reason is what has to reach the next attempt), and a
    rejection with the reworks spent fails the node, which stage 6 carries.
    """
    node = graph[node_id]
    reply = work["replies"].pop(node_id)
    work["in_flight"].pop(node_id, None)
    attempt = work["attempts"][node_id]
    _file(work, tick, node_id, "result", node.agent, _OK, reply.tokens)
    if reviewer is None:
        work["statuses"][node_id] = _OK
        work["texts"][node_id] = reply.text
        return
    verdict_reply = reviewer(stage_05.review_prompt(node, attempt), attempt=attempt)
    _charge(work, budget, verdict_reply)
    verdict = stage_05.next_attempt(_RUNNING, verdict_reply, attempts=attempt)
    _file(work, tick, node_id, "review", _label(reviewer, "reviewer"), verdict,
          verdict_reply.tokens)
    if verdict == "accepted":
        work["statuses"][node_id] = _OK
        work["texts"][node_id] = reply.text
        return
    if verdict == "rework":
        prompt = stage_05.rework_prompt(node, verdict_reply.text, attempt + 1)
        _dispatch(work, graph, agents, budget, node_id, tick, prompt)
        return
    _stopped(work, graph, node_id, _FAILED, tick)


def _ask(work, graph, agents, budget, approver, gate_id, tick):
    """Stage 7's question, asked **before** the effect it stops.

    The gate node is not dispatched: a question is not work, so the record
    carries no `dispatch` for it — what it carries is the ask and then the
    answer, and those are what the effect's dispatch waits for. The effect
    itself is held as `awaiting` while the answer is outstanding, with no line
    of its own, because the thing being waited for is a person and not the plan.

    An answer that is not one of `agents.APPROVALS` is not an answer at all: the
    run refuses it, naming the gate and what arrived, because a script that
    cannot say yes or no has left the effect with nobody to stop it and a run
    that read the silence as consent is the defect this stage exists to prevent.
    A denial answers as surely as an approval does — the effect is skipped, which
    is stage 7's `denied`, and the gate node is `ok` either way because it did
    answer. What the gate answered is that node's own result, and it is what the
    effect is handed, so a `ship` that waits for its approval is told whether the
    answer was yes.
    """
    gate = graph[gate_id]
    effects = _gated_effects(graph, gate_id)
    if not effects or work["statuses"][gate_id] != _PENDING:
        return False
    actor = _actor(agents, gate, approver)
    name = _label(actor, gate.agent)
    _file(work, tick, gate_id, "approval", name, _AWAITING)
    work["statuses"][gate_id] = _AWAITING
    for effect_id in effects:
        work["statuses"][effect_id] = _AWAITING
    if not _pay(work, graph, budget, gate, tick):
        return False
    reply = actor(stage_07.approval_prompt(graph[effects[0]]), attempt=1)
    if not stage_07.answers(reply):
        raise OrchestrationError(
            "the gate %r was asked about the effect %r and answered %r, which is "
            "not one of %r: an answer that is not an approval is not an answer, "
            "and an effect is never made on a guess"
            % (gate_id, effects[0], getattr(reply, "text", reply), APPROVALS))
    _charge(work, budget, reply)
    approved = reply.text == APPROVALS[0]
    work["texts"][gate_id] = reply.text
    _file(work, tick, gate_id, "approval", name,
          "approve" if approved else "deny", reply.tokens)
    work["statuses"][gate_id] = _OK
    for effect_id in effects:
        if approved:
            work["statuses"][effect_id] = _PENDING
        else:
            _skip(work, graph, effect_id, tick)
    return True


def _effect(work, graph, agents, budget, node_id, tick):
    """An effect node's dispatch: the gate decides first, and only `clear`
    opens.

    The gate is asked for its status *before* the dispatch, in the same tick, so
    there is no moment in which the effect is running and the approval is not
    answered — stage 7's refusal, turned into §3's decision: an effect the gate
    holds is held, and the run leaves it `awaiting` instead of dispatching it.
    """
    try:
        answer = stage_07.gate_status(graph, work["statuses"], node_id)
    except OrchestrationError as held:
        if _HELD not in str(held):
            raise
        return False
    if answer != "clear":
        return False
    prompt = stage_04.render_prompt(graph, _handoff_table(work), node_id)
    return _dispatch(work, graph, agents, budget, node_id, tick, prompt)


def _start(work, graph, agents, budget, approver, node_id, tick):
    """One candidate of the scheduler's set, decided the way §3's loop decides
    it: the gate for an effect, the question for a gate, the handoff and the
    call for everything else.

    `False` means the run decided nothing about this node — an effect the gate
    holds — and it is what stops the loop from spinning on a node that cannot
    move.
    """
    if stage_07.needs_approval(graph, node_id):
        return _effect(work, graph, agents, budget, node_id, tick)
    if _gated_effects(graph, node_id):
        return _ask(work, graph, agents, budget, approver, node_id, tick)
    prompt = stage_04.render_prompt(graph, _handoff_table(work), node_id)
    return _dispatch(work, graph, agents, budget, node_id, tick, prompt)


def run(graph, agents, *, clock=None, limit=DEFAULT_LIMIT, budget=None,
        reviewer=None, approver=None):
    """§3's loop, end to end: the dispatchable set under the cap, the gate
    before an effect, the budget before the call, the handoff, the call, the
    review, the failure rule and the record.

    The clock is the injected `fleet.Clock` (or a fresh one) and every tick is
    counted, never timed: a tick is one unit of work, a node dispatched at tick
    `t` is back at `t + node.ticks`, and the clock advances only to the next
    thing that can change the state. `limit` is the cap on how many nodes are in
    the air at once; `budget` is the run's token budget or `None` for no budget
    at all; `reviewer` is the `Agent` that reviews every result when it is given
    (stage 5's rule, at most `MAX_REWORK` reworks) and `approver` the `Agent`
    asked for an approval in place of the gate node's own actor.

    What comes back is the run as data: the states (a bare status per node, so
    two runs compare as values), the record (one line per decision, no text), the
    report recomputed from that record by stage 9 — which refuses a claim the
    record contradicts, so the run cannot report a number it did not count — the
    clock's last reading, and the last prompt every dispatched node was handed
    (a reworked node's is stage 5's rework prompt). No value is an object
    identity and no collection is walked in insertion order: two runs of the
    same graph with the same agents are equal, value for value.
    """
    graph = _require_plan(_require_graph(graph))
    clock = _require_clock(clock)
    agents = _require_agents(agents)
    limit = _require_count(limit, "run(): limit")
    if limit < 1:
        raise OrchestrationError("run(): limit=%d is not a cap: a run with no "
                                 "capacity dispatches nothing, ever" % (limit,))
    if budget is not None:
        budget = _require_count(budget, "run(): budget")
    for name, actor in (("reviewer", reviewer), ("approver", approver)):
        if actor is not None and not isinstance(actor, Agent):
            raise OrchestrationError("run(): %s must be an agents.Agent or None, "
                                     "got %r" % (name, type(actor).__name__))
    work = {"statuses": {node_id: _PENDING for node_id in sorted(graph)},
            "texts": {}, "attempts": {}, "handoffs": {},
            "replies": {}, "in_flight": {}, "events": [], "spent": 0}
    tick = clock.now()
    while True:
        due = sorted(node_id for node_id, done in work["in_flight"].items()
                     if done <= tick)
        if due:
            for node_id in due:
                _land(work, graph, agents, budget, reviewer, node_id, tick)
            continue
        candidates = stage_03.dispatchable(graph, work["statuses"],
                                           running=len(work["in_flight"]),
                                           limit=limit)
        started = 0
        for node_id in candidates:
            started += 1 if _start(work, graph, agents, budget, approver,
                                   node_id, tick) else 0
        if started:
            continue
        if not work["in_flight"]:
            break
        soonest = min(work["in_flight"].values())
        clock.tick(soonest - tick)
        tick = clock.now()
    tick = clock.now()
    _file(work, tick, None, "done", _RUN, "done")
    states = dict(work["statuses"])
    events = tuple(work["events"])
    return {"states": states,
            "events": events,
            "report": stage_09.report(graph, events, states, ticks=tick,
                                      tokens=work["spent"]),
            "clock": tick,
            "handoffs": {node_id: work["handoffs"][node_id]
                         for node_id in sorted(work["handoffs"])}}
