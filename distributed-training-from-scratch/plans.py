"""plans.py — the collective plan library, PROVIDED COMPLETE.

This is I9's ten stages lifted into one module so that H1's stages compose
plans instead of re-deriving algorithms. Each function answers the
`fabric.Plan` the executor would run for one collective over a **group** — a
tuple of the world's own rank ids — and nothing else:

* what the group is (its ranks, the world's links between them) is
  `group_fabric`;
* what a collective moves (which rank sends which slice to which rank, in which
  step, and whether the transfer combines into the destination) is the plan;
* what the plan *means* is `fabric.run`: a broadcast leaves the root's buffer on
  every member, a reduce leaves the element-wise sum on the root, an all-reduce
  on every member, an all-gather leaves, in rank order, the per-rank shards, a
  reduce-scatter leaves each rank holding its own shard of the element-wise
  sum, an all-to-all leaves each rank holding the other ranks' `split`-sized
  pieces, and a sendrecv moves one buffer from one rank to another.

No cost is computed here (that is `stage_01.step_ticks`) and nothing is held
between calls: a plan is a pure function of the world, the group and the
length. Every number is an `int`; every refusal is a `fabric.FabricError`
naming the offender and interpolating the actual.

The algorithms are I9's, verbatim in shape: the ring broadcast, the doubling
broadcast, the ring and tree reduce, the pipelined ring all-reduce, the tree
all-reduce, recursive doubling, the ring all-gather and reduce-scatter, and the
one-step all-to-all. `doubling_allreduce` needs one-hop XOR partners, so it is
refused on a ring and across a two-level switch spine; a group the topology
cannot serve (a member with no route to the others, an unknown rank), a length
the chunking cannot divide, and a plan the fabric cannot carry (two transfers
sharing one directed link in one step — the ring walk over a tree's rank order)
are refused by every function that needs them, naming the actual.

The all-to-alls are the exception to "one collective, one launch": I9's
one-step exchange exists only on a clique, so `alltoall` and
`alltoall_from_splits` **schedule** their pairs into as few steps as the
fabric's legality admits by a greedy sweep (a round-robin first-fit over the
waiting pairs, one send and one receive per rank per step) — `N - 1` steps on a
full mesh, more on a ring, a tree or a switch spine, and the same bytes either
way.

The helpers a stage asks its questions with:

* `group_ranks(world, group)` — the group's ranks, checked and put in the
  world's own rank order;
* `group_fabric(world, group)` — the sub-fabric the group's collective runs on
  (its members and the world's links between them), refusing a group whose own
  links do not reach every member;
* `chunking(members, elements, chunk=None)` — the chunk count and the elements
  in each chunk, refusing a chunk that is smaller than one, larger than the
  group, or does not divide the length;
* `equal_split(members, elements)` — the one piece size an equal-split
  all-to-all takes, refusing a length the group does not divide;
* `alltoall_from_splits(world, group, splits)` — the ragged table an uneven
  exchange (H1 stage 8's dispatch and combine) hands over instead of the equal
  split;
* `steps(plan)` — the step count of a built plan.

A group of one rank needs no plan at all: every collective over one rank is the
empty plan (no transfers, no steps), which costs nothing — the `dp`/`tp`/`ep`/
`cp` axis of one the stages must not charge for.
"""

import fabric


def _is_count(value):
    """Whether `value` is a whole count. A `bool` is an `int`, and not one."""
    return isinstance(value, int) and not isinstance(value, bool)


def _positive(elements, what="elements"):
    """The element count, or a refusal naming what was not positive."""
    if not _is_count(elements) or elements < 1:
        raise fabric.FabricError(
            "%s is %r: a collective moves a positive whole number of elements"
            % (what, elements))
    return elements


def group_ranks(world, group):
    """The group's ranks, in the world's own rank order, or a refusal.

    `group` is a tuple of rank ids. A rank the world does not have is refused
    (naming the rank and the world's own ranks), and so is a rank named twice —
    a group is a set of ranks. The answer is in the world's rank order, so a
    stage may hand the group in any order and still get a plan whose "rank
    order" is the world's.
    """
    if not isinstance(group, tuple):
        raise fabric.FabricError("group %r is not a tuple of rank ids" % (group,))
    if not group:
        raise fabric.FabricError(
            "group %r is empty: a collective runs over at least one rank" % (group,))
    members = []
    for rank in group:
        if rank not in world.ranks:
            raise fabric.FabricError(
                "group %r names rank %r, which %s does not have; the ranks are "
                "%r" % (group, rank, world, world.ranks))
        if rank in members:
            raise fabric.FabricError("group %r names rank %r twice" % (group, rank))
        members.append(rank)
    return tuple(rank for rank in world.ranks if rank in members)


def group_fabric(world, group):
    """The sub-fabric the group's collective runs on, or a refusal.

    The members are the group's ranks, and the links are the world's own links
    *between* them: the group sees the links it owns, not the ones it would
    have to borrow from a rank outside it. A group of one has no links and
    needs none. A group whose own links cannot reach every member — two ranks
    of a ring that are not neighbours, two ranks of a two-level fabric that
    share neither a group nor a spine port — is refused, naming both members.
    """
    members = group_ranks(world, group)
    if len(members) == 1:
        return fabric.Topology(ranks=members, links=(),
                               name="group(%s) of one on %s" % (members[0], world))
    inside = set(members)
    links = tuple(link for link in world.links
                  if link.a in inside and link.b in inside)
    sub = fabric.Topology(ranks=members, links=links,
                          name="group(%s) on %s" % (", ".join(members), world))
    seen = {members[0]}
    reached = [members[0]]
    while reached:
        rank = reached.pop(0)
        for neighbour in sub.neighbours(rank):
            if neighbour not in seen:
                seen.add(neighbour)
                reached.append(neighbour)
    for rank in members:
        if rank not in seen:
            raise fabric.FabricError(
                "group %r cannot be served by %s: %s and %s are members and "
                "the group has no route between them" % (group, world, members[0], rank))
    return sub


def chunking(members, elements, chunk=None):
    """`(chunks, chunk_size)` for a ring collective, or a refusal.

    `members` is the group's rank count and `elements` the buffer's length in
    elements. A `chunk` of `None` is one chunk — the whole buffer — and an
    explicit `chunk` is the number of equal chunks. A chunk count below one, a
    count above the rank count (the ring has one chunk slot per rank) and a
    length the count does not divide are refused, each naming the actual.
    """
    _positive(elements)
    if not _is_count(members) or members < 1:
        raise fabric.FabricError(
            "members is %r: a group runs over at least one rank" % (members,))
    count = 1 if chunk is None else chunk
    if not _is_count(count) or count < 1:
        raise fabric.FabricError(
            "chunk is %r: the buffer is cut into at least one chunk" % (chunk,))
    if count > members:
        raise fabric.FabricError(
            "chunk is %r for a group of %d ranks: the ring has one chunk slot "
            "per rank" % (chunk, members))
    if elements % count != 0:
        raise fabric.FabricError(
            "elements %r is not a multiple of chunk %r: the chunks are equal"
            % (elements, count))
    return count, elements // count


def equal_split(members, elements):
    """The piece size an equal-split all-to-all takes, or a refusal.

    Every rank's buffer is cut into one piece per member, so the length must be
    the group's multiple; the piece size is the exact quotient. A length the
    group does not divide is refused, naming both.
    """
    _positive(elements)
    if not _is_count(members) or members < 1:
        raise fabric.FabricError(
            "members is %r: a group runs over at least one rank" % (members,))
    if elements % members != 0:
        raise fabric.FabricError(
            "elements %r is not a multiple of the group's %d ranks: an equal "
            "split needs one whole piece per rank" % (elements, members))
    return elements // members


def steps(plan):
    """The step count of a built plan — what a stage prices, without pricing it."""
    return len(plan.steps())


def _empty(name):
    """The plan of a collective over one rank: nothing needs to move."""
    return fabric.Plan(transfers=(), name=name)


def _legal(topology, plan):
    """The plan, if the fabric can carry it; a refusal naming the collision if not.

    A plan is data, and the fabric is the judge of it: a step that puts two
    transfers on one directed link cannot run, so a collective that would build
    one is refused here, naming the topology and the colliding step, rather
    than answered with a plan `fabric.run` would reject. I9's ring walks the
    group's rank order, which is a ring of one-hop links on a ring or a clique
    (`full`, a switch group) but not on a tree — that refusal lives here.
    """
    problems = fabric.legality_problems(topology, plan)
    if problems:
        raise fabric.FabricError(
            "%s cannot carry this collective's plan: %s"
            % (topology, "; ".join(problems)))
    return plan


# --------------------------------------------------------------------------
# Broadcast — the root's buffer on every member (I9 stage 2).
# --------------------------------------------------------------------------

def _root_in_group(members, root, group):
    if root not in members:
        raise fabric.FabricError(
            "root %r is not a rank of group %r; its ranks are %r"
            % (root, group, members))
    return root


def _broadcast_ring(topology, root, length):
    """`N - 1` steps, the root's successor forwarding on around the ring."""
    order = tuple(topology.ranks)
    start = order.index(root)
    transfers = []
    for step in range(1, len(order)):
        src = order[(start + step - 1) % len(order)]
        dst = order[(start + step) % len(order)]
        transfers.append(fabric.send(src, dst, length, step - 1))
    return fabric.Plan(transfers=tuple(transfers),
                       name="broadcast_ring(%s, root=%s)" % (topology, root))


def _informed_order(topology, root):
    """The breadth-first order from `root`: `{rank: depth}` and `{rank: parent}`."""
    depth = {root: 0}
    parent = {root: None}
    layer = [root]
    while layer:
        following = []
        for rank in sorted(layer):
            for neighbour in topology.neighbours(rank):
                if neighbour in depth:
                    continue
                depth[neighbour] = depth[rank] + 1
                parent[neighbour] = rank
                following.append(neighbour)
        layer = following
    return depth, parent


def _broadcast_tree(topology, root, length):
    """One step per level: every informed rank forwards to its children."""
    depth, parent = _informed_order(topology, root)
    unreached = [rank for rank in topology.ranks if rank not in depth]
    if unreached:
        raise fabric.FabricError(
            "root %r cannot reach %r on %s, so the doubling cannot cover every "
            "rank" % (root, unreached[0], topology))
    transfers = tuple(
        fabric.send(parent[rank], rank, length, depth[rank] - 1)
        for rank in topology.ranks if rank != root)
    return fabric.Plan(transfers=transfers,
                       name="broadcast_tree(%s, root=%s)" % (topology, root))


def ring_broadcast(world, group, root, elements):
    """The root's buffer on every member, around the group's ring in rank order.

    `N - 1` steps of one transfer each: the rank after the root learns in step
    0 and the last rank learns in step `N - 2`. A root outside the group is
    refused, naming it; a group of one needs no plan at all. Every transfer
    moves the whole `elements`-element buffer.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    _root_in_group(members, root, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("broadcast of one on %s" % topology)
    return _legal(topology, _broadcast_ring(topology, root, elements))


def tree_broadcast(world, group, root, elements):
    """The root's buffer on every member, down the group's breadth-first tree.

    One step per level of the tree from the root: a rank learns in the step of
    its depth and forwards to its children in the next, so the plan is the
    group's own tree, not a ring. A root outside the group is refused, naming
    it; a group of one needs no plan at all.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    _root_in_group(members, root, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("broadcast of one on %s" % topology)
    return _legal(topology, _broadcast_tree(topology, root, elements))


# --------------------------------------------------------------------------
# Reduce — the element-wise sum at the root (I9 stage 3).
# --------------------------------------------------------------------------

def _ring_chain(topology, root):
    """The chain the accumulator walks: one `(src, dst)` per step, per hop."""
    ranks = list(topology.ranks)
    start = ranks.index(root)
    count = len(ranks)
    return [(ranks[(start - 1 - step) % count], ranks[(start - 2 - step) % count])
            for step in range(count - 1)]


def _reduce_tree_order(topology, root):
    """`(parent, depth)` of the breadth-first tree `root` hangs from."""
    parent = {root: None}
    depth = {root: 0}
    layer = [root]
    while layer:
        following = []
        for rank in sorted(layer):
            for neighbour in topology.neighbours(rank):
                if neighbour not in parent:
                    parent[neighbour] = rank
                    depth[neighbour] = depth[rank] + 1
                    following.append(neighbour)
        layer = following
    return parent, depth


def _reduce_ring(topology, root, length):
    """`N - 1` combining steps, the accumulator walking the ring to the root."""
    transfers = tuple(
        fabric.send(src, dst, length, step, op="reduce")
        for step, (src, dst) in enumerate(_ring_chain(topology, root)))
    return fabric.Plan(transfers=transfers,
                       name="reduce_ring(%s, root=%s)" % (topology, root))


def _reduce_tree(topology, root, length):
    """One step per level, deepest first: every rank combines into its parent."""
    parent, depth = _reduce_tree_order(topology, root)
    leaves = max(depth[rank] for rank in topology.ranks)
    order = sorted((rank for rank in topology.ranks if rank != root),
                   key=lambda rank: (-depth[rank], rank))
    transfers = tuple(
        fabric.send(rank, parent[rank], length, leaves - depth[rank], op="reduce")
        for rank in order)
    return fabric.Plan(transfers=transfers,
                       name="reduce_tree(%s, root=%s)" % (topology, root))


def ring_reduce(world, group, root, elements):
    """The element-wise sum of every member's buffer, at the root.

    `N - 1` steps, each combining a whole buffer into the next rank around the
    group's ring in rank order, so the accumulator's last hop lands on the
    root. Only the root's contents are the collective's answer; the ranks the
    accumulator passed through hold partial sums. A root outside the group is
    refused, naming it; a group of one is already reduced.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    _root_in_group(members, root, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("reduce of one on %s" % topology)
    return _legal(topology, _reduce_ring(topology, root, elements))


def tree_reduce(world, group, root, elements):
    """The element-wise sum of every member's buffer, at the root, up the tree.

    One step per level of the group's breadth-first tree from the root, deepest
    first: a rank whose children have all sent combines its own buffer — by then
    its subtree's sum — into its parent. A root outside the group is refused,
    naming it; a group of one is already reduced.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    _root_in_group(members, root, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("reduce of one on %s" % topology)
    return _legal(topology, _reduce_tree(topology, root, elements))


# --------------------------------------------------------------------------
# All-reduce — the element-wise sum on every member (I9 stages 4 and 5).
# --------------------------------------------------------------------------

def _reduce_scatter_transfers(topology, length, chunks, first_step, op):
    """The `N - 1` reduce-scatter steps, every rank sending one slice of `op`."""
    count, size = chunking(len(topology.ranks), length, chunks)
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
    """The `N - 1` all-gather steps, every rank forwarding the slice it holds."""
    count, size = chunking(len(topology.ranks), length, chunks)
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


def _all_reduce_ring(topology, length, chunk):
    """Reduce-scatter then all-gather: `2(N - 1)` steps on the group's ring."""
    count, size = chunking(len(topology.ranks), length, chunk)
    total = len(topology.ranks)
    transfers = _reduce_scatter_transfers(topology, length, chunk, 0, "reduce")
    transfers += _all_gather_transfers(topology, length, chunk, total - 1)
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_reduce_ring (chunks=%d, size=%d)" % (count, size))


def _tree_of(topology, root):
    """The topology's own tree as `(parent, level)`, rooted at `root`."""
    parent = {}
    level = {}
    for rank in topology.ranks:
        route = topology.path(rank, root)
        if route is None:
            raise fabric.FabricError(
                "rank %r has no route to root %r on %s: a tree all-reduce needs "
                "a connected group" % (rank, root, topology))
        level[rank] = len(route) - 1
        parent[rank] = route[1] if len(route) > 1 else None
    return parent, level


def _all_reduce_tree(topology, length):
    """Reduce to the root up the topology's own tree, then broadcast back down."""
    root = topology.ranks[0]
    parent, level = _tree_of(topology, root)
    levels = max(level.values())
    transfers = []
    for step in range(levels):
        for rank in topology.ranks:
            if level[rank] == levels - step and parent[rank] is not None:
                transfers.append(fabric.send(rank, parent[rank], length, step,
                                             op="reduce"))
    for step in range(levels):
        for rank in topology.ranks:
            if level[rank] != step:
                continue
            for child in topology.ranks:
                if parent[child] == rank:
                    transfers.append(fabric.send(rank, child, length, levels + step))
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_reduce_tree (root=%s, levels=%d)" % (root, levels))


def _all_reduce_doubling(topology, length):
    """`log2(N)` steps, each rank combining with the rank `r XOR 2**k`."""
    ranks = topology.ranks
    total = len(ranks)
    steps_count = 0
    while (1 << steps_count) < total:
        steps_count += 1
    if (1 << steps_count) != total:
        raise fabric.FabricError(
            "N is %d, not a power of two: recursive doubling needs one exchange "
            "per bit of the rank id, so N = 2**k" % (total,))
    transfers = []
    for step in range(steps_count):
        span = 1 << step
        for index, rank in enumerate(ranks):
            partner = ranks[index ^ span]
            hops = topology.distance(rank, partner)
            if hops != 1:
                raise fabric.FabricError(
                    "recursive doubling needs every XOR partner to be a direct "
                    "neighbour, but rank %s and rank %s are %r hops apart: a "
                    "butterfly step over them is not one legal exchange"
                    % (rank, partner, hops))
            transfers.append(fabric.send(rank, partner, length, step, op="reduce"))
    return fabric.Plan(
        transfers=tuple(transfers),
        name="all_reduce_doubling (N=%d, steps=%d)" % (total, steps_count))


def ring_allreduce(world, group, elements, *, chunk=None):
    """The element-wise sum of every member's buffer, on every member.

    The group's ring, the buffer cut into `chunk` equal chunks (`None` is one
    chunk — the whole buffer — so an explicit chunk is a pipelined ring).
    Reduce-scatter for `N - 1` steps, then all-gather for `N - 1` more: `2(N-1)`
    steps, every rank sending and receiving `2 * elements * (N - 1) // N`
    elements. A chunk below one, above the group's rank count, or one that does
    not divide `elements`, is refused, naming the actual; a group of one is
    already the whole sum.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    chunking(len(members), elements, chunk)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-reduce of one on %s" % topology)
    return _legal(topology, _all_reduce_ring(topology, elements, chunk))


def tree_allreduce(world, group, elements):
    """The element-wise sum on every member, up the group's own tree and back.

    `2 * levels` steps, where `levels` is the largest hop distance to the
    group's first rank: a reduce up the tree, then a broadcast down it. It is
    latency-cheap and bandwidth-dear — every level moves the whole payload
    again — which is the ring's trade the other way round. A group of one is
    already the whole sum.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-reduce of one on %s" % topology)
    return _legal(topology, _all_reduce_tree(topology, elements))


def doubling_allreduce(world, group, elements):
    """The element-wise sum on every member, by recursive doubling.

    `log2(N)` steps, each rank combining its whole buffer with the rank
    `r XOR 2**k` in step `k`. It needs `N` a power of two and every XOR partner
    a direct neighbour of the group's fabric, so it is refused — naming the
    offender and the hop count — on a ring (`r0` and `r2` are two hops apart)
    and across a two-level switch spine (a group spanning two switch groups has
    members three hops apart). A group of one is already the whole sum.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-reduce of one on %s" % topology)
    return _legal(topology, _all_reduce_doubling(topology, elements))


# --------------------------------------------------------------------------
# All-gather and reduce-scatter (I9 stage 6).
# --------------------------------------------------------------------------

def allgather(world, group, elements):
    """Every member ends holding every member's shard, in rank order.

    The buffer is cut into one shard per member (`elements // N` elements each,
    so the group must divide the length) and the piece a rank contributes is
    its own shard. `N - 1` steps, each rank forwarding one shard to its
    successor on the group's ring. A length the group does not divide is
    refused, naming both; a group of one already holds the whole concatenation.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    count, size = chunking(len(members), elements, len(members))
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-gather of one on %s" % topology)
    transfers = _all_gather_transfers(topology, elements, len(members), 0)
    return _legal(topology, fabric.Plan(
        transfers=tuple(transfers),
        name="all_gather (chunks=%d, size=%d)" % (count, size)))


def reduce_scatter(world, group, elements):
    """Each member ends holding its own shard of the element-wise sum.

    The buffer is cut into one shard per member; `N - 1` combining steps walk
    the group's ring, and shard `c` of the element-wise sum ends up on rank `c`
    of the group. The rest of each rank's buffer holds partial sums and is not
    the collective's answer. A length the group does not divide is refused,
    naming both; a group of one is already its own shard.
    """
    elements = _positive(elements)
    members = group_ranks(world, group)
    count, size = chunking(len(members), elements, len(members))
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("reduce-scatter of one on %s" % topology)
    transfers = _reduce_scatter_transfers(topology, elements, len(members), 0,
                                          "reduce")
    return _legal(topology, fabric.Plan(
        transfers=tuple(transfers),
        name="reduce_scatter (chunks=%d, size=%d)" % (count, size)))


# --------------------------------------------------------------------------
# All-to-all and sendrecv (I9 stages 7 and 8).
# --------------------------------------------------------------------------

def _check_splits(topology, splits):
    """The rank count, or a refusal naming the malformed `splits` table."""
    ranks = len(topology.ranks)
    if len(splits) != ranks:
        raise fabric.FabricError(
            "splits has %d rows, but %s has %d ranks" % (len(splits), topology, ranks))
    for index, row in enumerate(splits):
        if len(row) != ranks:
            raise fabric.FabricError(
                "splits[%d] has %d columns, but %s has %d ranks"
                % (index, len(row), topology, ranks))
        for slot, count in enumerate(row):
            if not _is_count(count):
                raise fabric.FabricError(
                    "splits[%d][%d] is %r, not an element count" % (index, slot, count))
            if count < 0:
                raise fabric.FabricError(
                    "splits[%d][%d] is %r: a count is never negative"
                    % (index, slot, count))
    return ranks


def _recv_offset(splits, i, j):
    """Where rank `j`'s buffer keeps the block rank `i` sent it."""
    return sum(splits[k][j] for k in range(i))


def _rotation_pairs(members):
    """The round-robin rounds of `members` ranks, as index pairs of each round.

    The circle method, one round per step: a round is a *pairing* — every rank
    exchanges with exactly one peer — and every unordered pair of ranks appears
    in exactly one round, so the rounds together move every ordered pair once.
    An even count has `members - 1` rounds; an odd count has `members` of them,
    one rank sitting out each round (the last circle position is a dummy).
    """
    if members < 2:
        return ()
    even = members % 2 == 0
    size = members if even else members + 1
    circle = size - 1
    half = size // 2
    rounds = []
    for step in range(circle):
        pairs = [(i, j) for i in range(circle) for j in range(i + 1, circle)
                 if (i + j) % circle == step]
        if even:
            pairs.append(tuple(sorted(((step * half) % circle, circle))))
        rounds.append(tuple(sorted(pairs)))
    return tuple(rounds)


def _rotation_order(members):
    """Every ordered pair once, round by round: the order the steps fill in."""
    order = []
    for pairs in _rotation_pairs(members):
        for i, j in pairs:
            order.append((i, j))
            order.append((j, i))
    return tuple(order)


def _no_aliasing(topology, transfers):
    """Refuse a table whose slices a rank's own incoming transfer overwrites
    before it sends them: read and written at one offset, the exchange would
    move bytes that are no longer the sender's.

    The equal split never hazards: a rank sends only from its own kept piece
    (offset `i * split`), and no rank ever receives into that piece. A ragged
    table can — the refusal names the rank, the two slices and the two steps.
    """
    reads = {}
    writes = {}
    for transfer in transfers:
        start, end = transfer.slice()
        reads.setdefault(transfer.src, []).append((start, end, transfer))
        writes.setdefault(transfer.dst, []).append((start, end, transfer))
    for rank in sorted(reads, key=topology.ranks.index):
        for start, end, read in reads[rank]:
            for other_start, other_end, written in writes.get(rank, ()):
                if written.step >= read.step:
                    continue
                if other_start < end and start < other_end:
                    raise fabric.FabricError(
                        "the in-place exchange cannot run on %s: rank %s's slice "
                        "[%d:%d] is overwritten by %s in step %d, before it is sent "
                        "in step %d" % (topology, rank, start, end, written,
                                        written.step, read.step))


def _equal_splits(members, split):
    """The square table of an equal split: `split` elements to every peer."""
    return tuple(tuple(split for _ in range(members)) for _ in range(members))


def _exchange(topology, splits, name):
    """The all-to-all's plan: every ordered pair's transfer, packed into steps.

    The rule, deterministic and a pure function of the table and the fabric:

    * the pairs are visited in the round-robin order `_rotation_order`, a round
      of which is a pairing — so each rank hands over at most one piece and
      takes in at most one piece per step, and a full mesh needs `N - 1` steps
      (`N` for an odd count), one round per step, carrying `N(N-1)` transfers;
    * a step is filled in one sweep of the pairs still waiting, in that order:
      a transfer goes into the step when its source has not sent, its
      destination has not received and none of its route's directed links is
      already taken by the step, and is carried to the next sweep otherwise (the
      first waiting pair always fits a fresh step, so a step is never empty and
      the sweeps end);
    * a topology with longer routes (a ring's cycle, a switch's spine) therefore
      defers pairs into later steps, and the same exchange costs more steps
      there than on a full mesh. That every step is legal — no directed link
      twice in it — is what justifies the count, and `fabric.legality_problems`
      is the judge of it.

    The exchange is in place — one offset is both read and written — so the
    schedule is checked against the one hazard that creates: a rank's outgoing
    slice must not have been overwritten by an earlier step's incoming transfer
    (`_no_aliasing`). The equal split never hazards, because a rank sends only
    from the piece it keeps and nothing writes there.
    """
    ranks = _check_splits(topology, splits)
    pending = []
    for i, j in _rotation_order(ranks):
        if i == j or splits[i][j] == 0:
            continue
        src, dst = topology.ranks[i], topology.ranks[j]
        route = topology.path(src, dst)
        pending.append((src, dst, splits[i][j], _recv_offset(splits, i, j),
                        tuple((route[hop], route[hop + 1])
                              for hop in range(len(route) - 1))))
    transfers = []
    step = 0
    while pending:
        # One step, filled as full as the routing admits: every pair still
        # waiting is tried in the round-robin order, and a fresh step always
        # takes the first of them, so a step is never empty and the loop ends.
        links = set()
        sends = set()
        takes = set()
        waiting = []
        for src, dst, length, offset, route in pending:
            if src in sends or dst in takes or any(link in links for link in route):
                waiting.append((src, dst, length, offset, route))
                continue
            links.update(route)
            sends.add(src)
            takes.add(dst)
            transfers.append(fabric.send(src, dst, length, step, offset=offset))
        pending = waiting
        step += 1
    _no_aliasing(topology, transfers)
    plan = fabric.Plan(transfers=tuple(transfers),
                       name=name % (ranks, len(transfers), step))
    return _legal(topology, plan)


def alltoall(world, group, elements, *, split):
    """Each member ends holding the other members' `split`-sized pieces.

    Every rank's buffer is cut into one piece per member — an equal split, so
    `elements` is the group's multiple and `split` is `elements // N` — and every
    ordered pair of distinct ranks is one transfer, `N(N-1)` of them, the piece a
    rank keeps never moving. The transfers are **scheduled** into steps by
    `_exchange`: a round-robin pairing per step, each pair's two directions
    placed in the earliest step the fabric's routing admits, so a full mesh runs
    the exchange in `N - 1` steps while a ring, a tree or a switch spine, whose
    routes are longer, needs more — the same bytes for more steps, which is the
    cost the stages are about. A `split` that is not `elements // N`, a length
    the group does not divide, and a group the topology cannot connect are all
    refused, naming the actual.
    """
    elements = _positive(elements)
    _positive(split, "split")
    members = group_ranks(world, group)
    size = equal_split(len(members), elements)
    if split != size:
        raise fabric.FabricError(
            "split is %r, but elements %r over %d ranks split equally into %r "
            "element pieces" % (split, elements, len(members), size))
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-to-all of one on %s" % topology)
    return _exchange(topology, _equal_splits(len(members), split),
                     "all_to_all (%d ranks, %d transfers, %d steps)")


def alltoall_from_splits(world, group, splits):
    """The ragged all-to-all: `splits[i][j]` elements from rank `i` to rank `j`.

    The equal split `alltoall` builds is one table; a stage whose exchange is
    uneven (H1 stage 8's expert dispatch, where a capacity cap makes the rows
    differ) hands its own square table instead. `splits[i][i]` is the piece
    rank `i` keeps, and the offset a piece is read from and written to is the
    running sum of the counts the ranks before the sender send that
    destination, so a table the buffer cannot hold is refused by the executor.
    The same scheduling, legality and in-place rules as `alltoall` apply, so a
    ragged exchange also runs on a ring, a tree and a switch.
    """
    members = group_ranks(world, group)
    topology = group_fabric(world, group)
    if len(members) == 1:
        return _empty("all-to-all of one on %s" % topology)
    return _exchange(topology, splits,
                     "all_to_all_from_splits (%d ranks, %d transfers, %d steps)")


def sendrecv(world, sender, receiver, elements):
    """One buffer from `sender` to `receiver`, in one step.

    The point-to-point primitive: one transfer, `elements` elements, offset 0,
    routed by the world's own shortest path. A sender or receiver the world
    does not have, a rank sending to itself, and a pair with no route are all
    refused, naming the offender.
    """
    elements = _positive(elements)
    for rank, what in ((sender, "sender"), (receiver, "receiver")):
        if rank not in world.ranks:
            raise fabric.FabricError(
                "%s %r is not a rank of %s; the ranks are %r"
                % (what, rank, world, world.ranks))
    if sender == receiver:
        raise fabric.FabricError(
            "sender and receiver are both %r: a sendrecv moves a buffer between "
            "two ranks" % (sender,))
    if world.path(sender, receiver) is None:
        raise fabric.FabricError(
            "there is no route from %r to %r on %s: the buffer cannot be moved"
            % (sender, receiver, world))
    return _legal(world, fabric.Plan(
        transfers=(fabric.send(sender, receiver, elements, 0),),
        name="sendrecv(%s -> %s, %d)" % (sender, receiver, elements)))
