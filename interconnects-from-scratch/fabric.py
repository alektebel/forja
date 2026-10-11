"""fabric.py — the fabric: links, topologies, transfers, and the executor.

PROVIDED COMPLETE. Do not edit; it has no TODOs.

This module is the world the collectives live in, and nothing more:

* `Link` and `Topology` — ranks joined by links, each with a bandwidth in bytes
  per tick and a latency in ticks. Four named topologies are fixtures: `ring`,
  `full`, `tree`, and `switch` (a two-level fabric: cheap links within a group,
  a slow spine across groups).
* `Transfer` and `Plan` — what a collective *is* here: a set of transfers, each
  placed in a step. Nothing is timed and nothing is concurrent: a step's
  transfers may run at once, and a plan is legal only if no link carries two
  transfers in the same step.
* `run` — the executor: it applies a plan to buffers and returns the result. It
  does not compute costs; that is the exercise.
* `ceil_div` and `legality_problems` — the arithmetic and the legality rules the
  exercise's cost model and validator are measured against.

Determinism is a property of the whole course: no time, no unseeded random, no
module-level mutable state, and no floats anywhere. Every number here is an
`int`; bytes are `ELEMENT_BYTES * elements`, and ticks are counted, never
measured.
"""

import types
from dataclasses import dataclass

#: Bytes per element of a buffer. A transfer's cost is charged on bytes.
ELEMENT_BYTES = 4

#: The combining operations a `reduce` transfer may use.
OPS = ("sum", "min", "max")

#: What a transfer does: copy the slice, or combine it into the destination.
TRANSFER_OPS = ("send", "reduce")


class FabricError(ValueError):
    """A plan that cannot be run, or a fabric that cannot exist."""


def ceil_div(a, b):
    """`ceil(a / b)` in integers. `b` must be positive, `a` non-negative."""
    if b <= 0:
        raise FabricError("cannot divide by %r" % (b,))
    if a < 0:
        raise FabricError("cannot take the ceiling of a negative: %r" % (a,))
    return -(-a // b)


@dataclass(frozen=True)
class Link:
    """One undirected connection between two ranks.

    `a` and `b` are rank ids with `a < b` in every topology this module builds.
    A transfer over a `d`-hop path is charged `latency` ticks per hop and
    `ceil(bytes / bandwidth)` ticks per hop.
    """

    a: str
    b: str
    bandwidth: int
    latency: int

    def other(self, rank):
        """The far end of the link from `rank`."""
        if rank == self.a:
            return self.b
        if rank == self.b:
            return self.a
        raise FabricError("rank %r is not on link %r" % (rank, self))

    def joins(self, x, y):
        return (x == self.a and y == self.b) or (x == self.b and y == self.a)


@dataclass(frozen=True)
class Topology:
    """Ranks joined by links, with a total shortest-path rule.

    The ranks are sorted and the links are sorted by `(a, b)`, so two fabrics
    with the same shape print the same text. `path` is a breadth-first search
    that visits neighbours in rank order and keeps the first predecessor it
    finds, which makes the route (and therefore the cost) a function of the
    topology alone.
    """

    ranks: tuple
    links: tuple
    name: str = ""

    def __post_init__(self):
        if len(set(self.ranks)) != len(self.ranks):
            raise FabricError("duplicate rank in %r" % (self.ranks,))
        for link in self.links:
            if link.a >= link.b:
                raise FabricError("link %r is not canonical (a < b)" % (link,))
            for rank in (link.a, link.b):
                if rank not in self.ranks:
                    raise FabricError("link %r names unknown rank %r" % (link, rank))
            if link.bandwidth < 1:
                raise FabricError("link %r has bandwidth < 1" % (link,))
            if link.latency < 0:
                raise FabricError("link %r has negative latency" % (link,))

    def link(self, a, b):
        """The link joining two neighbours, or None."""
        for link in self.links:
            if link.joins(a, b):
                return link
        return None

    def neighbours(self, rank):
        """The neighbours of a rank, sorted."""
        if rank not in self.ranks:
            raise FabricError("unknown rank %r" % (rank,))
        found = []
        for link in self.links:
            if rank in (link.a, link.b):
                found.append(link.other(rank))
        return tuple(sorted(found))

    def path(self, a, b):
        """The route from `a` to `b` as a tuple of ranks, or None.

        Shortest by hop count; among the shortest, the smallest predecessor
        wins at every layer, so the answer is total.
        """
        for rank in (a, b):
            if rank not in self.ranks:
                raise FabricError("unknown rank %r" % (rank,))
        if a == b:
            return (a,)
        previous = {a: None}
        layer = [a]
        while layer and b not in previous:
            following = []
            for rank in sorted(layer):
                for neighbour in self.neighbours(rank):
                    if neighbour not in previous:
                        previous[neighbour] = rank
                        following.append(neighbour)
            layer = following
        if b not in previous:
            return None
        route = [b]
        while route[-1] != a:
            route.append(previous[route[-1]])
        route.reverse()
        return tuple(route)

    def distance(self, a, b):
        """Hops along `path(a, b)`, or None."""
        route = self.path(a, b)
        return None if route is None else len(route) - 1

    def hops_of(self, transfer):
        """The links a transfer traverses, in order, or None if unroutable."""
        route = self.path(transfer.src, transfer.dst)
        if route is None:
            return None
        return tuple(self.link(route[i], route[i + 1]) for i in range(len(route) - 1))

    def __str__(self):
        return self.name or "topology(%d ranks, %d links)" % (len(self.ranks), len(self.links))


def rank_ids(n):
    """`("r0", "r1", ...)`, the rank ids every fixture topology uses."""
    if n < 1:
        raise FabricError("a fabric needs at least one rank, got %r" % (n,))
    return tuple("r%d" % index for index in range(n))


def _links_from_pairs(pairs, bandwidth, latency):
    built = []
    for a, b in pairs:
        if a > b:
            a, b = b, a
        built.append(Link(a=a, b=b, bandwidth=bandwidth, latency=latency))
    return tuple(sorted(built, key=lambda link: (link.a, link.b)))


def ring(n, *, bandwidth=100, latency=5):
    """`r0 — r1 — … — r(n-1) — r0`: one link per edge, uniform costs."""
    ranks = rank_ids(n)
    pairs = [(ranks[i], ranks[(i + 1) % n]) for i in range(n)]
    return Topology(ranks=ranks, links=_links_from_pairs(pairs, bandwidth, latency),
                    name="ring(%d)" % n)


def full(n, *, bandwidth=100, latency=5):
    """Every pair of ranks joined directly."""
    ranks = rank_ids(n)
    pairs = [(ranks[i], ranks[j]) for i in range(n) for j in range(i + 1, n)]
    return Topology(ranks=ranks, links=_links_from_pairs(pairs, bandwidth, latency),
                    name="full(%d)" % n)


def tree(n, *, bandwidth=100, latency=5):
    """A binary tree: rank `i` hangs off rank `(i - 1) // 2`."""
    ranks = rank_ids(n)
    pairs = [(ranks[i], ranks[(i - 1) // 2]) for i in range(1, n)]
    return Topology(ranks=ranks, links=_links_from_pairs(pairs, bandwidth, latency),
                    name="tree(%d)" % n)


def switch(n, *, width=4, group_bandwidth=200, group_latency=2,
           spine_bandwidth=25, spine_latency=20):
    """A two-level fabric: groups of `width` ranks behind a switch, switches
    joined by a spine.

    Every rank in a group is joined to every other rank in it (the cheap
    NVLink-shaped side, `group_bandwidth`/`group_latency`). Each group has one
    spine port — its lowest rank — and the ports are joined in a ring (the
    expensive InfiniBand-shaped side, `spine_bandwidth`/`spine_latency`). So a
    transfer inside a group is one hop, and a transfer across groups is three:
    rank, port, port, rank.
    """
    if width < 2:
        raise FabricError("a group needs at least two ranks, got %r" % (width,))
    ranks = rank_ids(n)
    groups = [ranks[index:index + width] for index in range(0, n, width)]
    pairs = []
    for group in groups:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pairs.append((group[i], group[j]))
    ports = [group[0] for group in groups]
    spine = []
    if len(ports) > 1:
        # A ring of two ports is one link, and a ring of four is a four-cycle:
        # the pairs are canonicalised so no link is built twice.
        spine = sorted({(min(ports[i], ports[(i + 1) % len(ports)]),
                         max(ports[i], ports[(i + 1) % len(ports)]))
                        for i in range(len(ports))})
    spine_pairs = set(spine)
    cheap = _links_from_pairs(
        [pair for pair in pairs if (min(pair), max(pair)) not in spine_pairs],
        group_bandwidth, group_latency)
    expensive = _links_from_pairs(spine, spine_bandwidth, spine_latency)
    return Topology(ranks=ranks, links=tuple(sorted(cheap + expensive,
                                                    key=lambda link: (link.a, link.b))),
                    name="switch(%d, width=%d)" % (n, width))


@dataclass(frozen=True)
class Transfer:
    """One slice of one rank's buffer moving to another rank, in one step.

    `offset` and `length` are in elements and refer to the same slice in both
    buffers. `op` is `"send"` (copy) or `"reduce"` (combine into the
    destination). A transfer with `op="reduce"` costs what a send costs; what it
    changes is the buffer, and therefore what the executor returns.
    """

    src: str
    dst: str
    offset: int
    length: int
    step: int
    op: str = "send"

    def endpoints(self):
        return (self.src, self.dst)

    def slice(self):
        return (self.offset, self.offset + self.length)


@dataclass(frozen=True)
class Plan:
    """A collective as data: transfers, each in a step.

    The transfers are stored sorted by `(step, src, dst, offset)`, so a plan is
    a canonical object and two plans that say the same thing are equal.
    """

    transfers: tuple
    name: str = ""

    def __post_init__(self):
        for transfer in self.transfers:
            if transfer.op not in TRANSFER_OPS:
                raise FabricError("transfer %r has op %r, not one of %r"
                                  % (transfer, transfer.op, TRANSFER_OPS))
            if transfer.step < 0:
                raise FabricError("transfer %r has a negative step" % (transfer,))
            if transfer.length <= 0:
                raise FabricError("transfer %r has length %r" % (transfer, transfer.length))
            if transfer.offset < 0:
                raise FabricError("transfer %r has a negative offset" % (transfer,))
            if transfer.src == transfer.dst:
                raise FabricError("transfer %r sends to itself" % (transfer,))
        # A plan is canonical: two plans that say the same thing are equal, and
        # a step's transfers are always visited in one order.
        object.__setattr__(self, "transfers", tuple(
            sorted(self.transfers, key=lambda transfer: (
                transfer.step, transfer.src, transfer.dst, transfer.offset,
                transfer.op))))

    def steps(self):
        """The distinct steps of the plan, sorted."""
        return tuple(sorted({transfer.step for transfer in self.transfers}))

    def at(self, step):
        """The transfers of one step, in canonical order."""
        return tuple(transfer for transfer in self.transfers if transfer.step == step)

    def outgoing(self, rank):
        return tuple(transfer for transfer in self.transfers if transfer.src == rank)

    def incoming(self, rank):
        return tuple(transfer for transfer in self.transfers if transfer.dst == rank)

    def elements_moved(self):
        """Total elements moved, counting a transfer once."""
        return sum(transfer.length for transfer in self.transfers)

    def __str__(self):
        return self.name or "plan(%d transfers, %d steps)" % (
            len(self.transfers), len(self.steps()))


def send(src, dst, size, step, *, offset=0, op="send"):
    """Build a `Transfer` without spelling the field names out.

    `size` is a length in elements — the name the course uses for it — and the
    argument order is the one every stage's plan builder reads like.
    """
    return Transfer(src=src, dst=dst, offset=offset, length=size, step=step, op=op)


def _sorted_reasons(reasons):
    seen = []
    for reason in reasons:
        if reason not in seen:
            seen.append(reason)
    return tuple(seen)


def legality_problems(topology, plan):
    """Every reason the plan cannot run, as a tuple of strings (empty if legal).

    The rules, in the order they are reported:

    * a transfer names a rank the topology does not have;
    * a transfer cannot be routed (`path` is None);
    * a transfer's slice falls outside `length`, when a length is given;
    * two transfers in the same step share a **directed** link, so they cannot
      be simultaneous. Links are full duplex: `r0 -> r1` and `r1 -> r0` in one
      step are legal (that is what a pairwise exchange is), while two transfers
      that both traverse `r0 -> r1` are not.

    The slice rule needs the buffer length, which the plan does not carry, so
    this function checks slices against nothing and the executor checks them
    against the buffers it was handed (see `run`).
    """
    problems = []
    known = set(topology.ranks)
    for transfer in plan.transfers:
        for rank in (transfer.src, transfer.dst):
            if rank not in known:
                problems.append("transfer %r names unknown rank %r" % (transfer, rank))
    for transfer in plan.transfers:
        if transfer.src in known and transfer.dst in known:
            if topology.hops_of(transfer) is None:
                problems.append("transfer %r cannot be routed" % (transfer,))
    for step in plan.steps():
        carriers = {}
        for transfer in plan.at(step):
            if transfer.src not in known or transfer.dst not in known:
                continue
            route = topology.path(transfer.src, transfer.dst)
            if route is None:
                continue
            for index in range(len(route) - 1):
                link = topology.link(route[index], route[index + 1])
                carriers.setdefault(
                    (link.a, link.b, route[index], route[index + 1]), []).append(transfer)
        for (a, b, x, y), transfers in sorted(carriers.items()):
            if len(transfers) > 1:
                problems.append(
                    "step %d carries %d transfers from %s to %s in the same direction"
                    % (step, len(transfers), x, y))
    return _sorted_reasons(problems)


def buffers(n, length, *, fill=None):
    """Deterministic starting buffers: rank `ri` holds `(i + 1) * (j + 1)`.

    Pass `fill(i, j)` for a different pattern; it must answer an `int`. The
    default has no zeros and no repeated values, so a lost chunk or an aliased
    accumulator changes the answer.
    """
    ranks = rank_ids(n)
    out = {}
    for index, rank in enumerate(ranks):
        if fill is None:
            out[rank] = tuple((index + 1) * (j + 1) for j in range(length))
        else:
            values = tuple(fill(index, j) for j in range(length))
            for value in values:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise FabricError("fill(%d, %r) answered %r, not an int"
                                      % (index, 0, value))
            out[rank] = values
    return out


def reference(buffers_map, *, op="sum"):
    """The element-wise combination of every rank's buffer."""
    if op not in OPS:
        raise FabricError("op %r is not one of %r" % (op, OPS))
    values = [buffers_map[rank] for rank in sorted(buffers_map)]
    if not values:
        raise FabricError("no buffers to combine")
    length = len(values[0])
    for rank in sorted(buffers_map):
        if len(buffers_map[rank]) != length:
            raise FabricError("rank %r holds %d elements, not %d"
                              % (rank, len(buffers_map[rank]), length))
    out = []
    for j in range(length):
        column = [value[j] for value in values]
        if op == "sum":
            out.append(sum(column))
        elif op == "min":
            out.append(min(column))
        else:
            out.append(max(column))
    return tuple(out)


def _combine(current, incoming, op):
    if op == "sum":
        return current + incoming
    if op == "min":
        return current if current < incoming else incoming
    if op == "max":
        return current if current > incoming else incoming
    raise FabricError("op %r is not one of %r" % (op, OPS))


def run(topology, plan, buffers_map, *, op="sum", check=True):
    """Apply `plan` to `buffers_map` and return the resulting buffers.

    Within a step every transfer reads the buffers as they were at the start of
    that step and writes its own destination, so the step is a simultaneous
    exchange. `op` is the combining operation for `op="reduce"` transfers.
    """
    if op not in OPS:
        raise FabricError("op %r is not one of %r" % (op, OPS))
    if check:
        problems = legality_problems(topology, plan)
        if problems:
            raise FabricError("illegal plan: " + "; ".join(problems))
    length = None
    for rank in sorted(buffers_map):
        if length is None:
            length = len(buffers_map[rank])
        elif len(buffers_map[rank]) != length:
            raise FabricError("rank %r holds %d elements, not %d"
                              % (rank, len(buffers_map[rank]), length))
    for rank in sorted(buffers_map):
        if rank not in topology.ranks:
            raise FabricError("buffers carry rank %r, which the topology does not have"
                              % (rank,))
    state = {rank: tuple(buffers_map[rank]) for rank in sorted(buffers_map)}
    for step in plan.steps():
        writes = {}
        for transfer in plan.at(step):
            if transfer.src not in state or transfer.dst not in state:
                raise FabricError("transfer %r names a rank with no buffer" % (transfer,))
            start, end = transfer.slice()
            if end > length:
                raise FabricError(
                    "transfer %r slices [%d:%d] out of a %d-element buffer"
                    % (transfer, start, end, length))
            piece = state[transfer.src][start:end]
            if transfer.op == "send":
                writes.setdefault(transfer.dst, {})
                for j, value in enumerate(piece):
                    writes[transfer.dst][start + j] = value
            else:
                target = writes.get(transfer.dst)
                merged = {}
                base = state[transfer.dst]
                for j, value in enumerate(piece):
                    has_pending = target is not None and (start + j) in target
                    current = target[start + j] if has_pending else base[start + j]
                    merged[start + j] = _combine(current, value, op)
                writes.setdefault(transfer.dst, {})
                writes[transfer.dst].update(merged)
        for rank, cells in sorted(writes.items()):
            row = list(state[rank])
            for index, value in sorted(cells.items()):
                row[index] = value
            state[rank] = tuple(row)
    return state
