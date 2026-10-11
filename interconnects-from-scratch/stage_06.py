"""Interconnects From Scratch — stage 6: All-gather and reduce-scatter, first class

All-gather and reduce-scatter are the two halves a ring all-reduce is made of
(stage 4), and this stage makes each of them a collective in its own right: one
plan, one price, one answer to check, with no all-reduce around them. Both walk
a ring of `N` ranks for `N - 1` steps, every rank passing one chunk to its
successor each step; they differ in what that pass *does* to the buffer.

DESIGN DECISION — all-gather and reduce-scatter are the same ring; are they each
other's inverse, and can one be implemented as the other read backwards?
Rejected: one function written as the other's inverse (the reduce-scatter's
transfers reversed to gather, or the all-gather's to scatter). The two are not
inverses in the plan: the reduce-scatter's transfers combine into the
destination (`op="reduce"`), so a chunk that passes a rank absorbs that rank's
contribution, while the all-gather's transfers copy (`op="send"`), leaving the
sender holding the chunk it forwarded. Reading the reduce-scatter backwards
re-reduces chunks that are already complete — every rank's data counted again
per hop — and the reversed direction touches the ranks in the wrong order, so
the buffer check fails while the byte count still looks symmetric. The cost of
the shortcut is a plan that moves the same volume and answers the wrong
question.

DESIGN DECISION — what does the last chunk of a reduce-scatter hold if the loop
stops one step early?
Rejected: running `N - 2` steps and calling the plan a reduce-scatter. In step
`k` rank `r` passes chunk `(r - k - 1) mod N` forward, so chunk `c` is complete
only after it has absorbed all `N` ranks; the final step is the one in which the
last contribution reaches rank `c`. Stopping one step early leaves chunk `c`
holding the combination of `N - 1` ranks — a buffer that has the right shape,
the right length and the wrong numbers — and it drops one step from the price,
which is exactly the failure the checks make visible: a plan that is one step
cheaper and silently short one rank's data.

DESIGN DECISION — what does a `chunks` smaller than `N` do to the schedule?
Rejected: believing that fewer, larger chunks shorten the ring. The schedule is
still `N - 1` steps — a chunk cannot cross the ring in fewer hops than the ring
has — and in each step only `chunks` of the `N` ranks have a chunk left to send,
so `N - chunks` of them idle: `chunks` transfers per step instead of `N`. The
chunk in flight is `length / chunks` elements instead of `length / N`, so each
step's byte time is that many times larger while the same `N - 1` latencies are
paid, and because the window of `chunks` senders slides around the ring, a
rank's traffic is no longer the uniform `2S(N - 1)/N` of `chunks = N` — it
depends on how often the window happens to include that rank. Fewer chunks buys
a shallower pipeline over a larger transfer, never a shorter schedule.

DESIGN DECISION — why is an `algorithm` other than `"ring"` refused, rather than
silently treating every name as the ring?
Rejected: accepting any algorithm string and answering the ring. The surface
names the algorithm because a caller is choosing between plans — the whole point
of the later stages is that one name is cheaper than another for a given size —
so a call that asks for a tree and quietly gets `N - 1` ring steps has been lied
to about the price it read. A refusal that names the offending algorithm is the
only answer that keeps the name meaningful, and it is `fabric.FabricError`, the
course's own error type.

DESIGN DECISION — may a step of the all-gather forward a chunk the same step
writes?
Rejected: a step in which a rank forwards the chunk arriving beside it. The
executor reads every buffer as it was at the *start* of its step, so a forward
of a chunk that has not arrived yet carries the pre-arrival value, and the last
chunks of the ring silently vanish while the plan still has the right number of
transfers and steps. Each step must forward the chunk received in the previous
step (in the first step, the chunk the rank owns), which is what makes the
gather a pipeline rather than a race.

TODO: implement `all_gather` and `reduce_scatter`.
"""


def all_gather(topology, length, *, algorithm="ring", chunks=None):
    """Every rank ends holding every rank's piece.

    A `fabric.Plan` over `fabric.buffers(len(topology.ranks), length)`. The
    buffer is cut into `chunks` equal chunks (`chunks` defaults to one chunk per
    rank); the piece rank `r` contributes is chunk `r` of the buffer it was
    handed. The plan is `N - 1` steps, each rank forwarding one chunk to its
    successor with `op="send"`, and running it leaves every rank holding every
    rank's piece. An `algorithm` other than `"ring"`, a `chunks` that does not
    divide `length`, a `chunks` smaller than two, or a `chunks` larger than the
    rank count is a `fabric.FabricError`.
    """
    raise NotImplementedError("stage 6: implement all_gather()")


def reduce_scatter(topology, length, *, algorithm="ring", chunks=None, op="reduce"):
    """Rank `r` ends holding the fully reduced chunk `r`, and only that chunk.

    The mirror plan: a `fabric.Plan` over
    `fabric.buffers(len(topology.ranks), length)`, cut into `chunks` equal
    chunks (`chunks` defaults to one chunk per rank), in which each of the
    `N - 1` steps has every rank combine one chunk forward with `op="reduce"`.
    Running it leaves chunk `c` fully reduced on rank `c` and every other chunk
    on that rank only partial — nothing else is reduced. `op` names the
    combining operation the caller runs with; like stage 4's all-reduce, the plan
    does not carry it, so an `op` that is neither a combining op nor the label
    `"reduce"` is refused. The same three `chunks` refusals as `all_gather`
    apply, and so does the `algorithm` refusal.
    """
    raise NotImplementedError("stage 6: implement reduce_scatter()")
