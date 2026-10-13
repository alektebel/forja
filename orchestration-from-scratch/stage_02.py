"""Orchestration From Scratch — stage 2: The order a dependency forces.

Stage 1 hands this stage a validated graph; this stage hands stages 3 and 9 the
order a graph has: which nodes may run together, which must wait for which, and
which graph may not be run at all because the waiting has no end. The records
say what a node waits for; this stage turns those edges into levels, and refuses
the one graph whose levels do not exist.

DESIGN DECISION — why is a node's wave one more than the *max* of its
dependencies' waves, and not one more than its first?
    Because a node waits for *every* dependency, and a wave is the earliest tick
    at which a node could be ready. `graphs['diamond']` is the whole case:
    `render` costs five ticks and `index` three, both depend on `plan`, and the
    join depends on both. Both branches belong to wave two — they may run
    together, and which of them finishes first is a runtime fact this stage must
    not bake in — and the join belongs to wave three. A rule that took the first
    dependency's wave would put the join in wave two whenever the plan happened
    to spell the faster branch first, and a scheduler reading the levels would
    then start the join beside the branch it exists to wait for: a fast node
    waiting on a slow sibling in the same wave, the failure this course opens
    with.

DESIGN DECISION — why does a cycle have to be *named* instead of detected by
counting waves?
    Because "the sweep could not place everything" is the only thing a sweep
    knows. It can say that some nodes are stuck; it cannot say which ids form
    the loop, and a refusal that says "this graph has no order" or reports the
    number of waves it managed sends a reader back to bisecting a job file by
    hand. A cycle is a path of edges: it can be found by walking edges, and the
    walk can hand back the path — `'index' -> 'render' -> 'index'` — which is
    the one fact that tells a reader which edge to cut. A detector that counts
    waves is also a detector that has to *run* the schedule it is refusing; a
    walk of the graph needs nothing but the graph.

DESIGN DECISION — why does `waves` refuse a graph with no order instead of
answering with the waves it could place?
    Because the answer would be a schedule that silently loses nodes. A caller
    handed the waves `[("plan",), ("render", "index")]` of a graph with a cycle
    two levels down would dispatch the nodes it has and then wait forever for
    consumers that were never in the list — and stage 3's `runnable` would
    report the cyclic nodes as `pending` on every tick with nothing to explain
    it. The refusal belongs where the levels are produced, because that is where
    the graph is looked at as a whole; `waves` validates and then sweeps, and
    the sweep is allowed to assume an order exists.

DESIGN DECISION — why does `dependencies` sort and deduplicate what stage 1
kept?
    Because the plan's spelling and the edge set are two different facts. Stage 1
    keeps exactly what the file said — `("render", "index", "render")` — because
    that is a fact about the file, and a parser that normalised it would hide a
    plan somebody should probably fix. The *order a dependency forces* is a fact
    about the graph: `render` appearing twice is one edge, and which edge a walk
    reaches first cannot depend on how a plan's keys or edges happened to be
    written, or two runs of the same graph would print two different waves and
    two different cycle paths. So this stage sorts by id and drops the repeats,
    and the one place the raw spelling still matters — the record — keeps it.

DESIGN DECISION — why does this stage look for cycles at all, when stage 1
already refuses a node that depends on itself?
    Because a self-dependency is the shortest cycle and not the only one.
    `graphs['cycles']` is the counter-example the course keeps: every id in it
    exists, every id is spelled right, no node depends on itself, stage 1 parses
    it without complaint — and it has no order, because `render` waits for
    `index` and `index` waits for `render`. A stage that trusted the parser's
    refusal of self-dependencies would hand a scheduler a graph whose two nodes
    are `pending` on every tick, and the failure would look like a hung run
    rather than a broken plan. The length of a cycle is not a property a plan
    can be assumed to respect.

DESIGN DECISION — why is `would_cycle` a question about the node, and about the
whole new tuple rather than the added edges?
    Because the caller is holding an edit and asking whether it can be made.
    "Would `node_id`, with these dependencies, be able to reach itself?" is
    answerable by walking the graph's own edges out of the proposed ones, and it
    is a different question from "does this graph contain a cycle anywhere": a
    graph can already be broken in one component while the edit concerns another,
    and a test that answered the larger question would refuse every edit to a
    graph somebody is trying to repair. The proposed tuple is the whole tuple
    for the same reason — it is what the node will have, so an edit that removes
    edges is tested as removing them, and an empty tuple can never cycle. The
    answer is `True` for a node that would wait for itself, because a cycle of
    length one is still a cycle, whatever a parser does with it.

TODO: implement `dependencies`, `waves`, `would_cycle` and `validate_order`.
"""

from collections.abc import Mapping, Sequence

from stage_01 import OrchestrationError, Subtask


def dependencies(graph, node_id):
    """The ids `node_id` waits for, sorted by id and deduplicated."""
    raise NotImplementedError("stage 2: implement dependencies()")


def waves(graph):
    """The graph's levels: `waves(graph)[K]` is the nodes of wave `K + 1`."""
    raise NotImplementedError("stage 2: implement waves()")


def would_cycle(graph, node_id, depends):
    """Would `node_id`, given the dependencies `depends`, reach itself?"""
    raise NotImplementedError("stage 2: implement would_cycle()")


def validate_order(graph):
    """Refuse a graph with no order, naming the cycle's path."""
    raise NotImplementedError("stage 2: implement validate_order()")
