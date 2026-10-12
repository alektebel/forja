"""Autograd From Scratch — stage 3: Broadcasting and the reduction (implementation)

The forward is `exact`'s own algebra — `exact.add`, `exact.sub`, `exact.mul`
broadcast their two operands, `exact.sum` and `exact.mean` reduce one axis or
all of them — so every node's value here is the provided forward element for
element, and the whole of the exercise is the backward of a *shape change*.

There are two of them, and they are inverse moves of the same axis. A binary
node's local derivative is stated per element of the *output*: its
contribution is born in the output's shape, and an operand the broadcast
stretched is owed that contribution summed over every axis the broadcast
stretched — `exact.reduce_gradient(contribution, operand.shape)`, called for
that operand only, because for an equal-shape operand the contribution is
already its own shape. A reduction removes an axis: its gradient arrives with
the axis removed and the operand is owed the axis put back as an extent `1`
(whence `exact.reshape`, which accepts a rank-`n + 1` target of the same size)
and stretched (`exact.broadcast_to`). `mean` is that expansion scaled by the
exact `Rational(1, n)` of the extent it averaged — an exact rational, never a
float, never `//`.

The container is stage 1's `Node` and the walk is stage 1's `backward`, so a
value or gradient built here is the same object the rest of the engine walks;
every contribution is *added* to a node's `grad` and never assigned, and every
gradient's shape is its operand's, not the output's and not the broadcast's
(§3 invariants 2 and 3). No float appears anywhere and no comparison has a
tolerance: a gradient is a `Tensor` of `Rational`s and it is compared with `==`
as pairs.

DESIGN DECISION — why is `exact.reduce_gradient` called for the broadcast
operand only?
    A local derivative is stated per element of the *output*, so `mul`'s left
    contribution — the gradient times the right operand, read at each output
    element — is born in the output's shape whatever the left operand's shape
    is. For an operand the broadcast stretched, one of its cells carries the sum
    of several output contributions and `reduce_gradient` is what sums them;
    for an equal-shape operand the contribution *is* the answer. The temptation
    is to reduce everything, because `reduce_gradient(gradient, shape)` with
    `gradient.shape == shape` returns its argument unchanged: the call is
    invisible, the shapes are all still right, and the engine is wrong only on
    the calls where the broadcast actually happened. `_reduce` therefore takes
    the decision in one place, on the two shapes, and the check spies on
    `exact.reduce_gradient` to prove that an equal-shape operand never reaches
    it.

DESIGN DECISION — why does `sum`'s backward re-insert the axis instead of
reshaping straight to the operand's shape?
    `sum(t, axis)` with `t` of shape `(3, 4)` and `axis=1` is a `(3,)`: one
    output cell is the sum of four operand cells, so all four of them keep the
    whole of that gradient and the operand's gradient is the seed repeated along
    the summed axis. Shape-wise the output is the operand with an axis removed,
    so the operand's size is `extent` times the output's and a `reshape` of the
    gradient directly into the operand's shape would refuse on the size. Dropping
    the extent `1` axis back in — `shape[:axis] + (1,) + shape[axis + 1:]`, a
    rank-`n + 1` target of the same size — and then stretching it with
    `exact.broadcast_to` is the only exact spelling, and it is `sum`'s own
    broadcast read backwards. `axis=None` is the same move at full rank: the
    reduction is a scalar and the gradient is the scalar broadcast to every
    cell. Inserting the axis in the wrong place, or always in the last one, is a
    defect only a seed with distinct cells can see.

DESIGN DECISION — why is the axis validated against the operand's shape and
normalized here?
    An axis names an axis of the *operand*, never of the reduction: `sum(t,
    axis=1)` on a `(2, 3)` is a valid call whose result has shape `(2,)`, so
    validating against the result would refuse the call the stage exists for.
    Normalizing is also what refuses the axis the operand does not have: the
    `%` that wraps a negative axis wraps an out-of-range positive one onto a
    valid axis as well (`2 % 2` is `0` on a rank-2 tensor), so the bounds check
    has to come first and it has to reject `axis >= rank`, not `axis > rank`.
    The *normalized* axis is what the forward and the expansion are both given,
    so a negative axis and its positive twin cannot land on two different axes:
    `-1` is the last axis of the operand in the value and in the gradient alike.

DESIGN DECISION — why does `mean`'s gradient carry the exact `1/n`?
    `mean(t, axis)` is `sum(t, axis) / n` with `n` the extent that was summed —
    `t.size` for `axis=None` and `shape[axis]` otherwise — so its backward is
    `sum`'s expansion multiplied by exactly `Rational(1, n)`. It is the extent
    of *that* call: an implementation that reaches for the whole size is right
    on `axis=None`, right on a rank-1 tensor, and off by an exact rational
    factor on every other call, which is why the probes seed a `rank-2` and a
    `rank-3` tensor and check the pairs. Dropping the scale altogether leaves a
    gradient that is `n` times too large and `sum`'s written twice — a defect
    invisible on a fixture whose seed is chosen so the missing factor cancels.
    There is no float here and no `//`: `1/n` is a `Rational` and the product is
    exact.

DESIGN DECISION — why is the reduction's local backward built from
`exact.reshape` and `exact.broadcast_to` rather than by hand?
    A backward is a forward of shapes: putting back an axis is `reshape` plus a
    stretch, which is exactly the pair of provided operations that already
    refuse a size that does not match or a shape that cannot be reached, each
    naming both shapes and both numbers. Hand-writing the index arithmetic for
    the expansion would be a second implementation of `broadcast_to` — the one
    place in this course where a plausible index bug (`extent` used as `1`, an
    axis counted from the wrong end, an off-by-one in the insertion) produces a
    gradient of the right shape with the wrong cells. It also keeps the stage's
    own code small enough to read against the two moves it makes: reduce a
    broadcast contribution back, expand a removed axis.

DESIGN DECISION — why does this stage import stage 1's `Node` instead of
declaring its own?
    The engine has one `Node`, one `backward` and one `zero_grad`, and a second
    container here would build graphs the walk cannot enter: `stage_01.backward`
    walks `parents` and accumulates into `grad`, so the node `add` returns must
    be *that* node. The forward is `exact`'s and the container is stage 1's;
    what this file adds is the pair of shape moves that make a broadcast
    differentiable, on top of everything stage 1 and 2 already established —
    accumulation and never assignment (§3.3), and a gradient whose shape is its
    operand's (§3.2).
"""

import exact
import stage_01


def _operand(op, name, node):
    """One operand that is a `stage_01.Node`, or the refusal naming it."""
    if not isinstance(node, stage_01.Node):
        raise exact.AutogradError(
            "%s: %s=%r is not a Node" % (op, name, node))
    return node


def _reduce(contribution, shape, output_shape):
    """`contribution` back to the shape it is owed to: `exact.reduce_gradient`
    for an operand the broadcast stretched, and the contribution itself when
    the operand's shape is already the output's.

    The guard is the whole point of the stage. `reduce_gradient` returns its
    argument unchanged when the two shapes agree, so calling it unconditionally
    would be invisible on every equal-shape call and would sum a gradient that
    was never stretched the moment a `(4,)` meets a `(3, 4)`.
    """
    if shape == output_shape:
        return contribution
    return exact.reduce_gradient(contribution, shape)


def _binary(op, a, b, forward, local):
    """One elementwise binary node over two `Node` operands of broadcastable
    shapes: the operand guards, `forward`'s value, and the local backward that
    reduces each contribution back to its own operand's shape and accumulates
    it there.

    `local(gradient, left_value, right_value)` is the local derivative read at
    the output's elements — it returns both contributions in the node's shape —
    and `_reduce` is what brings each one back to the operand it belongs to.
    """
    _operand(op, "a", a)
    _operand(op, "b", b)
    value = forward(a.value, b.value)
    shape = value.shape
    left_shape = a.value.shape
    right_shape = b.value.shape

    def backward_of_op(gradient):
        left, right = local(gradient, a.value, b.value)
        a.grad = exact.add(a.grad, _reduce(left, left_shape, shape))
        b.grad = exact.add(b.grad, _reduce(right, right_shape, shape))

    return stage_01.Node(value, parents=(a, b), backward=backward_of_op)


def add(a, b):
    """`a + b`, elementwise over operands of broadcastable shapes: `exact.add`'s
    value, and the incoming gradient handed to both operands — reduced back to
    each operand's own shape when the broadcast stretched it.

    The derivative of a sum is one for each addend, so the pair of
    contributions is `(gradient, gradient)`; a `(3, 4)` node against a `(4,)`
    operand owes the `(4,)` the gradient summed over the three rows, and the
    `(3, 4)` operand the gradient itself.
    """
    return _binary("add", a, b, exact.add,
                   lambda gradient, left, right: (gradient, gradient))


def sub(a, b):
    """`a - b`, elementwise over operands of broadcastable shapes: `exact.sub`'s
    value, the gradient to `a` and its negation to `b`, each reduced back to
    its own operand's shape.

    `d(a - b)/db` is `-1`, and the sign is the whole content of the operation:
    a subtrahend handed `+gradient` cancels a fixture whose contributions are
    opposite and is invisible on one whose shapes are equal.
    """
    return _binary("sub", a, b, exact.sub,
                   lambda gradient, left, right: (gradient, exact.neg(gradient)))


def mul(a, b):
    """`a * b`, elementwise over operands of broadcastable shapes: `exact.mul`'s
    value, and each operand handed the gradient times the *other* one — the
    contribution born in the node's shape, reduced back to the operand's own.

    `d(a * b)/da` is `b` read at the output's elements, so an operand the
    broadcast stretched owes the sum of its cells' contributions over the
    stretched axes: `exact.mul(gradient, right)` is in the node's shape and
    `_reduce` brings it to the left operand's. Two operands the wrong way round
    on one side of the pair leaves a gradient that is right only on a fixture
    whose two operands are equal in value.
    """
    return _binary("mul", a, b, exact.mul,
                   lambda gradient, left, right: (exact.mul(gradient, right),
                                                  exact.mul(gradient, left)))


def _axis_of(op, axis, shape):
    """A normalized in-range axis of the *operand's* `shape`, or the refusal
    naming the operation, the axis, the rank and the shape.

    `axis=None` stays `None` (every axis is summed). A non-int — a `bool`
    included — is refused by name, and so is an axis below `-rank` or at or
    above `rank`: the `%` below would fold an out-of-range positive axis onto a
    valid one, so the bounds are checked before it is applied.
    """
    if axis is None:
        return None
    if isinstance(axis, bool) or not isinstance(axis, int):
        raise exact.ExactError("%s: axis=%r is not an int" % (op, axis))
    if len(shape) == 0 or axis < -len(shape) or axis >= len(shape):
        raise exact.ExactError(
            "%s: axis=%d is outside the %d axes of shape=%r"
            % (op, axis, len(shape), shape))
    return axis % len(shape)


def _expand(gradient, shape, axis):
    """`gradient` — a reduction's own gradient — re-read in the operand's
    `shape`: the summed axis put back as an extent `1` and stretched.

    `axis` is already normalized (`None` for a reduction over every axis, in
    which case the whole rank is put back). The extent `1` axis is inserted
    where the summed axis was, so `exact.reshape` has a target of the same size
    as the gradient, and `exact.broadcast_to` repeats each cell over every
    offset the axis has in `shape`.
    """
    if axis is None:
        carried = exact.reshape(gradient, (1,) * len(shape))
    else:
        carried = exact.reshape(gradient, shape[:axis] + (1,) + shape[axis + 1:])
    return exact.broadcast_to(carried, shape)


def sum(t, axis=None):
    """The sum of `t`, over one axis or over every axis: `exact.sum`'s value,
    and the gradient put back along the axis that was summed away.

    The axis is validated and normalized against the operand's shape, and the
    *normalized* axis is what the forward and the expansion both see, so a
    negative axis lands where its positive twin lands. The operand's `grad`
    grows by the expanded gradient — a node reached by two paths gets two
    contributions — and every axis the operand does not have is refused naming
    the axis and the shape.
    """
    _operand("sum", "t", t)
    shape = t.value.shape
    normalized = _axis_of("sum", axis, shape)
    value = exact.sum(t.value, normalized)

    def backward_of(gradient):
        t.grad = exact.add(t.grad, _expand(gradient, shape, normalized))

    return stage_01.Node(value, parents=(t,), backward=backward_of)


def mean(t, axis=None):
    """The exact mean of `t`: `exact.mean`'s value, and `sum`'s expansion
    scaled by the exact `Rational(1, n)` of the extent that was averaged.

    `n` is `t.size` for `axis=None` and the extent of the named axis otherwise.
    The scale is applied to the *expanded* gradient, so the operand's `grad` has
    the operand's shape and the cells of one reduced cell all carry `1/n` of it.
    An empty axis is refused by `exact.mean` itself, which names the axis and
    the shape — never a division by zero and never a float.
    """
    _operand("mean", "t", t)
    shape = t.value.shape
    normalized = _axis_of("mean", axis, shape)
    value = exact.mean(t.value, normalized)
    extent = t.value.size if normalized is None else shape[normalized]
    scale = exact.full(shape, exact.Rational(1, extent))

    def backward_of(gradient):
        t.grad = exact.add(t.grad, exact.mul(_expand(gradient, shape, normalized),
                                             scale))

    return stage_01.Node(value, parents=(t,), backward=backward_of)
