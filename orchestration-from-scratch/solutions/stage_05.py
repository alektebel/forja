"""Orchestration From Scratch — stage 5: The reviewer that can reject.

A node has run and its result is in hand; a reviewer says `accept` or `reject`,
and the run has to know what that answer *costs the node*: an acceptance is what
lets the result into the handoff, and a rejection re-dispatches the node with the
reviewer's reason in its prompt, up to `MAX_REWORK` times, and then the node is
`failed`. The failure this stage exists to prevent is the one that looks exactly
like progress: a reviewer that rejects, a rejection that is recorded, and a node
that goes on being `ok` — a run that reports success about work nobody accepted.

DESIGN DECISION — why does `rework_prompt` carry the reviewer's reason into the
node's own prompt, instead of asking the node to try again?
    Because a rework that re-sends the *original* prompt asks the node to do the
    same thing again, and the same thing again is the same result: the loop runs,
    the reviewer rejects a second time, and nothing has changed but the tick. The
    reason is the one piece of new information the review produced, so it travels
    with the instruction — and it is *appended* to the node's own prompt rather
    than replacing it, because this is the same node: the prompt is the node's
    instruction plus what the reviewer said about the attempt just made.

DESIGN DECISION — why is `MAX_REWORK` a bound at all, and why does spending it
*fail* the node rather than stop trying?
    Because a reviewer that rejects forever and a node that reworks forever look
    exactly like a run that is making progress: attempts keep happening and ticks
    keep passing, and no counter ever says the run is going in circles. The bound
    is the difference between a rework and a livelock. When the bound is spent the
    node is `failed` — a state stage 6 can propagate and stage 9 can record — and
    an unbounded `while` has neither. `MAX_REWORK` counts *reworks* (2), so a node
    that is reviewed is dispatched at most three times: the original and two more.

DESIGN DECISION — why does `accepts` read `Reply.text` and never `Reply.tokens`?
    Because the two are different facts about the same call. `Reply.tokens` is
    what the call *cost* — stage 8 spends exactly this number — and `Reply.text`
    is what the agent *said*. A verdict read from the cost accepts a failure that
    happened to be cheap and rejects a success that happened to be expensive, and
    the bug is invisible until a budget changes. So the acceptance is exactly the
    `Reply.text`, and only a text that `agents.VERDICTS` declares is a verdict at
    all: any other text — what a `refuser` answers — is a rejection, and its text
    is the reason the rework carries back to the node.

DESIGN DECISION — why must `state` be `"running"`, and what does refusing every
other state prevent?
    Because a review is a decision about a *result that is in hand*. A node is
    `running` between its dispatch and the verdict, `ok` once a review accepted it
    and `failed` once the bound is spent. A review that arrives in any other state
    is out of order, and the most dangerous of them is a review of an `ok` node:
    it can only agree (doing nothing) or reject a result that later stages have
    already been handed on — the rejection recorded and then ignored, with the
    node still `ok`. Refusing it names the state, so the run stops where it went
    wrong instead of carrying a lie forward.

DESIGN DECISION — why is a rework the same node's next attempt, and not a new
node?
    Because a rework is a decision about one node, and the record stage 9 builds
    has one entry per node. If a rework became a new node, a run would report more
    nodes than its graph has, the attempt counts would be per-run instead of
    per-node, and two runs of the same graph — one reviewed and accepted first
    time, one reworked — would not agree on `nodes`. So `next_attempt` decides for
    the node it was handed, `rework_prompt` restates that same node's id, and the
    attempt number is that node's own count.

TODO: implement `MAX_REWORK`, `review_prompt`, `accepts`, `rework_prompt` and
`next_attempt`.
"""

from agents import Reply, VERDICTS
from stage_01 import OrchestrationError, Subtask

#: How many times a rejected node may be re-dispatched with the reviewer's
#: reason before it is failed. Two reworks, so a reviewed node is dispatched at
#: most three times; the third rejection is the failure.
MAX_REWORK = 2

#: The one verdict that accepts a result: the other text in `agents.VERDICTS` is
#: a rejection, and any text that is not a verdict is a rejection too — the text
#: a `refuser` answers is the reason a rework carries back to the node.
_ACCEPT = VERDICTS[0]

#: The states in which a node's result is in hand and a review may decide its
#: fate: the node has run and no verdict has been written yet. Any other state is
#: a review out of order, and refusing it names the state.
_REVIEWABLE = ("running",)


def _require_node(node):
    """The node being reviewed: a stage 1 `Subtask`, or nothing to review."""
    if not isinstance(node, Subtask):
        raise OrchestrationError(
            "a review is of a Subtask, got %s" % (type(node).__name__,))
    return node


def _require_count(value, what):
    """An attempt or a count of them: a real `int` from one, and `bool` refused
    although `isinstance(True, int)` is true, because `True` is a flag."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrchestrationError("%s must be an int, got %r" % (what, value))
    if value < 1:
        raise OrchestrationError("%s must be at least 1, got %r" % (what, value))
    return value


def _require_reason(reason):
    """The reviewer's reason: the text that has to reach the next attempt. A
    blank reason is no reason, and a rework that carries it changes nothing."""
    if not isinstance(reason, str) or not reason.strip():
        raise OrchestrationError(
            "a rework reason must be a non-blank string, got %r" % (reason,))
    return reason


def _require_reply(reply):
    """The reviewer's answer: a `Reply`, whose `text` is the verdict. Anything
    else has no verdict to read."""
    if not isinstance(reply, Reply):
        raise OrchestrationError(
            "a review reads its verdict from a Reply, got %s"
            % (type(reply).__name__,))
    return reply


def review_prompt(node, attempt):
    """The prompt handed to the reviewer of `node`'s `attempt`-th result."""
    _require_node(node)
    _require_count(attempt, "a review attempt")
    return "review %s (attempt %d): %s" % (node.id, attempt, node.prompt)


def accepts(reply):
    """True when the reviewer's reply accepts the result.

    The verdict is exactly `Reply.text`, and the acceptance is the one text
    `agents.VERDICTS` declares as accepting: `tokens` is the cost of the call and
    never the verdict, and a text that is not a verdict is not an acceptance.
    """
    _require_reply(reply)
    return reply.text == _ACCEPT


def rework_prompt(node, reason, attempt):
    """The prompt `node` is re-dispatched with after a rejection: its own
    instruction, then the reviewer's `reason` and which attempt this becomes."""
    _require_node(node)
    _require_count(attempt, "a rework attempt")
    reason = _require_reason(reason)
    return "%s\n(rework %s, attempt %d, rejected: %s)" % (
        node.prompt, node.id, attempt, reason)


def next_attempt(state, reply, *, attempts):
    """The review's one decision: `"accepted"`, `"rework"` or `"failed"`.

    `state` is the reviewed node's status and must be `"running"` — a review of a
    node whose verdict is already written is out of order. `attempts` is how many
    times the node has been dispatched, the attempt just reviewed included; a
    rejection that has already spent `MAX_REWORK` reworks fails the node.
    """
    if state not in _REVIEWABLE:
        raise OrchestrationError(
            "a review decides a %s node, and this one is %r"
            % ("/".join(_REVIEWABLE), state))
    _require_reply(reply)
    _require_count(attempts, "attempts")
    if accepts(reply):
        return "accepted"
    if attempts > MAX_REWORK:
        return "failed"
    return "rework"
