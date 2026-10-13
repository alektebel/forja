"""Orchestration From Scratch — stage 7: The approval, and the effect it stops.

DESIGN DECISION — Why does the gate refuse the dispatch instead of reporting on it?
    `gate_status()` is asked one question at the one moment that matters: may
    this node be dispatched now? For an effect whose approval has not been
    answered the answer has to *stop* the dispatch, not describe it — a status
    is something a caller may keep, and a caller that keeps it has already sent
    the effect. So the gate refuses, with the text `effect-before-approval`,
    naming the effect and the approval it waits for: holding the dispatch and
    refusing it are the same act, and the alternative — reporting afterwards
    that the effect ran without its approval — is the classic defect.

DESIGN DECISION — Why is the approval a node of the graph, and not a flag on the effect?
    The approval has an actor, costs a call and takes ticks, so it is a node
    like any other: `graphs["gate"]` is `ask` (an `approver`) and then `ship`
    (an `effect`) that depends on it. An effect none of whose dependencies is
    an approver is refused here rather than dispatched: an effect nobody in the
    graph can stop is worse than an effect whose approval is late.

DESIGN DECISION — Why does `needs_approval()` answer from the plan and `gate_status()` from the run?
    `needs_approval()` is the question asked before anything runs — which
    nodes are gated at all? — and it takes no `states`, because whether the
    approval has been *asked* is the run's business and lives in `states`,
    where `gate_status()` reads it. One function answering both halves would
    have to guess which half it was called for, and a scheduler holding the
    plan-level answer at dispatch time dispatches the effect.

DESIGN DECISION — Why is a denial a decision, and not a failure?
    `answers()` is true for `deny`: a denial is an answer, and the worst
    reading of it — `reply.text == "approve"` — files it as "no answer yet",
    holding the effect forever. A denial means the effect is *not made*: the
    run records the decision (the effect node ends `skipped`, the state a
    policy leaves behind) and the gate says `denied`. Nothing failed, and a
    report that called it a failure of the effect would send somebody to repair
    an effect that was never supposed to happen.

DESIGN DECISION — Why is the approval prompt built from the plan alone?
    By the time there is a result to describe, the effect has already landed,
    so asking then is the defect itself. The prompt therefore carries the
    effect's id and the instruction it *will* run, and never a result: the gate
    holds the dispatch, so at the moment the question is asked the effect has
    not happened and there is nothing else to say.

TODO: implement approval_prompt(), needs_approval(), answers(), gate_status().
"""


def approval_prompt(node):
    """The question an approver is asked about an effect, built from the plan.

    The effect's id and the instruction it will run; never a result, because
    the gate holds the dispatch and there is no result yet. A node that is not
    an effect has nothing to approve, and is refused naming the node.
    """
    raise NotImplementedError("stage 7: implement approval_prompt()")


def needs_approval(graph, node_id):
    """Whether `node_id` must have its approval answered before it may be
    dispatched: `True` for an effect node, `False` for anything else.

    Answered from the plan, not from the run: an effect node is gated for the
    whole run. An effect that no dependency of the graph approves, or that more
    than one dependency approves, is refused, naming the node.
    """
    raise NotImplementedError("stage 7: implement needs_approval()")


def answers(reply):
    """Whether a reply answers an approval at all: its `text` is one of
    `agents.APPROVALS`, exactly.

    `deny` answers as surely as `approve` does, and the tokens never decide:
    what a call cost is not what it meant. A reply that is not a record with a
    text is refused, naming what arrived.
    """
    raise NotImplementedError("stage 7: implement answers()")


def gate_status(graph, states, node_id):
    """What the gate says about dispatching `node_id` given `states`.

    `none` for a node that is not an effect (no approval gates it); `clear`
    when the approval answered and the effect has not been decided against;
    `denied` when the approval answered and the effect is not made — the
    effect node is `skipped`, the decision, never `failed`; `held` when the
    approval never answered and never will.

    And it refuses, with `effect-before-approval`, when the effect must not be
    dispatched — its approval has not been answered. If the effect node's own
    state shows it was dispatched, the refusal says the approval arrived after
    the effect. `states` is read, never written.
    """
    raise NotImplementedError("stage 7: implement gate_status()")
