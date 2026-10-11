"""Interconnects From Scratch — stage 7: All-to-all, even and uneven (implementation).

The reasoning behind the exchange lives in the template's docstring
(`stage_07.py`); this file is only the body. Nothing here is measured: the
collective is a plan built as data, and every number in it is an `int`.

The one idea: an all-to-all is a transpose that never moves a byte twice. Rank
`i`'s buffer is cut, in rank order, into the pieces it sends out; the plan
copies each piece once, and the destination stores the pieces it receives,
again in rank order. So rank `i` ends holding, for `j` in rank order, what rank
`j` sent it — and the piece a rank keeps never has to move, because it is
already in the slot it belongs in. The offset a piece is read from and written
back to is one number: the running sum of the counts the ranks before the sender
send that destination, so it is `splits`-shaped, never a per-pair product.
"""

import fabric


def _ranks(topology):
    """The rank count of the fabric the exchange runs on."""
    return len(topology.ranks)


def _check_splits(topology, splits):
    """The rank count, or a refusal naming the malformed `splits`.

    `splits` is a square table with one row and one column per rank:
    `splits[i][j]` is how many elements rank `i` sends rank `j`, and the
    diagonal `splits[i][i]` is the piece rank `i` keeps. A row or column count
    that disagrees with the fabric's, a count that is not an `int` (a `bool` is
    not one) and a negative count are refused, each naming the offender.
    """
    ranks = _ranks(topology)
    if len(splits) != ranks:
        raise fabric.FabricError(
            "splits has %d rows, but %s has %d ranks"
            % (len(splits), topology, ranks))
    for index, row in enumerate(splits):
        if len(row) != ranks:
            raise fabric.FabricError(
                "splits[%d] has %d columns, but %s has %d ranks"
                % (index, len(row), topology, ranks))
        for slot, count in enumerate(row):
            if isinstance(count, bool) or not isinstance(count, int):
                raise fabric.FabricError(
                    "splits[%d][%d] is %r, not an element count"
                    % (index, slot, count))
            if count < 0:
                raise fabric.FabricError(
                    "splits[%d][%d] is %r: a count is never negative"
                    % (index, slot, count))
    return ranks


def _recv_offset(splits, i, j):
    """Where rank `j`'s buffer keeps the block rank `i` sent it.

    The receiver lays its buffer out in rank order, so the block from rank `i`
    starts after every block the ranks before `i` sent it: the running sum of
    `splits[k][j]` for `k < i`. One number is the whole exchange — the sender
    reads its piece from it and the receiver writes it back to it — which is
    why nothing is copied twice and why the transpose falls out of the count.
    """
    return sum(splits[k][j] for k in range(i))


def _blocks(topology, splits):
    """Per rank, in rank order, the blocks its buffer ends holding.

    Each block is `(source rank, source offset, length)`: rank `j`'s buffer
    holds, one after another in rank order, the `splits[i][j]` elements rank `i`
    sent it — read from offset `_recv_offset(splits, i, j)` of rank `i` — so the
    j-th entry of the result is the j-th column of `splits`, top to bottom,
    minus its own cell: the diagonal is the slice rank `j` keeps, already in the
    slot the transpose wants it in, so it is never a block the exchange fills.
    Blocks of length zero are absent, nothing having moved, and every rank of
    the fabric appears even when it neither sends nor receives.
    """
    ranks = _check_splits(topology, splits)
    layout = []
    for j in range(ranks):
        blocks = []
        for i in range(ranks):
            if i == j:
                continue
            length = splits[i][j]
            if length:
                blocks.append((topology.ranks[i], _recv_offset(splits, i, j), length))
        layout.append(tuple(blocks))
    return tuple(layout)


def all_to_all(topology, splits):
    """One step in which every rank hands every other rank its own count.

    Rank `i` sends `splits[i][j]` elements to rank `j` for every `j`, and keeps
    `splits[i][i]`; the piece bound for rank `j` is read from offset
    `_recv_offset(splits, i, j)` of rank `i`'s buffer and written back to the
    same offset of rank `j`'s, so rank `i` ends holding, for `j` in rank order,
    what rank `j` sent it. Every pair that moves anything is one transfer in one
    step, the diagonal is not a transfer at all, and a fabric the one-step
    exchange cannot run on (a route that would carry two transfers the same way
    at once) is refused, naming the fabric and the collision rather than
    answered with a plan the executor would reject.
    """
    ranks = _check_splits(topology, splits)
    transfers = []
    for i in range(ranks):
        for j in range(ranks):
            if i == j:
                continue
            length = splits[i][j]
            if length == 0:
                continue
            transfers.append(fabric.send(
                topology.ranks[i], topology.ranks[j], length, 0,
                offset=_recv_offset(splits, i, j)))
    plan = fabric.Plan(
        transfers=tuple(transfers),
        name="all_to_all (%d ranks, %d transfers)" % (ranks, len(transfers)))
    problems = fabric.legality_problems(topology, plan)
    if problems:
        raise fabric.FabricError(
            "the one-step exchange cannot run on %s: %s"
            % (topology, "; ".join(problems)))
    return plan


def exchange_with(topology, splits):
    """The buffer every rank ends holding, as the blocks that fill it.

    A tuple in rank order; entry `j` is rank `rj`'s buffer, described as the
    blocks it ends holding — `(source rank, source offset, length)` each, in
    rank order — so a caller can read rank `j`'s answer out of any starting
    buffers, `fabric.run(all_to_all(topology, splits), buffers)` agreeing with
    it block for block, without the counts being spelled out again. The kept
    slice is not a block — it is already in the slot the transpose wants it in —
    and everything no block covers stays where it was. The same `splits`
    refusals as `all_to_all` apply.
    """
    return _blocks(topology, splits)
