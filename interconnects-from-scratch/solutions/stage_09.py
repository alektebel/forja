"""Interconnects From Scratch — stage 9: Choosing an algorithm, and the lower bound (implementation).

The reasoning behind the choice and the bound lives in the template's docstring
(`stage_09.py`); this file is only the body. Nothing here is measured: a
candidate is built as a plan, priced with `stage_01.plan_ticks`, and compared,
and every number is an `int`.

The one idea: `choose` builds every candidate whose own preconditions hold — the
ring (stage 4), the topology's own tree and the XOR butterfly (stage 5), and
SHARP — and keeps the cheapest by its own recomputed ticks. A candidate that
refuses itself is *dropped*, not raised, so the picker answers on a fabric where
one shape does not fit. SHARP is modelled as a rank-level plan on the two-level
fabric: each group's ranks reduce into the group's spine port, the ports walk
the spine cycle combining their partials, and the ports copy the result back
into their groups — three phases on `switch(8, width=4)`, so the same executor
that runs a ring can run it. `lower_bound` states the elements one rank must
move in one direction, and `within_bound` checks a plan against that floor.
"""

import fabric
import stage_01
import stage_04
import stage_05

#: The candidates `choose` builds, in the order ties are broken.
_ALGORITHMS = ("ring", "tree", "doubling", "sharp")


def _check_op(op):
    """Refuse an `op` that is neither a combining op nor the label `"reduce"`.

    A plan does not carry the combining operation — `fabric.run` applies it —
    so `op` selects nothing in a plan; it is checked and named, exactly as in
    `stage_04.all_reduce_ring` and `stage_05.all_reduce_tree`.
    """
    if op not in fabric.OPS and op != "reduce":
        raise fabric.FabricError(
            "op %r is not one of the combining ops %r, nor 'reduce'"
            % (op, fabric.OPS))


def _link_costs(topology):
    """The topology's links grouped by their cost `(bandwidth, latency)`."""
    costs = {}
    for link in topology.links:
        costs.setdefault((link.bandwidth, link.latency), []).append(link)
    return costs


def _rank_order(topology):
    """`{rank: index}`, the topology's own rank order.

    A rank id is `"r%d"`, but ten ranks in, the ids no longer sort as strings
    (`"r10"` before `"r8"`). Every choice of a group's port and every walk of
    the spine follows the order the topology itself carries its ranks in, which
    for every fixture fabric is `r0, r1, ...` by index.
    """
    return {rank: index for index, rank in enumerate(topology.ranks)}


def _cheap_components(cheap, order):
    """The cheap links' connected components, each in rank order."""
    components = []
    seen = set()
    for rank in sorted(cheap, key=order.__getitem__):
        if rank in seen:
            continue
        pending = [rank]
        found = []
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            found.append(current)
            pending.extend(sorted((neighbour for neighbour in cheap[current]
                                   if neighbour not in seen), key=order.__getitem__))
        components.append(tuple(sorted(found, key=order.__getitem__)))
    return components


def _two_level(topology):
    """`(groups, ports, spine)` of a two-level fabric, or a refusal naming it.

    A two-level fabric has exactly two link costs: the cheap one joins every
    rank of a group to every other rank of *that* group (a clique per group,
    the NVLink-shaped side) and the expensive one joins the groups' spine ports
    — each group's lowest rank — in a cycle (the InfiniBand-shaped side). Every
    rank belongs to a group, so the cheap links partition the ranks. Anything
    else is not a fabric SHARP could reduce in.
    """
    costs = _link_costs(topology)
    if len(costs) != 2:
        raise fabric.FabricError(
            "%s has %d distinct link costs, not the two of a two-level fabric: "
            "SHARP needs a cheap group side and an expensive spine to reduce in"
            % (topology, len(costs)))
    ordered = sorted(costs, key=lambda cost: (-cost[0], cost[1]))
    group_cost, spine_cost = ordered[0], ordered[1]
    order = _rank_order(topology)
    cheap = {}
    for link in costs[group_cost]:
        cheap.setdefault(link.a, set()).add(link.b)
        cheap.setdefault(link.b, set()).add(link.a)
    groups = []
    for rank in topology.ranks:
        if rank in cheap:
            continue
        groups.append((rank,))
    for component in _cheap_components(cheap, order):
        for first in component:
            for second in component:
                if order[first] < order[second] and second not in cheap[first]:
                    raise fabric.FabricError(
                        "the cheap links of %s do not form a group: %s and %s "
                        "are in one group but not joined by a cheap link"
                        % (topology, first, second))
        groups.append(component)
    if len(groups) < 2:
        raise fabric.FabricError(
            "%s has %d group(s): SHARP needs the spine between two of them"
            % (topology, len(groups)))
    ports = tuple(min(group, key=order.__getitem__) for group in groups)
    spine_adjacent = {}
    for link in costs[spine_cost]:
        for near, far in ((link.a, link.b), (link.b, link.a)):
            spine_adjacent.setdefault(near, set()).add(far)
    listed = sorted(spine_adjacent, key=order.__getitem__)
    if listed != sorted(ports, key=order.__getitem__):
        raise fabric.FabricError(
            "%s does not join its %d spine ports in a cycle: the expensive "
            "links touch %r, not %r"
            % (topology, len(ports), listed, sorted(ports, key=order.__getitem__)))
    degrees = sorted(len(spine_adjacent[port]) for port in ports)
    wanted = [1, 1] if len(ports) == 2 else [2] * len(ports)
    if degrees != wanted:
        raise fabric.FabricError(
            "%s does not join its %d spine ports in a cycle: their expensive "
            "degrees are %r, not %r" % (topology, len(ports), degrees, wanted))
    spine = [ports[0]]
    while len(spine) < len(ports):
        ahead = sorted((rank for rank in spine_adjacent[spine[-1]]
                        if rank not in spine), key=order.__getitem__)
        spine.append(ahead[0])
    return groups, ports, tuple(spine)


def _sharp_plan(topology, length, *, op="reduce"):
    """The in-network reduction as a rank-level plan on the two-level fabric.

    Phase one: every rank that is not its group's port sends its whole buffer
    to that port with `op="reduce"`, so one cheap step leaves each port holding
    its group's partial. Phase two: the ports combine on the spine — with two
    ports they exchange their partials in one crossing; with more, the
    accumulator walks the spine cycle and the result walks back, so no step
    ever has a port read what it is writing. Phase three: each port copies the
    result back into its group in one cheap step with `op="send"`. Three phases
    on `switch(8, width=4)`, and every transfer of each phase can run beside
    the others in one step.
    """
    _check_op(op)
    groups, ports, spine = _two_level(topology)
    transfers = []
    for group, port in zip(groups, ports):
        for rank in group:
            if rank != port:
                transfers.append(fabric.send(rank, port, length, 0, op="reduce"))
    if len(spine) == 2:
        crossing = 1
        transfers.append(fabric.send(spine[0], spine[1], length, 1, op="reduce"))
        transfers.append(fabric.send(spine[1], spine[0], length, 1, op="reduce"))
    else:
        crossings = len(spine) - 1
        for index in range(crossings):
            transfers.append(fabric.send(spine[index], spine[index + 1], length,
                                         1 + index, op="reduce"))
        for index in range(crossings):
            transfers.append(fabric.send(spine[crossings - index],
                                         spine[crossings - 1 - index], length,
                                         1 + crossings + index))
        crossing = 2 * crossings
    for group, port in zip(groups, ports):
        for rank in group:
            if rank != port:
                transfers.append(fabric.send(port, rank, length, 1 + crossing))
    return fabric.Plan(
        transfers=tuple(transfers),
        name="sharp (groups=%d, ports=%d, length=%d)"
             % (len(groups), len(ports), length))


def sharp_ticks(topology, length):
    """What the in-network reduction costs, in the cost model's own ticks.

    The price of the rank-level SHARP plan `_sharp_plan` builds: a refusal on a
    topology with no two-level fabric (no cheap group side, no spine), naming
    that topology, and otherwise `stage_01.plan_ticks` of the plan itself — the
    same arithmetic every other candidate is priced with.
    """
    if length <= 0:
        raise fabric.FabricError(
            "length %r names no elements to reduce" % (length,))
    return stage_01.plan_ticks(topology, _sharp_plan(topology, length))


def _build(algorithm, topology, length, op):
    """Build the named candidate's plan, or let its own refusal out."""
    if algorithm == "ring":
        return stage_04.all_reduce_ring(topology, length, op=op)
    if algorithm == "tree":
        return stage_05.all_reduce_tree(topology, length, op=op)
    if algorithm == "doubling":
        return stage_05.all_reduce_doubling(topology, length, op=op)
    return _sharp_plan(topology, length, op=op)


def choose(topology, length, op="reduce"):
    """The cheapest candidate for this fabric and size, and its plan.

    Every candidate in `_ALGORITHMS` is built and priced with its own
    `stage_01.plan_ticks`; the smallest total wins and ties go to the earlier
    name in `_ALGORITHMS`. A candidate whose preconditions fail — a ring whose
    chunking does not divide `length`, a butterfly whose `N` is not a power of
    two or whose XOR partners are not neighbours, a SHARP plan on a fabric with
    no spine — is *dropped*, not raised: the answer is a function of the costs
    of the candidates that fit, never of a size table or of the fabric's name.
    A fabric where nothing fits is a `fabric.FabricError`.
    """
    _check_op(op)
    if length <= 0:
        raise fabric.FabricError(
            "length %r names no elements to reduce" % (length,))
    best = None
    for algorithm in _ALGORITHMS:
        try:
            plan = _build(algorithm, topology, length, op=op)
        except fabric.FabricError:
            continue
        ticks = stage_01.plan_ticks(topology, plan)
        if best is None or ticks < best[0]:
            best = (ticks, algorithm, plan)
    if best is None:
        raise fabric.FabricError(
            "no all-reduce fits %s at %d elements: the ring needs a dividend "
            "chunking, the tree a route to the root, the butterfly a power of "
            "two whose XOR partners are neighbours, and SHARP a two-level "
            "fabric" % (topology, length))
    return best[1], best[2]


def lower_bound(length, n):
    """The elements one rank must move, in one direction, for an all-reduce.

    However the collective is shaped, each of the `n` ranks contributes its
    `length`-element buffer to the answer, and the answer is assembled from
    `length * (n - 1)` elements that some rank other than its owner moved in
    that rank's direction: `S(N - 1)/N` per rank, rounded down because a rank
    cannot move a fraction of an element. One rank (`n == 1`) moves nothing.
    """
    if n < 1:
        raise fabric.FabricError(
            "n is %r: an all-reduce needs at least one rank" % (n,))
    if length < 0:
        raise fabric.FabricError(
            "length is %r: an all-reduce moves elements, not negative ones"
            % (length,))
    return length * (n - 1) // n


def within_bound(plan, length, n):
    """Whether the plan's largest per-rank send reaches the bound.

    The bound is a floor, not a ceiling: no plan can move *less* than
    `lower_bound(length, n)` elements in one direction, so the largest total a
    rank sends in `plan` must be at least it. A plan whose busiest rank sends
    fewer elements than that moves information that does not exist, and answers
    `False`. The comparison is between two `int`s: the per-rank totals are
    element counts, summed over that rank's outgoing transfers.
    """
    bound = lower_bound(length, n)
    sent = {}
    for transfer in plan.transfers:
        sent[transfer.src] = sent.get(transfer.src, 0) + transfer.length
    largest = max(sent.values()) if sent else 0
    return largest >= bound
