"""Interconnects From Scratch — stage 3: Reduce, and where the accumulator lives

A reduce takes `N` buffers of the same length and leaves their element-wise
combination on one rank, the root. Everything below this stage is provided:
`fabric.Transfer` says whether a message combines into its destination
(`op="reduce"`) or copies over it (`op="send"`), `fabric.run` applies a plan to
buffers and returns them, and `fabric.reference` is the answer the combination
must equal. What is not provided is the plan, and a plan is a placement: who
sends what to whom, in which step, and — the question this stage is named after
— where the accumulator that the messages combine into actually lives.

The accumulator is not a variable in this course; it is *bytes in a buffer*.
That is the whole difficulty. A rank can only receive a combination into its own
buffer, and a rank can only send what is in its buffer, so wherever the partial
sum sits is a rank whose own data is on top of it, and moving it forward means
that rank sending the buffer it has just been given. The two plans below walk
the accumulator through the fabric — around the ring for one, up the levels of
a tree for the other — and they are correct when the root ends holding
`fabric.reference` under the caller's `op`, and when every rank the accumulator
passed through holds the partial sum it relayed forward.

DESIGN DECISION — why does the accumulator travel the ring, combining into each
relay's own buffer, instead of every rank sending its buffer straight to the
root?
    The straight plan is a star gather: every rank but the root sends its whole
    buffer to the root with `op="reduce"`, one message per step, and the root
    does all the combining. It is simple and it is legal, and its cost is
    exactly what the ring exists to avoid: *hops*. A star message from a rank
    `d` hops away pays `d` hops, so on `ring(4)` the star's three messages cost
    `21 + 42 + 21 = 84` ticks while the chain of three one-hop messages costs
    `21 + 21 + 21 = 63` — the star re-crosses links that the ring's own route
    carries the accumulator over once, and the further a rank is, the worse it
    gets. The star also hides the accumulator: the root is the only rank whose
    buffer changes, so nothing can be seen travelling, and the topology stops
    mattering. The ring's advantage is precisely that every message is one hop.

DESIGN DECISION — why does every hop combine (`op="reduce"`) rather than copy
the buffer onward (`op="send"`)?
    Copying looks like the obvious way to relay: take the buffer you received
    and hand it to the next rank. Its cost is that `send` *overwrites* the slice
    it lands in, so the moment the accumulator reaches a rank, that rank's own
    contribution is gone — every hop discards the data it lands on, and the
    root ends holding the last source's buffer, not the combination of every
    rank's. The op is part of the plan's meaning, and it is the only thing that
    makes a relay a *combine*; the fold cannot be left to the routing.

DESIGN DECISION — why must a rank forward the accumulator in a step *after* the
one it receives it in, instead of forwarding it in the same step?
    Pipelining the chain looks free: put every hop in one step and the whole
    ring is traversed at once. Its cost is that `fabric.run` applies a step
    *simultaneously* — every transfer reads the buffers as they were at the
    step's start — so a relay's send carries the value it held before its own
    combine arrived, and the bytes it has just received never move. On
    `ring(4)`, the one-step chain answers the root with `(3, 6)`, the sum of two
    buffers, instead of `(10, 20)`: the plan does not fail, it silently loses
    exactly the ranks it combined and did not forward, and the answer looks
    like an answer. The step boundary is the accumulator's boundary, and it is
    the only place a plan can get the order of "receive, then send" right.

DESIGN DECISION — why does the tree combine level by level, deepest first, into
each parent's own buffer, instead of placing every level in one step?
    A parent that sends in the step its children's combines arrive forwards the
    value it held *before* its subtree landed in it. Its cost is the same
    silent loss as the pipelined chain, with a subtree instead of a rank: on
    `tree(4)` a root that receives `r1` and `r2` while `r1` is still being
    combined with `r3` answers `6 * (j+1)` — `r3`'s bytes reached `r1` and went
    nowhere — instead of the `10 * (j+1)` of every rank. The level order is the
    dependency a tree carries written down: a rank's buffer is only worth
    forwarding once every child of its subtree has sent, which is why the
    deepest level goes first and a level that overlaps a parent's route on a
    fabric that is not a tree waits for the next step.

DESIGN DECISION — why is the root's answer the element-wise combination instead
of the mean, the combination divided by `N`?
    Averaging inside the collective is the classic confusion: the same plan,
    the same bytes, one division, and a number that looks like the answer. Its
    cost is that a transfer cannot scale — it combines a slice into a slice, so
    a mean is a rewrite of every element of the root's buffer, a second pass the
    plan does not describe and the cost model does not price — and that it makes
    the collective wrong for everything that asked for a *sum*: a gradient, a
    count, an error are all reduced, not averaged, and a caller who wants the
    mean is the one who divides, once, after the reduce. The contract is the
    element-wise combination, which is what `fabric.reference` answers.

The two plans differ only in the shape the accumulator walks: a ring's chain of
one-hop hops, and a tree's levels from the deepest leaves up. Both end with the
combination on the root.

TODO: implement `reduce_ring` and `reduce_tree`.
"""


def reduce_ring(topology, root, length):
    """The ring reduce: the accumulator walks the ring, one hop per step.

    Returns a `fabric.Plan` over `fabric.buffers(len(topology.ranks), length)`
    whose execution leaves the element-wise combination of every rank's buffer
    on `root`, under whatever `op` the caller hands `fabric.run`. Step `k` of
    the `N-1` steps carries the rank `k + 1` places before the root in the
    ring's order one more place back, `op="reduce"`: the accumulator travels
    through the buffers of `root-1, root-2, …` (rank indices around the ring),
    each rank it passes through ends holding the partial sum it relayed, and the
    last hop is the one that lands the combination on the root. Every step
    carries one hop.

    Refuses a `root` that is not a rank, a `length` below one, and a rank with
    no route to the root, with `fabric.FabricError`.
    """
    raise NotImplementedError("stage 3: implement reduce_ring()")


def reduce_tree(topology, root, length):
    """The tree reduce: level by level, deepest first, each rank into its parent.

    Returns a `fabric.Plan` with the same contract as `reduce_ring`. Every rank
    whose children have all sent combines its own buffer into its parent with
    `op="reduce"`, and the deepest level is placed first, so a parent is never
    forwarding in the step its children arrive in. On `tree(4)` that is two
    steps: `r3 -> r1`, then `r1 -> r0` and `r2 -> r0` together.

    Refuses a `root` that is not a rank, a `length` below one, and a rank with
    no route to the root, with `fabric.FabricError`.
    """
    raise NotImplementedError("stage 3: implement reduce_tree()")
