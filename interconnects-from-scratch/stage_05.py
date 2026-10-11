"""Interconnects From Scratch — stage 5: All-reduce, tree and doubling

An all-reduce makes every rank end holding the element-wise combination of every
rank's buffer. Stage 4 built it on a ring, pipelining equal chunks around the
cycle. This stage builds the other two shapes NCCL chooses between, and then
picks between all three by *counting ticks*, never by timing anything.

`all_reduce_tree` walks the tree the topology already has. `all_reduce_doubling`
is the butterfly. `all_reduce_best` builds every shape whose preconditions hold,
prices each with `stage_01.plan_ticks`, and returns the cheapest — the crossover
between them is a comparison of two plans, not a magic message size.

DESIGN DECISION — why reduce up the topology's own tree, and not a fixed binary
tree over the rank numbering? A tree built by rank id (`rank i hangs off
(i - 1) // 2`, the `fabric.tree` fixture) is cheap on *that* topology and wrong
on every other: on `switch(8, width=4)` its edges would route ranks 5..7 across
the slow spine when the fabric itself offers a shallow tree whose deepest leaf is
two hops from `r0`. The tree this stage reduces up is the shortest-route tree
`topology.path(rank, root)` already names, so its *levels* — and therefore its
step count, `2 * levels` — is a property of the fabric alone. The rejected
alternative costs more steps than the fabric needs, and the extra steps are
exactly the latency this algorithm exists to avoid.

DESIGN DECISION — why is a tree latency-cheap and bandwidth-dear, and not the
ring? The tree is `2 * levels` steps, i.e. `2 * log2(N)` on a balanced fabric,
against the ring's `2(N - 1)`: for a tiny message the tree sends a handful of
tiny messages and finishes. But every level moves the *whole* payload again —
`S(N - 1)` elements up and `S(N - 1)` down, about `2S(N - 1)` across the network
— while the ring moves only `2S(N - 1)/N` per rank, its chunks overlapping in the
pipeline. The rejected alternative, the ring, wins on bytes and loses on steps;
the tree wins on steps and loses on bytes. That is the whole crossover, and it
is why the choice cannot be made here without the numbers.

DESIGN DECISION — why does recursive doubling need `N` a power of two, and not
`(r + 2**k) mod N`? Step `k` pairs a rank with `r XOR 2**k`, whose partners are
distinct for `k = 0 .. log2(N) - 1` only when `N = 2**k`: the XOR of a rank index
with a power of two is a rank index precisely because the index has `log2(N)`
bits. The rejected alternative — `(r + 2**k) mod N`, which "works" for any `N` —
silently overlaps its partner sets on a non-power-of-two `N`, so some ranks
exchange twice and others never exchange at all, and the buffers are wrong even
though the step count looks right. Rather than ship a plan that only looks like a
butterfly, the stage refuses a non-power-of-two `N`, naming it.

DESIGN DECISION — why must every XOR partner be a direct neighbour, and not a
rank the router can still reach? A butterfly step is *one* exchange in *one*
step, so each pair's message must use a directed link no other pair's message
uses. A partner several hops away routes through the same inner links as its
neighbours' routes, so two transfers in one step share a directed link and the
plan is not one the fabric can run — `ring(8)` is exactly this, rank `r0` and
rank `r2` two hops apart. The rejected alternative, letting the router patch the
difference with a multi-hop transfer, either hands back a plan the executor
refuses or quietly stops being `log2(N)` steps. The stage refuses such a
topology, naming the pair and its hop count.

DESIGN DECISION — why does `all_reduce_best` compare ticks instead of a
hard-coded size? A rule like "messages under 4096 elements take the tree" bakes
in one fabric's bandwidth and one fabric's latency. On a ring fabric the ring is
bandwidth-optimal and eventually wins; on a switched fabric the spine's twenty
ticks per hop make a different shape cheapest at a different size. The rejected
alternative — a threshold constant — picks the more expensive plan on any fabric
it was not tuned for. Comparing `stage_01.plan_ticks` for each shape makes the
crossover fall out of the two costs, and makes the picker correct on a fabric it
has never seen.

DESIGN DECISION — why move the whole buffer per tree transfer, and not chunks?
Chunking the tree would not shorten it: the tree's step count is set by `levels`,
not by the payload, and a node must hold its full accumulator before it can
combine a child's chunk into it. Cutting the buffer into chunks would only add
steps (one per chunk per level) for the same network bytes. The rejected
alternative — a chunked tree — costs more latency and saves nothing, so each
tree transfer carries all `length` elements, which is what makes the step count
`2 * levels` and the network bytes about `2S(N - 1)`.

TODO: implement `all_reduce_tree`, `all_reduce_doubling` and `all_reduce_best`.
"""


def all_reduce_tree(topology, length, *, op="reduce"):
    """Reduce to the root up the topology's own tree, then broadcast back down."""
    raise NotImplementedError("stage 5: implement all_reduce_tree()")


def all_reduce_doubling(topology, length, *, op="reduce"):
    """Recursive doubling: `log2(N)` steps, each rank reducing with `r XOR 2**k`.

    Needs `N` a power of two and every XOR partner a direct neighbour; a
    non-power-of-two `N` or a partner more than one hop away is refused.
    """
    raise NotImplementedError("stage 5: implement all_reduce_doubling()")


def all_reduce_best(topology, length, *, op="reduce"):
    """The cheapest of `("ring", "tree", "doubling")`, and its plan."""
    raise NotImplementedError("stage 5: implement all_reduce_best()")
