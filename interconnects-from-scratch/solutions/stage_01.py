"""Interconnects From Scratch — stage 1: The link and the fabric (implementation).

The reasoning behind the cost model lives in the template's docstring
(`stage_01.py`); this file is only the body. Nothing here is measured: a tick
count is computed from the plan and the topology, and every number is an `int`.
"""

import fabric

#: How many bytes one element of a buffer is worth. It mirrors
#: `fabric.ELEMENT_BYTES`; the cost model charges bytes, and this is the only
#: place a length in elements becomes a size in bytes.
BYTES_PER_ELEMENT = fabric.ELEMENT_BYTES


def hop_count(topology, a, b):
    """The number of hops on the shortest route from `a` to `b`."""
    return topology.distance(a, b)


def transfer_ticks(topology, transfer):
    """What one transfer costs: every hop of its route, latency and byte time."""
    hops = topology.hops_of(transfer)
    if hops is None:
        raise fabric.FabricError(
            "transfer %r cannot be routed on %s" % (transfer, topology))
    size = BYTES_PER_ELEMENT * transfer.length
    ticks = 0
    for link in hops:
        ticks += link.latency + fabric.ceil_div(size, link.bandwidth)
    return ticks


def step_ticks(topology, plan, step):
    """What one step costs: its slowest transfer, or nothing if it is empty."""
    transfers = plan.at(step)
    if not transfers:
        return 0
    return max(transfer_ticks(topology, transfer) for transfer in transfers)


def plan_ticks(topology, plan):
    """What the whole plan costs: the sum of the steps' costs."""
    steps = plan.steps()
    if not steps:
        return 0
    return sum(step_ticks(topology, plan, step) for step in steps)


def bytes_by_link(topology, plan):
    """Bytes carried by each undirected link, over the whole plan."""
    carried = {}
    for transfer in plan.transfers:
        hops = topology.hops_of(transfer)
        if hops is None:
            raise fabric.FabricError(
                "transfer %r cannot be routed on %s" % (transfer, topology))
        size = BYTES_PER_ELEMENT * transfer.length
        for link in hops:
            carried[link] = carried.get(link, 0) + size
    return carried


def bytes_per_rank(topology, plan):
    """Bytes each rank handled: what it sent plus what it received."""
    handled = {rank: 0 for rank in topology.ranks}
    for transfer in plan.transfers:
        size = BYTES_PER_ELEMENT * transfer.length
        handled[transfer.src] += size
        handled[transfer.dst] += size
    return handled


def validate(topology, plan):
    """Refuse a plan the fabric could not run, naming the offender."""
    known = topology.ranks
    for transfer in plan.transfers:
        for rank in (transfer.src, transfer.dst):
            if rank not in known:
                raise fabric.FabricError(
                    "transfer %r names unknown rank %r" % (transfer, rank))
    for transfer in plan.transfers:
        if transfer.src == transfer.dst:
            raise fabric.FabricError(
                "transfer %r sends to itself" % (transfer,))
        if transfer.length <= 0:
            raise fabric.FabricError(
                "transfer %r has length %r, not a positive number of elements"
                % (transfer, transfer.length))
        if transfer.offset < 0:
            raise fabric.FabricError(
                "transfer %r has a negative offset" % (transfer,))
    limit = getattr(plan, "length", None)
    if limit is not None:
        for transfer in plan.transfers:
            start, end = transfer.slice()
            if end > limit:
                raise fabric.FabricError(
                    "transfer %r slices [%d:%d] past the %d-element buffer"
                    % (transfer, start, end, limit))
    for transfer in plan.transfers:
        if topology.path(transfer.src, transfer.dst) is None:
            raise fabric.FabricError(
                "transfer %r cannot be routed on %s" % (transfer, topology))
    for step in plan.steps():
        carriers = {}
        for transfer in plan.at(step):
            route = topology.path(transfer.src, transfer.dst)
            if route is None:
                continue
            for index in range(len(route) - 1):
                link = topology.link(route[index], route[index + 1])
                key = (link.a, link.b, route[index], route[index + 1])
                carriers.setdefault(key, []).append(transfer)
        for key in sorted(carriers):
            if len(carriers[key]) > 1:
                raise fabric.FabricError(
                    "step %d carries %d transfers from %s to %s in the same "
                    "direction" % (step, len(carriers[key]), key[2], key[3]))
    return None
