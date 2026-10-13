"""Orchestration From Scratch — stage 6: One failure, and the rest of the graph.

The finished implementation. The reasoning — why a failure takes its transitive
dependents and not its wave, why a dependent that was already dispatched is still
skipped while a sibling still runs, why the cascade never rewrites a node that
already finished `ok`, and why the new states are a fresh, id-sorted mapping —
lives in the DESIGN DECISION blocks of `stage_06.py`.
"""

from collections.abc import Mapping, Sequence, Set

from stage_01 import OrchestrationError

#: The states a node may be in, in the order the course defines them. A state
#: that is not one of these is a caller's typo, and a typo that runs as a state
#: is a run whose report cannot be recomputed from its own record.
_STATES = ("pending", "running", "awaiting", "ok", "failed", "skipped")

#: The states a node does not come back from: a node that has one of these has a
#: result or a verdict of its own, and the cascade leaves it alone. A skip is a
#: statement about work that *will not happen*, and it cannot be written over
#: work that already did.
_FINISHED = ("ok", "failed", "skipped")

#: The states that take the rest of the graph down with them. A failure and a
#: skip are one fact seen from two nodes — the work downstream of either cannot
#: be computed — so the same cascade answers both.
_CASCADES = ("failed", "skipped")

#: What a node the caller's states do not mention is: nothing has happened to
#: it. A node the states *do* mention and the graph does not have is a refusal,
#: not a default.
_UNSEEN = "pending"

#: What a node that will not run becomes, whatever it was doing — still
#: `pending`, already dispatched as `running`, or `awaiting` an approval — when
#: the dependency it was waiting for failed.
_SKIPPED = "skipped"


def _require_graph(graph, what):
    """The graph this stage walks: stage 1's parsed mapping of id to subtask.

    A list, a string or a raw plan is not one, and the refusal names the
    function that wanted it, because the caller has to know which of the two
    surfaces they called with the wrong thing.
    """
    if not isinstance(graph, Mapping):
        raise OrchestrationError(
            "%s: a graph must be a mapping of id to subtask, got %r"
            % (what, type(graph).__name__))
    return graph


def _failed_ids(graph, failed):
    """The ids the caller says failed: one id, or a collection of them.

    A single failure is the common case, and `failed` is one id when it is a
    string and a collection of ids otherwise — `()` is no failure at all. The
    offenders are examined in sorted order, so which one a refusal names first
    is a function of the caller's ids and not of the order they wrote them in.
    """
    if isinstance(failed, str):
        ids = (failed,)
    elif isinstance(failed, (bytes, bytearray)) or not isinstance(failed, (Sequence, Set)):
        raise OrchestrationError(
            "skip_set: `failed` must be a node id or a collection of ids, got "
            "%r" % (type(failed).__name__,))
    else:
        ids = tuple(failed)
    for index, node_id in enumerate(ids):
        if not isinstance(node_id, str):
            raise OrchestrationError(
                "skip_set: failed[%d] must be a str id, got %r"
                % (index, node_id))
    for node_id in sorted(ids):
        if node_id not in graph:
            raise OrchestrationError(
                "skip_set: %r is not a node of this graph, so it cannot be the "
                "one that failed" % (node_id,))
    return tuple(sorted(set(ids)))


def _dependents(graph):
    """The reverse edges, built once and read as values: for every id, the ids
    that name it in their `depends`.

    Every tuple is sorted and deduplicated for the reason the graph's ids are: a
    node that spells the same dependency twice waits for it once, and the walk
    below must not depend on the order the plan was written in.
    """
    names = {}
    for node_id in sorted(graph):
        for dependency in graph[node_id].depends:
            names.setdefault(dependency, set()).add(node_id)
    return {node_id: tuple(sorted(edges)) for node_id, edges in names.items()}


def skip_set(graph, failed):
    """The transitive dependents of the nodes that failed, sorted.

    Read as a prediction about work that will not happen: every node that
    depends on a failed node, directly or through any number of levels, can no
    longer be computed, and every node that does not is untouched — a sibling of
    the failure is not its dependent, and neither is the wave the failure
    happened to run in. The failed nodes themselves are not in their own skip
    set: they failed, they were not skipped.
    """
    _require_graph(graph, "skip_set")
    failed_ids = _failed_ids(graph, failed)
    dependents = _dependents(graph)
    down = set(failed_ids)
    queue = list(failed_ids)
    while queue:
        node_id = queue.pop()
        for dependent in dependents.get(node_id, ()):
            if dependent not in down:
                down.add(dependent)
                queue.append(dependent)
    return tuple(sorted(down - set(failed_ids)))


def propagate(graph, states, node_id, status):
    """The states after `node_id` reaches `status`, the rest of the graph behind
    it.

    A node that reaches `failed` or `skipped` takes its transitive dependents
    down with it: each becomes `skipped`, whatever it was doing — a node that was
    already dispatched (`running`) is skipped too, because the dependency it was
    waiting for failed after it started and its result is worthless. A node that
    has finished — `ok`, `failed` or `skipped` — keeps the state it finished
    with.

    The mapping that comes back is fresh, holds every node of the graph in
    sorted id order, and gives a node the caller's states do not mention the
    state `pending`.
    """
    _require_graph(graph, "propagate")
    if not isinstance(states, Mapping):
        raise OrchestrationError(
            "propagate: the states must be a mapping of id to state, got %r"
            % (type(states).__name__,))
    if status not in _STATES:
        raise OrchestrationError(
            "propagate: %r is not a state; the states are %r"
            % (status, _STATES))
    if not isinstance(node_id, str) or node_id not in graph:
        raise OrchestrationError(
            "propagate: %r is not a node of this graph, so it cannot be the one "
            "whose state changed" % (node_id,))
    for node in sorted(states, key=repr):
        if not isinstance(node, str) or node not in graph:
            raise OrchestrationError(
                "propagate: the states name %r, which is not a node of this "
                "graph" % (node,))
        if states[node] not in _STATES:
            raise OrchestrationError(
                "propagate: the state of %r is %r, which is not a state; the "
                "states are %r" % (node, states[node], _STATES))
    new = {}
    for node in sorted(graph):
        new[node] = states[node] if node in states else _UNSEEN
    new[node_id] = status
    if status in _CASCADES:
        for dependent in skip_set(graph, node_id):
            if new[dependent] not in _FINISHED:
                new[dependent] = _SKIPPED
    return new
