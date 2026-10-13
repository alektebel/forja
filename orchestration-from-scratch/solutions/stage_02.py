"""Orchestration From Scratch — stage 2: The order a dependency forces.

The finished implementation. The reasoning — why a wave is one more than the
*max* of a node's dependencies and not one more than its first, why a cycle has
to be named instead of detected by counting waves, why a diamond's two branches
share a wave and its join does not, and why stage 1's refusal of a
self-dependency does not save this stage from looking for cycles of length two —
lives in the DESIGN DECISION blocks of `stage_02.py`.
"""

from collections.abc import Mapping, Sequence

from stage_01 import OrchestrationError, Subtask


def _require_graph(graph):
    """The graph this stage was handed: the frozen mapping stage 1 parsed, with
    at least one node in it.

    Ordering is reasoning about a graph, not building one, so this stage reads
    records instead of re-parsing a plan: a raw plan handed here is refused
    naming the node whose value is not a `Subtask`. An empty graph is refused
    too — a caller that got `()` back would have no way to tell a graph with no
    nodes from one whose nodes are all in the first wave.
    """
    if not isinstance(graph, Mapping):
        raise OrchestrationError("a graph must be a mapping of id to Subtask, "
                                 "got %r" % (type(graph).__name__,))
    for node_id in graph:
        if not isinstance(node_id, str):
            raise OrchestrationError("a graph's key must be a str id, got %r"
                                     % (node_id,))
    if not graph:
        raise OrchestrationError("a graph must have at least one node: an empty "
                                 "graph has no order to have")
    for node_id in sorted(graph):
        node = graph[node_id]
        if not isinstance(node, Subtask):
            raise OrchestrationError(
                "the node %r is %r, not a `Subtask`: this stage orders a graph "
                "that stage 1 has parsed" % (node_id, type(node).__name__))
    return graph


def _edges(graph, node_id):
    """One node's dependencies, exactly as the plan spelled them, refusing an id
    the graph does not have.

    The plan's own order is kept here: `dependencies` is what sorts and
    deduplicates, and the raw spelling is the record's own property, not this
    stage's to lose.
    """
    if node_id not in graph:
        raise OrchestrationError("the graph does not have the node %r; its "
                                 "nodes are %r" % (node_id, sorted(graph)))
    return graph[node_id].depends


def _sorted_edges(graph, node_id):
    """One node's dependencies, sorted by id and deduplicated: the edge set.

    One order for everything this stage prints and walks: a repeat is one edge,
    and the order two runs of the same graph agree on is the ids sorted.
    """
    return sorted(set(_edges(graph, node_id)))


def _require_edges(graph):
    """Every dependency the graph spells must be a node of the graph.

    Stage 1 refuses a plan that names a dependency it does not have; a graph
    assembled after that, or by hand, can still name one, and no wave can be
    computed for an edge that leaves the graph. The refusal names the node that
    wants the missing id and the id it wants.
    """
    for node_id in sorted(graph):
        for dependency in _sorted_edges(graph, node_id):
            if dependency not in graph:
                raise OrchestrationError(
                    "the node %r depends on %r, which the graph does not have: "
                    "no wave can be computed for an edge that leaves the graph"
                    % (node_id, dependency))
    return graph


def dependencies(graph, node_id):
    """The ids `node_id` waits for, sorted by id and deduplicated.

    Stage 1 keeps what the plan wrote — `("render", "index", "render")` is what
    a job file said, and losing it there would hide a fact about the file — but
    the order a dependency *forces* does not depend on how a plan happened to
    spell its edges: a repeat is one edge, and the ids come back sorted, so that
    every wave and every refusal downstream prints the same thing twice.
    """
    graph = _require_graph(graph)
    return tuple(_sorted_edges(graph, node_id))


def _ready(graph, node_id, placed):
    """Is every one of `node_id`'s dependencies already placed?

    Every one, and not the first one: a node released when its first dependency
    is done can start while the slowest edge it waits on is still working, which
    is the join of a diamond running beside the branch it exists to wait for.
    """
    for dependency in _sorted_edges(graph, node_id):
        if dependency not in placed:
            return False
    return True


def _sweep(graph):
    """Every node's wave, by sweeping: the nodes whose dependencies are all
    placed join the next wave.

    `graph` must already have an order — the sweep is not a cycle check, and it
    cannot be one: a sweep that leaves nodes unplaced knows that something is
    stuck and nothing more, not which ids form the loop. Every node is placed
    exactly once, in the wave it belongs to, and the ids inside a wave are the
    sorted ids the sweep walked.
    """
    levels = []
    placed = set()
    remaining = sorted(graph)
    while remaining:
        wave = tuple(node_id for node_id in remaining
                     if _ready(graph, node_id, placed))
        for node_id in wave:
            placed.add(node_id)
        levels.append(wave)
        remaining = [node_id for node_id in remaining if node_id not in placed]
    return tuple(levels)


def _cycle_path(ids):
    """The cycle's path, spelled the way the refusal spells it — `'index' ->
    'render' -> 'index'` — beginning at the smallest id on the cycle.

    A cycle has no first node, and the walk enters it wherever the graph's ids
    let it: reporting the walk's entry would make the message a function of how
    the plan was written. Beginning at the smallest id makes it a function of
    the cycle, and closing the path on that id makes it a loop a reader can
    follow edge by edge.
    """
    body = list(ids)
    first = min(body)
    at = body.index(first)
    return " -> ".join("'%s'" % node_id
                       for node_id in body[at:] + body[:at] + [first])


def _cycle(graph):
    """The path of the first cycle a walk of the graph closes, or `""`.

    The walk is depth first and iterative: it starts at the smallest id it has
    not finished with, and it takes every node's dependencies through
    `_sorted_edges`, so which cycle is reported — and the ids on it — are a
    function of the graph and not of the order a plan happened to write its keys
    or its edges in. `graph` must have passed `_require_graph` and
    `_require_edges`.
    """
    placed = set()
    for start in sorted(graph):
        if start in placed:
            continue
        path = [start]
        at = {start: 0}
        frames = [[start, _sorted_edges(graph, start)]]
        while frames:
            node_id, remaining = frames[-1]
            if remaining:
                dependency = remaining.pop(0)
                if dependency in placed:
                    continue
                if dependency in at:
                    return _cycle_path(path[at[dependency]:])
                at[dependency] = len(path)
                path.append(dependency)
                frames.append([dependency, _sorted_edges(graph, dependency)])
                continue
            placed.add(node_id)
            path.pop()
            del at[node_id]
            frames.pop()
    return ""


def _require_order(graph):
    """The graph must have an order: a cycle makes every node on it wait for
    something that is waiting for it, so none of them can ever start.

    The refusal names the cycle's path, because that is the one thing a reader
    cannot reconstruct: the nodes of a cycle stay pending together forever, and
    "the graph has no order", or a count of the waves a sweep could place,
    tells them nothing about which edge to cut.
    """
    cycle = _cycle(graph)
    if cycle:
        raise OrchestrationError(
            "the graph has no order: the cycle %s closes back on itself, so no "
            "node on it can ever start" % (cycle,))


def waves(graph):
    """The graph's levels: `waves(graph)[K]` is the nodes of wave `K + 1`.

    Every node in wave one waits for nothing; a node waits for every node of an
    earlier wave it depends on, and for no node of its own; the ids inside a
    wave come back sorted. A node's wave is one more than the *max* of its
    dependencies' waves, not one more than the first of them:
    `graphs['diamond']`'s two branches share wave two, and `join`, which waits
    for both, belongs to wave three although each of its dependencies sits in
    wave two. Placing a node in its first dependency's wave puts it beside a
    branch that may be the short one, and a scheduler that trusted the wave
    would run the join while the slow branch is still working.

    A graph with no order is refused here, naming the cycle's path, and never
    answered with the waves the sweep could place: a partial wave list is a plan
    that quietly loses the nodes nobody can run.
    """
    graph = _require_edges(_require_graph(graph))
    _require_order(graph)
    return _sweep(graph)


def _require_proposed(depends, what):
    """The dependency tuple a caller is about to give a node: a sequence of ids,
    never a bare string.

    A string is the tempting argument and the wrong one: walked as a sequence
    `"plan"` is 'p', 'l', 'a', 'n' — four dependencies the graph does not have,
    and a refusal about four ids nobody wrote instead of about the string the
    caller passed.
    """
    if isinstance(depends, (str, bytes)) or not isinstance(depends, Sequence):
        raise OrchestrationError("%s must be a sequence of ids, got %r"
                                 % (what, depends))
    ids = []
    for index, node_id in enumerate(depends):
        if not isinstance(node_id, str) or not node_id.strip():
            raise OrchestrationError("%s[%d] must be a str id, got %r"
                                     % (what, index, node_id))
        ids.append(node_id)
    return tuple(ids)


def would_cycle(graph, node_id, depends):
    """Would `node_id`, given the dependencies `depends`, be able to reach
    itself? `depends` is the whole tuple the edit hands the node, not the edges
    it adds.

    The test walks the graph's own edges out of every proposed dependency and
    asks whether any walk arrives back at `node_id`: a node that can reach
    itself is waiting for something that waits for it, and can never start. A
    self-dependency is a cycle of length one and answers `True` — a graph handed
    back with the node in its own `depends` is no more runnable for having been
    refused by a different stage's parser. The question is about the node being
    edited and not about the graph: a graph that already has a cycle somewhere
    else still answers about the edit, and the empty tuple — an edit that
    removes every edge — always answers `False`.

    A dependency the graph does not have is refused, naming it and the node the
    edit is for, because that edit could not be applied; a `depends` that is not
    a sequence of ids is refused the same way.
    """
    graph = _require_edges(_require_graph(graph))
    _edges(graph, node_id)
    proposed = _require_proposed(depends, "the dependencies of an edit to %r"
                                 % (node_id,))
    for dependency in proposed:
        if dependency not in graph:
            raise OrchestrationError(
                "the edit gives the node %r the dependency %r, which the graph "
                "does not have" % (node_id, dependency))
    seen = set()
    frontier = list(proposed)
    while frontier:
        current = frontier.pop()
        if current == node_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(_edges(graph, current))
    return False


def validate_order(graph):
    """The gate: a graph that has an order has nothing to say about it, and a
    graph that has none is refused, naming the cycle's path.

    A caller that wants the waves wants `waves`; this is the function that
    answers "which graph may be run at all", and it answers by not answering. It
    refuses a cycle, naming the path, a dependency the graph does not have, and
    a graph this stage cannot read — never a `KeyError`, and never a partial
    answer.
    """
    _require_order(_require_edges(_require_graph(graph)))
    return None
