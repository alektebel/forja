"""Interconnects From Scratch — stage 4: All-reduce, ring (implementation).

The reasoning behind the pipelined ring lives in the template's docstring
(`stage_04.py`); this file is only the body. Nothing here is measured: a plan is
built as data, and every number in it is an `int`.

The one idea: a ring of `N` ranks, the buffer cut into `chunks` equal chunks.
The reduce-scatter runs `N - 1` steps, each rank sending one chunk forward and
combining what arrives into the chunk it already holds; after them chunk `c`
sits fully reduced on rank `c`. The all-gather runs `N - 1` more steps, each
rank copying forward the chunk it just received, until every rank holds every
chunk. `chunks = N` is one chunk per rank per step, the pipelined ring.
"""

import fabric


def _chunking(topology, length, chunks):
    """The chunk count, and the number of elements in each chunk, or a refusal.

    `chunks` defaults to one chunk per rank (`len(topology.ranks)`). The buffer
    is cut into that many equal chunks, so `chunks` must divide `length`, be at
    least two (a ring with one chunk has nothing to scatter), and not exceed the
    rank count (the ring has one chunk slot per rank, one transfer per rank per
    step).
    """
    ranks = len(topology.ranks)
    count = ranks if chunks is None else chunks
    if count < 2:
        raise fabric.FabricError(
            "chunks is %r: a ring needs at least two chunks" % (count,))
    if count > ranks:
        raise fabric.FabricError(
            "chunks is %r for %d ranks: the ring has one chunk slot per rank"
            % (count, ranks))
    if length % count != 0:
        raise fabric.FabricError(
            "length %r is not a multiple of chunks %r: the chunks are equal"
            % (length, count))
    return count, length // count


def _reduce_scatter_transfers(topology, length, chunks, first_step, op):
    """The `N - 1` reduce-scatter steps, every rank sending one slice of `op`.

    In step `k` (the `(k + 1)`-th) rank `r` sends chunk `(r - k - 1) mod N` to
    rank `(r + 1) mod N`; the slice it sends is the one that rank `r - k - 1`
    started with, now carrying the combination of the ranks it has passed. After
    `N - 1` steps chunk `c` holds the combination of all `N` ranks' chunk `c`,
    and it sits on rank `c`.
    """
    count, size = _chunking(topology, length, chunks)
    ranks = topology.ranks
    total = len(ranks)
    transfers = []
    for step in range(total - 1):
        for index in range(total):
            slot = (index - step - 1) % total
            if slot >= count:
                continue
            transfers.append(fabric.send(
                ranks[index], ranks[(index + 1) % total], size,
                first_step + step, offset=slot * size, op=op))
    return transfers


def _all_gather_transfers(topology, length, chunks, after):
    """The `N - 1` all-gather steps, every rank forwarding the slice it holds.

    In step `t` rank `r` forwards chunk `(r - t) mod N` to rank `(r + 1) mod N`
    with `op="send"`: at `t = 0` that is the chunk `r` owns (just reduced), and
    at later steps it is the chunk rank `r` received in step `t - 1`. The copy
    leaves the sender holding it too, so chunk `c` walks the whole ring and
    every rank ends with every chunk.
    """
    count, size = _chunking(topology, length, chunks)
    ranks = topology.ranks
    total = len(ranks)
    transfers = []
    for step in range(total - 1):
        for index in range(total):
            slot = (index - step) % total
            if slot >= count:
                continue
            transfers.append(fabric.send(
                ranks[index], ranks[(index + 1) % total], size,
                after + step, offset=slot * size, op="send"))
    return transfers


def reduce_scatter_ring(topology, length, *, chunks=None):
    """Reduce-scatter over a ring: rank `r` ends holding the reduced chunk `r`.

    The buffer is cut into `chunks` equal chunks of `length // chunks`
    elements (`chunks` defaults to one chunk per rank). The plan is `N - 1`
    steps; running it leaves chunk `c` fully reduced on rank `c` and every
    other rank's other chunks only partial. A `chunks` that does not divide
    `length`, is smaller than two, or exceeds the rank count is a
    `fabric.FabricError`.
    """
    count, size = _chunking(topology, length, chunks)
    transfers = _reduce_scatter_transfers(topology, length, chunks, 0, "reduce")
    return fabric.Plan(
        transfers=tuple(transfers),
        name="reduce_scatter_ring (chunks=%d, size=%d)" % (count, size))


def all_gather_ring(topology, length, *, chunks=None):
    """All-gather over a ring: every rank ends holding every chunk.

    The mirror of `reduce_scatter_ring`: `N - 1` further steps in which each
    rank copies forward, with `op="send"`, the chunk it received in the step
    before (at the first step, the chunk it owns). Its input is the buffer a
    reduce-scatter leaves — one reduced chunk per rank — so running the two in
    sequence is an all-reduce.
    """
    count, size = _chunking(topology, length, chunks)
    transfers = _all_gather_transfers(topology, length, chunks, 0)
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_gather_ring (chunks=%d, size=%d)" % (count, size))


def all_reduce_ring(topology, length, *, chunks=None, op="reduce"):
    """Every rank ends holding `fabric.reference(buffers, op=...)`.

    The reduce-scatter and the all-gather in one plan: `N - 1` combining steps
    (steps `0 .. N - 2`) followed by `N - 1` copying steps (steps
    `N - 1 .. 2(N - 1) - 1`), so `2(N - 1)` steps in all, each rank sending and
    receiving `2 * length * (N - 1) // N` elements.

    `op` names the combining operation the caller will run the plan with
    (`"sum"`, `"min"`, `"max"`, or the collective's own label `"reduce"`, the
    default). A plan does not carry the combining operation — it applies it at
    `fabric.run` — so `op` selects nothing in the plan; it is checked and named,
    not written into a transfer.
    """
    if op not in fabric.OPS and op != "reduce":
        raise fabric.FabricError(
            "op %r is not one of the combining ops %r, nor 'reduce'"
            % (op, fabric.OPS))
    count, size = _chunking(topology, length, chunks)
    total = len(topology.ranks)
    halves = _reduce_scatter_transfers(topology, length, chunks, 0, "reduce")
    halves += _all_gather_transfers(topology, length, chunks, total - 1)
    return fabric.Plan(
        transfers=tuple(halves),
        name="all_reduce_ring (chunks=%d, size=%d, op=%s)" % (count, size, op))
