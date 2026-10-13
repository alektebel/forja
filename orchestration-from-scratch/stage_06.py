"""Orchestration From Scratch — stage 6: One failure, and the rest of the graph.

The scheduler runs nodes; a worker eventually returns `failed`; and the question
this stage answers is what that one failure does to every other node. It hands
the loop two functions: the *prediction*, which nodes can no longer be computed
at all, and the *transition*, what the states are now. Nothing here runs a node,
asks a clock or touches a worker: a failure is data, and its damage is a function
of the graph.

DESIGN DECISION — why does a failure take down its transitive dependents, and
not the wave the failure happened to run in?
    Because a wave is a fact about the *schedule* and a dependency is a fact
    about the *data*. Stage 3 already established that a wave is not a unit of
    work: `graphs["diamond"]`'s `render` and `index` are in one wave, and a
    failure of `index` says nothing about `render`, which is a sibling and not a
    dependent — it still has to run. What the failure does say is that every
    node whose result is built from `index` — directly, and then everything
    downstream of that, however many levels deep — has nothing to compute from.
    A skip set that stops at the direct dependents loses the second level and
    every level after it, and each of those nodes gets dispatched against a
    dependency that never finished: a wrong answer that looks like progress.

DESIGN DECISION — why is a dependent that was already dispatched still skipped?
    Because "it was already dispatched" is a fact about the past and the skip is
    about the result. A node in the same tick as the failure, or one the
    scheduler had already sent to a worker, was computing an answer from a
    dependency that has since failed; keeping it `running` (or accepting its
    result as `ok`) means the graph's next node is built on the output of a node
    whose input never existed. So the cascade writes `skipped` over `pending`,
    `running` and `awaiting` alike, and the record shows the node was told to
    stop rather than quietly succeeding.

DESIGN DECISION — why does `skip_set` take no states, while `propagate` does?
    Because they are two different questions. `skip_set` is structural: "which
    nodes does this failure make impossible", a function of the graph alone, so
    a loop can ask it before anything has run and get the same answer. What
    state a node is in when the failure arrives is the second question, and
    `propagate` is where the state mapping is rebuilt. `propagate` also takes the
    *status* rather than assuming a failure, so there is one place in the loop
    that writes states and one cascade serving both a node that failed and a node
    that was skipped by policy — the two differ in the node's own state and not
    in what they do to the rest of the graph.

DESIGN DECISION — why does the cascade never overwrite a node that already
finished `ok`?
    Because a skip is a prediction and an `ok` is a fact. "This node will not
    run" cannot be written over a node that already produced an accepted result:
    the record already carries that result, the report recomputes it from the
    record, and a run that rewrites it loses work that happened — the same class
    of failure as accepting a result that never should have been computed.
    Finished is finished: `ok`, `failed` and `skipped` all keep the state they
    finished with, and the cascade only moves a node that has not landed.

DESIGN DECISION — why is the new mapping a fresh, id-sorted mapping of every
node, and why is a state for a node the graph does not have refused?
    Because the states are what the record and the report are recomputed from. A
    mapping whose key order follows whoever last edited the dict serialises
    differently for the same run, so the ids come back sorted, exactly as the
    graph's do. It covers every node of the graph — a caller that hands in a
    partial mapping means "nothing has happened to these nodes", and that is
    `pending`, never a missing key a later stage has to guess at. And a mapping
    that *names* an id the graph does not have, or gives a node a state that is
    not one of the six, is a typo: this course refuses a typo by naming it
    rather than letting it become a default nobody noticed.

TODO: implement `skip_set` and `propagate`.
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


def skip_set(graph, failed):
    """The transitive dependents of the nodes that failed, sorted."""
    raise NotImplementedError("stage 6: implement skip_set()")


def propagate(graph, states, node_id, status):
    """The states after `node_id` reaches `status`, the rest of the graph behind
    it."""
    raise NotImplementedError("stage 6: implement propagate()")
