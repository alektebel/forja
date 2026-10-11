"""Interconnects From Scratch — stage 4: All-reduce, ring

Every rank holds a buffer of `length` elements and every rank must end holding
the element-wise combination of all of them. The ring does it in two halves: a
reduce-scatter that leaves rank `r` owning the fully reduced chunk `r`, then an
all-gather that hands every chunk to every rank.

DESIGN DECISION — one chunk per step, or the whole buffer per step?
Rejected: every rank sends its whole buffer to its neighbour each step. That is
still `N - 1` steps, and it still reduces, but every transfer is `S` elements
instead of `S / N`, so a step's cost is `N` times the byte time and each rank
handles `2S(N - 1)` elements instead of `2S(N - 1) / N`. Chunking is what makes
the ring bandwidth-optimal; the whole buffer per step is the stage's first
mistake.

DESIGN DECISION — `chunks=None` means one chunk per rank, or one chunk?
Rejected: `chunks=None` meaning a single chunk of the whole buffer. Then the
ring degenerates to `N - 1` whole-buffer hops, which is exactly the mistake
above, and the default would be the one setting that cannot pipeline. `chunks`
defaults to `len(topology.ranks)`, so the default is one chunk in flight per
rank per step and `chunks=N` is what "the ring" means.

DESIGN DECISION — who sends which chunk in which step?
Rejected: each rank sends the chunk it owns, chunk `r`, every step. Then chunk
`r` is copied to the same neighbour `N - 1` times and never accumulates: no
chunk ever sees the other `N - 1` ranks' contributions, so the answer is wrong.
Rejected too: rank `r` sends chunk `r - k` for step `k` yet an implementation
where rank `r` ends holding some other rank's chunk. In step `k` of
reduce-scatter rank `r` must send the slice that is one step behind it in the
chain, `chunk (r - k - 1) mod N`, so that after `N - 1` steps chunk `c` is
complete and the rank holding it is exactly rank `c`.

DESIGN DECISION — why are the two halves not each other's inverse?
Rejected: implementing all-gather as the reduce-scatter plan with the direction
reversed (or vice versa). The halves move the same volume but do different work:
reduce-scatter combines with `op="reduce"` into the destination, all-gather
copies with `op="send"`. Reversing the reduce-scatter's transfers would
re-reduce chunks that are already reduced, double-counting every rank's data,
and would leave ranks untouched by the reversed direction without the chunks
they never received. Byte-for-byte the traffic looks symmetric; the buffers are
not.

DESIGN DECISION — may a gather step read what another rank writes in it?
Rejected: a gather step in which a rank forwards a chunk written in the same
step. The executor reads every buffer as it was at the *start* of its step, so
the forward would carry the pre-arrival value and the last ranks' chunks would
silently vanish. Each gather step must forward the chunk received in the
previous step, never one arriving beside it.

TODO: implement `reduce_scatter_ring`, `all_gather_ring` and `all_reduce_ring`.
"""


def reduce_scatter_ring(topology, length, *, chunks=None):
    """Reduce-scatter over a ring: rank `r` ends holding the reduced chunk `r`.

    The buffer is cut into `chunks` equal chunks of `length // chunks` elements
    (`chunks` defaults to one chunk per rank). The plan is `N - 1` steps, each
    rank sending one chunk forward with `op="reduce"`; running it leaves chunk
    `c` fully reduced on rank `c`, and every other chunk on that rank partial.
    A `chunks` that does not divide `length`, is smaller than two, or exceeds
    the rank count is a `fabric.FabricError`.
    """
    raise NotImplementedError("stage 4: implement reduce_scatter_ring()")


def all_gather_ring(topology, length, *, chunks=None):
    """All-gather over a ring: every rank ends holding every chunk.

    The mirror of `reduce_scatter_ring`: `N - 1` further steps in which each
    rank copies forward, with `op="send"`, the chunk it received in the step
    before (at the first step, the chunk it owns). Run after a reduce-scatter
    it is the all-gather half of an all-reduce; run alone it gathers whatever
    one-reduced-chunk-per-rank buffer it is handed.
    """
    raise NotImplementedError("stage 4: implement all_gather_ring()")


def all_reduce_ring(topology, length, *, chunks=None, op="reduce"):
    """The reduce-scatter and the all-gather in one plan.

    `2(N - 1)` steps: `N - 1` combining steps, then `N - 1` copying steps, so
    that every rank ends holding `fabric.reference(buffers)`. On a uniform ring
    with `chunks = N`, each rank sends and receives `2 * length * (N - 1) // N`
    elements. `op` names the combining operation the caller runs with
    (`"sum"`, `"min"`, `"max"`, or the collective's label `"reduce"`, the
    default); a plan does not carry it, so it selects nothing in the plan and is
    only checked, not written into a transfer.
    """
    raise NotImplementedError("stage 4: implement all_reduce_ring()")
