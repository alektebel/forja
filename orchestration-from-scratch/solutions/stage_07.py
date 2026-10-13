"""Orchestration From Scratch — stage 7: The approval, and the effect it stops.

The finished implementation. The reasoning — why the gate refuses a dispatch
instead of returning a status, why an approval is a node of the graph, why the
plan-level question and the run-level question are two functions, why a denial
is a decision and not a failure, and why the prompt is built from the plan alone
— lives in the DESIGN DECISION blocks of `stage_07.py`.
"""

from agents import APPROVALS

from stage_01 import OrchestrationError

#: The agent label of the node that answers an approval: the one actor a graph
#: puts between an effect and the world. A dependency that is not this label is
#: work, not a gate — and an effect whose dependencies are all workers is an
#: effect nobody can stop.
_APPROVER = "approver"

#: The identifying text every refusal of this stage carries, whatever else its
#: message says: the defect is one defect — an effect reaching the world before
#: its approval was answered — and a caller must be able to catch it by name.
_REFUSAL = "effect-before-approval"

#: The states an effect node's own entry holds while it shows the effect was
#: dispatched: `running` is the effect landing, `ok` is one that landed before
#: anybody answered. Both are read by the refusal only, never by a status.
_MADE = ("running", "ok")


def _node(graph, node_id):
    """The record `node_id` names, or a refusal that names it.

    Every function here starts from the id, so a caller that asks about a node
    the graph does not have hears that — and not a bare `KeyError` it has to
    guess at.
    """
    try:
        return graph[node_id]
    except (KeyError, TypeError):
        raise OrchestrationError("the graph has no node %r; its nodes are %r"
                                 % (node_id, tuple(sorted(graph)))) from None


def _gates(graph, node_id):
    """Every approval of `node_id`: the dependencies whose agent is the
    approver, sorted — so which one a message names is a function of the graph
    and not of the order somebody wrote the plan in."""
    node = _node(graph, node_id)
    return tuple(sorted(dependency for dependency in node.depends
                        if _node(graph, dependency).agent == _APPROVER))


def _approval(graph, node_id):
    """The one approval an effect waits for, or a refusal naming the effect
    that has none or has more than one.

    An effect without an approver among its dependencies has nobody to ask —
    the graph cannot run it safely, whatever later states say. An effect with
    two approvals would open on whichever answered first, which is not a gate.
    """
    node = _node(graph, node_id)
    gates = _gates(graph, node_id)
    if not gates:
        raise OrchestrationError(
            "the effect %r has no approval: none of its dependencies %r is an "
            "%r, so no node in the graph can stop it"
            % (node_id, node.depends, _APPROVER))
    if len(gates) > 1:
        raise OrchestrationError(
            "the effect %r has %d approvals %r: the gate would open on "
            "whichever answered first" % (node_id, len(gates), gates))
    return gates[0]


def approval_prompt(node):
    """The question an approver is asked about an effect, built from the plan:
    the effect's id and the instruction it will run.

    Never from a result — the gate holds the dispatch, so when this is built
    the effect has not happened and there is nothing else to say. A node that
    is not an effect has nothing to approve, and is refused naming the node.
    """
    if getattr(node, "effect", None) is not True:
        raise OrchestrationError("the node %r is not an effect: there is "
                                 "nothing to approve"
                                 % (getattr(node, "id", node),))
    return "approve the effect %r? %s" % (node.id, node.prompt)


def needs_approval(graph, node_id):
    """Whether `node_id` must have its approval answered before it may be
    dispatched: `True` for an effect node, `False` for anything else.

    Answered from the plan, not from the run: an effect node is gated for the
    whole run, and whether the approval has been asked yet lives in `states`,
    where `gate_status()` reads it. An effect no dependency approves, or one
    two dependencies approve, is refused — naming the node.
    """
    node = _node(graph, node_id)
    if not node.effect:
        return False
    _approval(graph, node_id)
    return True


def answers(reply):
    """Whether a reply answers an approval at all: its `text` is one of
    `agents.APPROVALS`, exactly.

    `deny` answers as surely as `approve` does — a denial is a decision, and
    reading it as "no answer yet" holds the effect forever. The tokens never
    decide: what a call cost is not what it meant, and a count that happens to
    be spelled like an approval is still a count. A reply that is not a record
    with a text is refused, naming what arrived.
    """
    text = getattr(reply, "text", None)
    if not isinstance(text, str):
        raise OrchestrationError("an approval is answered by a reply with a "
                                 "text, got %r" % (reply,))
    return text in APPROVALS


def gate_status(graph, states, node_id):
    """What the gate says about dispatching `node_id` given `states`:

    `none`   the node is not an effect; no approval gates it;
    `clear`  the approval answered (`ok`) and the effect has not been decided
             against: the gate is open, and whatever stops the node next is
             not the gate;
    `denied` the approval answered and the effect is not made — the effect
             node is `skipped`, the decision a policy leaves behind, and never
             `failed`;
    `held`   the approval never answered and never will (it is `failed` or
             `skipped`): the gate is shut.

    And it refuses, with `effect-before-approval`, when the effect must not be
    dispatched: its approval has not answered (`pending`, `running`, or the
    `awaiting` of the approver's outstanding call). If the effect node's own
    state shows it was already dispatched, the refusal says the approval
    arrived after the effect — the classic defect, caught instead of filed as
    a success.

    `states` is read, never written: what a run does with the answer — hold,
    dispatch, or record the decision — is the run's business, and a gate that
    edited the states would be a gate that dispatches.
    """
    node = _node(graph, node_id)
    if not node.effect:
        return "none"
    approval = _approval(graph, node_id)
    answer = states.get(approval, "pending")
    if answer == "ok":
        if states.get(node_id, "pending") == "skipped":
            return "denied"
        return "clear"
    if answer in ("failed", "skipped"):
        return "held"
    effect = states.get(node_id, "pending")
    if effect in _MADE:
        raise OrchestrationError(
            "the effect %r is %r while its approval %r is %r: the approval "
            "arrived after the effect: %s"
            % (node_id, effect, approval, answer, _REFUSAL))
    raise OrchestrationError(
        "the effect %r cannot be dispatched while its approval %r is %r, not "
        "'ok': %s" % (node_id, approval, answer, _REFUSAL))
