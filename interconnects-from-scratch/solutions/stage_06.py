"""Interconnects From Scratch — stage 6: All-gather and reduce-scatter, first class (implementation).

The reasoning behind the two collectives lives in the template's docstring
(`stage_06.py`); this file is only the body. Nothing here is measured: each
collective is a plan built as data, and every number in it is an `int`.

The one idea: all-gather and reduce-scatter are the same ring walked the same
way for the same `N - 1` steps, and they are still not each other's inverse.
Every rank passes one chunk to its successor each step; the all-gather copies
that chunk with `op="send"` (so the piece rank `r` contributes is chunk `r` of
the buffer it was handed), and the reduce-scatter combines it with
`op="reduce"` (so that rank `r` ends holding the fully reduced chunk `r`). The
all-gather is the reduce-scatter's mirror in *shape* and its opposite in *work*.
"""

import fabric


def _chunking(topology, length, chunks):
    """The chunk count, and the elements in each chunk, or a refusal.

    `chunks` defaults to one chunk per rank (`len(topology.ranks)`). The buffer
    is cut into that many equal chunks, so `chunks` must divide `length`, be at
    least two (a ring with one chunk has nothing to pass), and not exceed the
    rank count (the ring has one chunk slot per rank).
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


def _algorithm(algorithm):
    """The algorithm name, or a refusal that names the unsupported one.

    Only the ring is implemented here; a name that is not `"ring"` is refused
    rather than silently answered with the ring's plan, so that the price a
    caller reads is the price of the plan they asked for.
    """
    if algorithm != "ring":
        raise fabric.FabricError(
            "algorithm %r is not the ring: all_gather and reduce_scatter "
            "implement only 'ring'" % (algorithm,))
    return algorithm


def _all_gather_transfers(topology, length, chunks, op):
    """The `N - 1` all-gather steps, every rank forwarding the chunk it holds.

    In step `t` rank `r` forwards chunk `(r - t) mod N` to rank `(r + 1) mod N`
    with the given `op`. At `t = 0` that is the chunk `r` owns — the piece rank
    `r` contributes — and at later steps it is the chunk rank `r` received in
    step `t - 1`, never one arriving beside it. The copy leaves the sender
    holding the chunk too, so after `N - 1` steps every rank holds every chunk.
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
                step, offset=slot * size, op=op))
    return transfers


def _reduce_scatter_transfers(topology, length, chunks, op):
    """The `N - 1` reduce-scatter steps, every rank combining one chunk forward.

    In step `k` rank `r` sends chunk `(r - k - 1) mod N` to rank `(r + 1) mod N`
    with the given `op`; the slice it sends is the one that rank `r - k - 1`
    started with, now carrying the combination of the ranks it has passed. After
    `N - 1` steps chunk `c` holds the combination of all `N` ranks' chunk `c`,
    and it sits on rank `c`. One step short leaves whatever rank was behind it
    out of the sum.
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
                step, offset=slot * size, op=op))
    return transfers


def all_gather(topology, length, *, algorithm="ring", chunks=None):
    """Every rank ends holding every rank's piece.

    The buffer is cut into `chunks` equal chunks of `length // chunks` elements
    (`chunks` defaults to one chunk per rank); the piece rank `r` contributes is
    chunk `r` of the buffer it was handed. The plan is `N - 1` steps in which
    every rank forwards one chunk to its successor with `op="send"`. An
    `algorithm` other than `"ring"` is refused, naming it; so is a `chunks` that
    does not divide `length`, is smaller than two, or exceeds the rank count.
    """
    _algorithm(algorithm)
    count, size = _chunking(topology, length, chunks)
    transfers = _all_gather_transfers(topology, length, chunks, "send")
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_gather (chunks=%d, size=%d)" % (count, size))


def reduce_scatter(topology, length, *, algorithm="ring", chunks=None, op="reduce"):
    """Rank `r` ends holding the fully reduced chunk `r`, and nothing else.

    The buffer is cut into `chunks` equal chunks of `length // chunks` elements
    (`chunks` defaults to one chunk per rank). The plan is `N - 1` steps in
    which every rank combines one chunk forward with `op="reduce"`; running it
    leaves chunk `c` fully reduced on rank `c` and every other chunk on that
    rank only partial. `op` is the combining operation the caller runs with
    (`"sum"`, `"min"`, `"max"`, or the collective's label `"reduce"`, the
    default): a plan does not carry it, so it selects nothing and is only
    checked and named. The same `algorithm` and `chunks` refusals as
    `all_gather` apply.
    """
    if op not in fabric.OPS and op != "reduce":
        raise fabric.FabricError(
            "op %r is not one of the combining ops %r, nor 'reduce'"
            % (op, fabric.OPS))
    _algorithm(algorithm)
    count, size = _chunking(topology, length, chunks)
    transfers = _reduce_scatter_transfers(topology, length, chunks, "reduce")
    return fabric.Plan(
        transfers=tuple(transfers),
        name="reduce_scatter (chunks=%d, size=%d, op=%s)" % (count, size, op))
