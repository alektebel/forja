"""Distributed Training From Scratch — stage 5: Tensor parallel (implementation).

The reasoning behind the two halves, the block's two all-reduces and the choice
of algorithm lives in the template's docstring (`stage_05.py`); this file is
only the body. Every number is an `int`, on the fixture matrices and in the
plan, and two calls with equal arguments return equal values.
"""

import fabric
import model
import plans
import stage_01

#: The all-reduce candidates `plans.py` can build, in the order ties are broken.
_ALGORITHMS = ("ring", "tree", "doubling")


def _positive(value, what):
    """A positive whole count, or the refusal naming it.

    A `bool` is an `int` and not a count, and neither is a string: a token count
    that is not a positive whole number cannot size an activation.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise model.ModelError("%s=%r is not a positive int" % (what, value))
    return value


def _rows(value, what):
    """`(rows, width)`: a non-empty tuple of equal-length `int` rows, or the
    refusal naming `what`.

    The rule `model`'s own calculus applies to a matrix: rows are tuples of
    equal length, every entry is an `int`, and a `bool` is not one.
    """
    if not isinstance(value, tuple) or not value:
        raise model.ModelError("%s=%r is not a non-empty tuple of rows" % (what, value))
    width = None
    for row in value:
        if not isinstance(row, tuple) or not row:
            raise model.ModelError(
                "%s=%r has a row that is not a tuple" % (what, value))
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise model.ModelError(
                "%s=%r has rows of different lengths" % (what, value))
        for item in row:
            if isinstance(item, bool) or not isinstance(item, int):
                raise model.ModelError(
                    "%s=%r holds a non-int element" % (what, value))
    return value, width


def _contract(x, w):
    """`y[i][j] = sum_k x[i][k] * w[j][k]`: the column half's matmul, one row of
    the answer per row of `w`."""
    rows, inner = _rows(x, "x")
    w_rows, w_inner = _rows(w, "w")
    if w_inner != inner:
        raise model.ModelError(
            "w inner=%d does not match x inner=%d" % (w_inner, inner))
    return tuple(tuple(sum(rows[i][k] * w_rows[j][k] for k in range(inner))
                       for j in range(len(w_rows)))
                 for i in range(len(rows)))


def _contract_columns(partial, w):
    """`y[i][j] = sum_k partial[i][k] * w[k][j]`: the row half's matmul, one row
    of `w` per input feature."""
    rows, inner = _rows(partial, "partial")
    w_rows, out = _rows(w, "w")
    if len(w_rows) != inner:
        raise model.ModelError(
            "w has %d rows, but partial has %d columns" % (len(w_rows), inner))
    return tuple(tuple(sum(rows[i][k] * w_rows[k][j] for k in range(inner))
                       for j in range(out))
                 for i in range(len(rows)))


def column_parallel(x, w):
    """The block's first half: one rank's slice of the projection's output.

    The full input against the rank's own rows of the weight — the rank's
    columns of the projection, a disjoint slice no other rank holds and no
    collective has to combine.
    """
    return _contract(x, w)


def row_parallel(partial, w):
    """The block's second half: one rank's **partial** output.

    The rank's shard of the intermediate contracted against the rank's own rows
    of the second weight (one row per input feature the rank owns). The answer
    is a partial sum over the whole output; the group's all-reduce is what
    combines it.
    """
    return _contract_columns(partial, w)


def f(x, w):
    """The block's first half under the name the fixture composes."""
    return column_parallel(x, w)


def g(x, w):
    """The block's second half under the name the fixture composes."""
    return row_parallel(x, w)


def _build(world, group, elements, algorithm):
    """The named candidate's plan from `plans.py`, or that candidate's own
    refusal."""
    if algorithm == "ring":
        return plans.ring_allreduce(world, group, elements)
    if algorithm == "tree":
        return plans.tree_allreduce(world, group, elements)
    return plans.doubling_allreduce(world, group, elements)


def _cheapest(world, group, elements):
    """`(algorithm, plan)`: the cheapest all-reduce `plans.py` builds here.

    Every candidate in `_ALGORITHMS` is built and priced with
    `stage_01.plan_ticks` on the group's **own** fabric — the links the group
    owns, not the world's routes through ranks it does not have — and the
    smallest total wins, a tie going to the earlier name in `_ALGORITHMS`. A
    candidate whose own preconditions fail is dropped, not raised: the butterfly
    that needs a one-hop XOR partner is simply not a candidate on a ring or
    across a two-level spine, and the answer is a function of the plans that fit
    rather than of the fabric's name. A group where nothing fits is refused.
    """
    topology = plans.group_fabric(world, group)
    best = None
    for algorithm in _ALGORITHMS:
        try:
            plan = _build(world, group, elements, algorithm)
        except fabric.FabricError:
            continue
        ticks = stage_01.plan_ticks(topology, plan)
        if best is None or ticks < best[0]:
            best = (ticks, algorithm, plan)
    if best is None:
        raise fabric.FabricError(
            "no all-reduce fits %s at %d elements: the ring needs a length its "
            "chunking divides, the tree a route to the group's root, and the "
            "butterfly a power-of-two group whose XOR partners are neighbours"
            % (topology, elements))
    return best[1], best[2]


def tensor_parallel(shape, world, *, group, batch=1, seq=1):
    """One MLP block's `StepPlan`: its two all-reduces, in the order it issues
    them.

    The block is split over `group`; the tensor at the row-parallel boundary is
    `batch * seq * hidden` elements per rank. The forward all-reduce combines
    the row half's partials into the projection's output; the backward's
    combines the column half's gradient partials. `batch` and `seq` default to a
    single token, so the plan of a one-token step is `tensor_parallel(shape,
    world, group=group)`. A group of one rank means the block is not split at
    all, and issues nothing.
    """
    if not isinstance(shape, model.ModelShape):
        raise model.ModelError("shape=%r is not a ModelShape" % (shape,))
    _positive(batch, "batch")
    _positive(seq, "seq")
    members = plans.group_ranks(world, group)
    if len(members) == 1:
        return stage_01.StepPlan(collectives=(), compute=0, memory=())
    elements = batch * seq * shape.hidden
    algorithm, plan = _cheapest(world, members, elements)
    forward = stage_01.Collective(
        "tp", "activations", members, elements, algorithm, plan)
    backward = stage_01.Collective(
        "tp", "grads", members, elements, algorithm, plan)
    return stage_01.StepPlan(collectives=(forward, backward), compute=0, memory=())
