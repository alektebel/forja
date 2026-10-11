"""Distributed Training From Scratch — stage 8: Expert parallel (implementation).

The reasoning behind the routing, the two exchanges and the two statistics
lives in the template's docstring (`stage_08.py`); this file is only the body.
Nothing here is measured and nothing is random: the routing is a function of
the shape, the batch and the sequence, every number is an `int`, and two calls
return equal values.
"""

import fabric
import model
import plans

import stage_01 as stage1


#: The state a rank holds per parameter it owns: the bf16 parameter and its
#: gradient, the fp32 master weight and the two fp32 Adam moments — sixteen
#: bytes, priced exactly as stage 1's ledger prices them.
_STATE_BYTES_PER_PARAM = (model.PARAM_BYTES + model.PARAM_BYTES
                          + model.MASTER_BYTES + model.OPTIMIZER_BYTES)


def _count(value, what, minimum=1):
    """A whole count, or the refusal naming it. A `bool` is not a count."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise model.ModelError("%s=%r is not an int" % (what, value))
    if value < minimum:
        raise model.ModelError("%s=%d is below %d" % (what, value, minimum))
    return value


def _moe(shape, *, batch, seq):
    """`(experts, top_k, tokens)`, or the refusal naming the offender.

    A dense shape has no expert to route a token to, so it is refused naming
    `experts`; `tokens` is the number of tokens one rank's block holds, so the
    layer processes `experts * tokens` of them.
    """
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    if shape.experts < 1:
        raise model.ModelError(
            "shape has experts=%d: a dense FFN has no expert to route a token "
            "to, so it is not an expert-parallel layer" % (shape.experts,))
    batch = _count(batch, "batch")
    seq = _count(seq, "seq")
    return shape.experts, shape.top_k, batch * seq


def _hot_index(shape, hot):
    """The hot expert's index, checked, or `None` for the balanced routing."""
    if hot is None:
        return None
    _count(hot, "hot", 0)
    if hot >= shape.experts:
        raise model.ModelError(
            "hot=%d is not an expert of this model: experts=%d"
            % (hot, shape.experts))
    return hot


def _placements(experts, top_k, tokens, hot):
    """One source rank's row of the routing table, in placements per expert.

    Token `q` of the block takes the `top_k` experts `(q + k) % experts`, which
    are distinct because `top_k <= experts`; with `hot` the token's last choice
    becomes `hot` when the balanced choices do not already name it, so no token
    is ever listed twice and every token keeps exactly `top_k` experts.
    """
    row = [0] * experts
    for token in range(tokens):
        chosen = [(token + k) % experts for k in range(top_k)]
        if hot is not None and hot not in chosen:
            chosen[-1] = hot
        for expert in chosen:
            row[expert] += 1
    return tuple(row)


def _rows(routing):
    """The rank count of a square routing table, or the refusal naming it."""
    if not isinstance(routing, tuple) or not routing:
        raise model.ModelError(
            "routing=%r is not a non-empty tuple of rows" % (routing,))
    width = len(routing)
    for row in routing:
        if not isinstance(row, tuple) or len(row) != width:
            raise model.ModelError(
                "routing=%r is not a square table: row %r has %r columns, not %d"
                % (routing, row, len(row) if isinstance(row, tuple) else row,
                   width))
        for count in row:
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise model.ModelError(
                    "routing=%r holds %r, not a token count" % (routing, count))
    return width


def _capacity(placed, experts, capacity_factor):
    """The placements one (source, expert) cell may keep.

    `capacity_factor` times the table's own mean cell — `ceil_div(factor *
    placed, experts * experts)` — so the cap is a whole count and never a
    fraction of a token.
    """
    _count(capacity_factor, "capacity_factor")
    return model.ceil_div(capacity_factor * placed, experts * experts)


def routing(shape, *, batch, seq, hot=None):
    """The routing table: `routing[source][expert]` placements, as data.

    Rows are the group's ranks in rank order (rank `i` owns the `i`-th block of
    `batch * seq` tokens) and columns are the experts (one expert per rank), so
    the table is exactly the square `splits` table `plans.alltoall_from_splits`
    takes. Every row sums to `batch * seq * top_k`: a token is counted once per
    expert it reaches. Deterministic, and `hot` is an expert index.
    """
    experts, top_k, tokens = _moe(shape, batch=batch, seq=seq)
    hot = _hot_index(shape, hot)
    row = _placements(experts, top_k, tokens, hot)
    return tuple(row for _ in range(experts))


def dropped(routing, capacity_factor):
    """The placements the capacity cap refuses, summed over every cell."""
    rows = _rows(routing)
    placed = sum(sum(row) for row in routing)
    capacity = _capacity(placed, rows, capacity_factor)
    total = 0
    for row in routing:
        for count in row:
            if count > capacity:
                total += count - capacity
    return total


def balance_loss(routing):
    """The imbalance of the expert loads, as an exact integer.

    `experts * sum(load ** 2) - sum(load) ** 2` — the sum of the squared
    deviations from the mean load, scaled by the expert count so that no
    fraction of a token is ever needed. Zero exactly when every expert holds
    the same load; larger the more one expert carries.
    """
    rows = _rows(routing)
    loads = [sum(row[index] for row in routing) for index in range(rows)]
    return rows * sum(load * load for load in loads) - sum(loads) ** 2


def _busiest(splits):
    """The elements the busiest rank moves in one direction.

    The rank's own diagonal piece never leaves its expert, so it is excluded in
    both directions: what the exchange costs is the greatest total any one rank
    sends or takes in — the maximum over the ranks, never their mean.
    """
    rows = len(splits)
    busiest = 0
    for index in range(rows):
        kept = splits[index][index]
        sent = sum(splits[index]) - kept
        taken = sum(splits[other][index] for other in range(rows)) - kept
        busiest = max(busiest, sent, taken)
    return busiest


def _intake(splits):
    """The placements the busiest expert rank takes in: its column's load."""
    return max(sum(splits[other][index] for other in range(len(splits)))
               for index in range(len(splits)))


def _expert_params(shape):
    """One expert's bank: its `w1`, `w2` and `w3` of every layer, once."""
    return (sum(tensor.elements for tensor in shape.tensors()
                if ".expert." in tensor.name) // shape.experts)


def _scaled(splits, factor):
    """The same table with every count multiplied by `factor` elements."""
    return tuple(tuple(count * factor for count in row) for row in splits)


def expert_parallel(shape, world, *, batch, seq, capacity_factor=2, hot=None):
    """The MoE layer's exchange: the dispatch and the combine all-to-alls.

    One expert per rank of the world, `shape.top_k` experts per token. The
    dispatch moves every placement the routing names (the rank must hold the
    tokens it hands over); the combine moves back only what the experts kept,
    so the combine's table is exactly `dropped` placements smaller than the
    dispatch's. Each collective's length is the busiest rank's share, and the
    step owns no compute: the exchange is what this stage prices.
    """
    experts, top_k, tokens = _moe(shape, batch=batch, seq=seq)
    _count(capacity_factor, "capacity_factor")
    hot = _hot_index(shape, hot)
    group = tuple(world.ranks)
    if len(group) != experts:
        raise model.ModelError(
            "the world's %d ranks cannot hold the model's %d experts: expert "
            "parallel puts one expert per rank, so the group is the world and "
            "its size is the expert count" % (len(group), experts))
    table = routing(shape, batch=batch, seq=seq, hot=hot)
    placed = sum(sum(row) for row in table)
    capacity = _capacity(placed, experts, capacity_factor)
    kept = tuple(tuple(min(count, capacity) for count in row) for row in table)
    hidden = shape.hidden
    dispatch = _scaled(table, hidden)
    combine = tuple(tuple(kept[source][expert] * hidden
                          for source in range(experts))
                    for expert in range(experts))
    collectives = (
        stage1.Collective("ep", "dispatch", group, _busiest(dispatch),
                          "alltoall",
                          plans.alltoall_from_splits(world, group, dispatch)),
        stage1.Collective("ep", "combine", group, _busiest(combine),
                          "alltoall",
                          plans.alltoall_from_splits(world, group, combine)),
    )
    memory = (
        stage1.MemoryLine("expert_state", group,
                          _STATE_BYTES_PER_PARAM * _expert_params(shape)),
        stage1.MemoryLine("activations", group,
                          _intake(table) * hidden * fabric.ELEMENT_BYTES),
    )
    return stage1.StepPlan(collectives=collectives, compute=0, memory=memory)
