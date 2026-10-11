"""Interconnects From Scratch — stage 7: All-to-all, even and uneven

Every stage so far has moved one rank's data to every other rank, or combined
every rank's data onto one. All-to-all is the collective where the *pattern*
itself is the data: rank `i` holds one piece for each rank `j`, and wants the
pieces everyone else cut for it. In the language of this course it is a
transpose — the table of counts turns ninety degrees — and it is the one
collective whose price depends on which cell of that table is big, because a
hot pair slows the whole step while the rest of the fabric waits.

The numbers are `splits`: `splits[i][j]` is how many elements rank `i` sends
rank `j`, and the diagonal `splits[i][i]` is what rank `i` keeps. The layout
this stage freezes is the receiver's: rank `j`'s buffer holds, one block after
another in rank order, the `splits[i][j]` elements rank `i` sent it, and its own
kept slice sits at index `j` of that same order, exactly where it already is. So
a block never changes its offset: the sender reads its piece from the offset the
receiver writes it to, and the offset of the block from rank `i` is the running
sum of what the ranks before `i` send rank `j`.

DESIGN DECISION — why is a block's offset the cumulative of what the destination
receives, rather than the cumulative of what each sender produces?
    Rejected: the produced-cumulative — rank `i`'s buffer cut into the pieces it
    sends, in destination order, each piece at the running sum of its own row.
    That is the obvious table-shaped answer, and it tiles the *sender* perfectly,
    which is why it looks right: every rank's outgoing blocks are disjoint. But
    the walls a receiver needs are the sum of what it receives, not the sum of
    what each sender sends, so on an even table — every pair exchanging the same
    count — every sender's window starts at the same offset of every receiver,
    all of them write the same slot, and the exchange keeps one sender's data and
    silently drops the rest. The received-cumulative is the one that tiles the
    receiver in rank order, so it is the one that makes the result a transpose.

DESIGN DECISION — why is the diagonal a kept slice and never a transfer?
    Rejected: emitting a transfer for every cell, including `splits[i][i]`.
    A rank sending to itself is not a message — nothing crosses a link, nothing
    costs a tick — and it is not even representable: `fabric.Plan` refuses a
    transfer whose source and destination are the same rank, so a plan built
    that way cannot exist, let alone run. The kept slice's whole point is that it
    is already in the slot the transpose wants it in, which is what lets a rank
    keep it without moving a byte. The mistake costs a plan that cannot be
    constructed; the refusal names the offender.

DESIGN DECISION — why is the whole table one step, and not one step per pair?
    Rejected: serialising the pairs — `N (N - 1)` steps, or one step per
    destination — so that each transfer is alone on the fabric. It is legal on
    every topology, which is its only virtue, and it is what a plan does when it
    confuses a *collective* with a *sequence of sends*: a step is what the fabric
    runs at once, and the price of the exchange is the slowest transfer in its
    one step, not the sum over a conversation. The cost of the mistake is a plan
    that is `N` times too expensive while moving exactly the same bytes, which is
    the difference this whole course is built to show.

DESIGN DECISION — why is a per-pair offset (`count * index`) the mistake this
stage is built to catch?
    Rejected: computing each block's offset from the pair alone — `i *
    splits[i][j]`, or `j * splits[i][j]`, or the size of the block itself. On an
    even table the first two agree with the cumulative and the bug hides
    completely, because every count is the same number; on a ragged table they
    do not, and every block after the first lands somewhere else. The buffer
    still has the right length, the right number of transfers and the right
    bytes moved — the shape is perfect and the numbers are wrong — which is
    exactly the failure a cost-only or shape-only check would wave through.

DESIGN DECISION — why does a rank that neither sends nor receives still appear
in the answer, and why must the last block be delivered?
    Rejected: dropping the empty rows and columns from the plan and the result,
    and stopping the loops one pair short because the last destination of the
    last sender looks like an edge. A rank with a zero row and a zero column is
    a rank that stayed put, not a rank that left: it has a place in the result,
    it is indexed by its rank id like every other, and nothing about it is a
    transfer. Its neighbour, the last block of the last sender, is the block a
    short loop loses: the receiver's tail then holds a stale copy of its own
    data, the transfer count is one short, and the buffers still have exactly
    the right length — the quietest way for a transpose to be one cell wrong.

DESIGN DECISION — why is an exchange that cannot run in one step refused rather
than returned?
    Rejected: handing back the plan anyway, or building it and running it with
    `check=False`. On a fabric where a route between two ranks traverses links
    other transfers also need — a ring, where a distant pair's route crosses the
    near pair's — two transfers in one step would share a directed link, which is
    exactly what a step forbids; the executor refuses such a plan, and papering
    over it produces a plan whose price is fiction. Staging the transfers over
    more steps is a different plan at a different price than the caller asked
    for, so the honest answer is a refusal that names the fabric and the
    collision.

Every count in `splits` is an element count, so every offset, length and tick
this stage computes is an `int`; a table whose rows and columns do not match the
fabric's, a count that is not an `int`, a negative count and a plan the fabric
cannot run are all `fabric.FabricError`s.

TODO: implement `all_to_all` and `exchange_with`.
"""


def all_to_all(topology, splits):
    """One step in which every rank hands every other rank its own count.

    `splits` is a table with one row and one column per rank: `splits[i][j]` is
    how many elements rank `i` sends rank `j`, and `splits[i][i]` is the piece
    rank `i` keeps. The answer is a `fabric.Plan` whose every transfer is in
    step `0`: one transfer for each pair `i != j` with a non-zero count, from
    rank `i` to rank `j`, of `splits[i][j]` elements, read from and written to
    offset `sum(splits[k][j] for k in range(i))` — the running sum of what the
    ranks before `i` send rank `j`. So rank `j` ends holding, for `i` in rank
    order, the `splits[i][j]` elements rank `i` sent it, with its own kept slice
    at index `j` of that order, untouched: the table has been transposed. A
    `len(splits)`, or a row, that disagrees with the rank count, a count that is
    not an `int`, a negative count, and a fabric the one-step exchange cannot
    run on (two transfers sharing a directed link) are `fabric.FabricError`s,
    each naming the offender.
    """
    raise NotImplementedError("stage 7: implement all_to_all()")


def exchange_with(topology, splits):
    """The buffer every rank ends holding, described block by block.

    A tuple in rank order: entry `j` is rank `rj`'s buffer, given as the blocks
    that fill it — `(source rank, source offset, length)` each, one after
    another in rank order — so a caller can read rank `j`'s answer out of any
    starting buffers and compare it with what running `all_to_all` produced,
    block for block, without the counts being spelled out again. The kept slice
    is not a block, the diagonal never having been a transfer: it is already in
    the slot the transpose wants it in, so only the received blocks appear.
    Blocks of zero length are absent, nothing having moved, and every rank of
    the fabric appears even when it neither sends nor receives. The same
    `splits` refusals as `all_to_all` apply.
    """
    raise NotImplementedError("stage 7: implement exchange_with()")
