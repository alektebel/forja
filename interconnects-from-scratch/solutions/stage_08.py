"""Interconnects From Scratch — stage 8: Send, recv and groups (implementation).

The reasoning behind the group lives in the template's docstring
(`stage_08.py`); this file is only the body. A group is one launch: every
exchange lands in step 0, the step's slowest transfer is its price, and the
fabric's full-duplex rule — one transfer per *directed* link per step — decides
which exchanges may share the step. Nothing here is measured, and every number
is an `int`.
"""

import fabric

import stage_01


def sendrecv(topology, exchanges):
    """A group as one plan: every exchange lands in step 0."""
    transfers = []
    occupied = {}
    for exchange in exchanges:
        src, dst, offset, length = exchange
        if src == dst:
            raise fabric.FabricError(
                "stage 8: exchange %r sends %s to itself" % (exchange, src))
        for rank in (src, dst):
            if rank not in topology.ranks:
                raise fabric.FabricError(
                    "stage 8: exchange %r names unknown rank %r" % (exchange, rank))
        if length <= 0:
            raise fabric.FabricError(
                "stage 8: exchange %r has length %r, not a positive one"
                % (exchange, length))
        if offset < 0:
            raise fabric.FabricError(
                "stage 8: exchange %r has offset %r, not a non-negative one"
                % (exchange, offset))
        route = topology.path(src, dst)
        if route is None:
            raise fabric.FabricError(
                "stage 8: exchange %r cannot be routed on %s" % (exchange, topology))
        for hop in range(len(route) - 1):
            key = (route[hop], route[hop + 1])
            if key in occupied:
                raise fabric.FabricError(
                    "stage 8: exchange %r and exchange %r both cross %s -> %s in "
                    "step 0, and a directed link carries one transfer per step"
                    % (occupied[key], exchange, key[0], key[1]))
            occupied[key] = exchange
        transfers.append(fabric.send(src, dst, length, 0, offset=offset))
    return fabric.Plan(transfers=tuple(transfers))


def group_ticks(topology, exchanges):
    """The price of the group as one launch: the slowest transfer of step 0."""
    plan = sendrecv(topology, exchanges)
    transfers = plan.at(0)
    if not transfers:
        return 0
    ticks = 0
    for transfer in transfers:
        cost = stage_01.transfer_ticks(topology, transfer)
        if cost > ticks:
            ticks = cost
    return ticks
