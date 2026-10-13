"""Orchestration From Scratch — stage 4: The handoff that carries its own context.

The finished implementation. The reasoning — what a budget is a budget of and
why the cut is exact, why a child gets its own dependencies' results and not
every ancestor's, what a state is and which of the six makes a result part of
the handoff, what separates two results and what an empty handoff renders to,
and what this stage refuses — lives in the DESIGN DECISION blocks of
`stage_04.py`.
"""

from collections.abc import Mapping

from stage_01 import OrchestrationError, Subtask

#: The six states of the frozen execution model, in the order a reader meets
#: them. A status outside this tuple is not a state this stage guesses at.
_STATUSES = ("pending", "running", "awaiting", "ok", "failed", "skipped")

#: What separates one dependency's result from the next, and the node's prompt
#: from the block of them: one character, and the same one both times.
_SEPARATOR = "\n"

#: The keys a state record carries: the status the node is in, and the text it
#: answered. A record may carry more; the handoff reads these two.
_STATUS_KEY = "status"
_TEXT_KEY = "text"


class HandoffError(OrchestrationError):
    """A handoff this stage refuses: a plan that was never parsed, a node or a
    dependency the graph does not have, a state that is not one of the six, a
    budget that is not an int count.

    Derived from stage 1's `OrchestrationError`, so one `except` catches a
    broken graph and a broken handoff, and every message names the node, the
    status or the budget at fault.
    """


def _budget(tokens, what):
    """A budget: a real `int` count, and not negative.

    `bool` is refused although `isinstance(True, int)` is true — `True` is a
    flag, and a flag that passes as the budget 1 is a budget nobody wrote — and
    a float is refused rather than truncated, because a budget that arrives as a
    float has already been rounded somewhere else.
    """
    if isinstance(tokens, bool) or not isinstance(tokens, int):
        raise HandoffError("%s must be an int count of tokens, got %r"
                           % (what, tokens))
    if tokens < 0:
        raise HandoffError("%s must be >= 0, got %r" % (what, tokens))
    return tokens


def budgeted(text, tokens):
    """`text` cut to `tokens` characters, exactly, or the refusal that names the
    budget it was given.

    A token is one character: `len` on the string and a slice at the budget, so
    a result of seventeen characters with a budget of three comes back as its
    first three, and the same result with a budget of seventeen or more comes
    back whole. Nothing here divides, rounds or measures bytes.
    """
    if not isinstance(text, str):
        raise HandoffError("a result to hand on must be a str, got %r"
                           % (type(text).__name__,))
    tokens = _budget(tokens, "the budget of a result")
    return text[:tokens]


def _node(graph, node_id):
    """The node `graph` holds under `node_id`, or the refusal that names what
    was wrong with the question.

    A graph that is not a mapping, or whose node is not a `Subtask`, is a plan
    nobody parsed: the handoff reads `depends`, `prompt` and `tokens` off the
    record stage 1 froze, and a raw plan would answer those questions with a
    `KeyError` three lines later.
    """
    if not isinstance(graph, Mapping):
        raise HandoffError("a graph must be a mapping of id to subtask, got %r"
                           % (type(graph).__name__,))
    if node_id not in graph:
        raise HandoffError("the graph does not have the node %r" % (node_id,))
    node = graph[node_id]
    if not isinstance(node, Subtask):
        raise HandoffError("the node %r is %r, not a `Subtask`: the graph must "
                           "be the one stage 1 parsed"
                           % (node_id, type(node).__name__))
    return node


def _states(states):
    """The state table: a mapping of node id to state, or the refusal that says
    what a state table is."""
    if not isinstance(states, Mapping):
        raise HandoffError("the states must be a mapping of node id to state, "
                           "got %r" % (type(states).__name__,))
    return states


def _status(status, node_id):
    """One of the six statuses, or the refusal that names the node and the
    status a state table got wrong."""
    if status not in _STATUSES:
        raise HandoffError("the state of %r is %r, and the states are %r"
                           % (node_id, status, _STATUSES))
    return status


def _state(states, node_id):
    """The `(status, text)` of `node_id` in `states`, or `("pending", "")` when
    the table does not name it.

    A state is one of the six statuses — a node with nothing to hand on yet —
    or a record carrying the status and the text it answered. Only a record
    whose status is `ok` has a text this stage reads: a node whose work was not
    accepted has no result, so whatever a run keeps under `text` for a draft,
    a reason or a count of attempts is not one.
    """
    if node_id not in states:
        return "pending", ""
    value = states[node_id]
    if isinstance(value, str):
        return _status(value, node_id), ""
    if not isinstance(value, Mapping):
        raise HandoffError("the state of %r is %r, and a state is one of %r or a "
                           "record carrying %r"
                           % (node_id, type(value).__name__, _STATUSES,
                              (_STATUS_KEY, _TEXT_KEY)))
    if _STATUS_KEY not in value:
        raise HandoffError("the state of %r spells no %r: a record's keys are %r"
                           % (node_id, _STATUS_KEY, (_STATUS_KEY, _TEXT_KEY)))
    status = _status(value[_STATUS_KEY], node_id)
    if status != "ok":
        return status, ""
    text = value.get(_TEXT_KEY, "")
    if not isinstance(text, str):
        raise HandoffError("the state of %r spells a %r that is not a str, got "
                           "%r" % (node_id, _TEXT_KEY, type(text).__name__))
    return status, text


def _dependencies(graph, node):
    """The node's own dependencies, each id once, sorted by id.

    The plan's own order is stage 1's data, and this is where writing one
    dependency twice stops meaning two results: an id names one node, whose
    accepted result is one text. Sorted, so that a node handed two results is
    handed them in the same order as every other node that waits for the same
    pair, whatever order the plan happened to spell.
    """
    for dependency in node.depends:
        if dependency not in graph:
            raise HandoffError("the node %r waits for %r, which the graph does "
                               "not have" % (node.id, dependency))
    return tuple(sorted(set(node.depends)))


def handoff(graph, states, node_id):
    """The accepted results of the node's own dependencies, each cut to the
    budget that dependency declared, in sorted order.

    One entry per dependency that is `ok`, labelled with the id it came from;
    a dependency that is not `ok` yet contributes nothing, because its result
    is not one this stage may hand on.
    """
    node = _node(graph, node_id)
    _states(states)
    results = []
    for dependency in _dependencies(graph, node):
        status, text = _state(states, dependency)
        if status != "ok":
            continue
        cut = budgeted(text, graph[dependency].tokens)
        results.append("%s: %s" % (dependency, cut))
    return _SEPARATOR.join(results)


def render_prompt(graph, states, node_id):
    """The node's prompt, and its handoff when it has one.

    A node with no dependency, or none that is `ok`, is rendered as exactly its
    own prompt: no separator, no empty block, nothing to tell the agent that
    something is missing.
    """
    node = _node(graph, node_id)
    block = handoff(graph, states, node_id)
    if not block:
        return node.prompt
    return node.prompt + _SEPARATOR + block
