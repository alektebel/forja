"""Autograd From Scratch — stage 8: The kink (implementation)

The three operations below are the ones whose derivative is not a formula but a
*choice*: `max(a, b)` has no slope where the two operands meet, `relu` has none
at `0`, and `abs` has none at `0` either. Away from those points the derivative
is trivial — the gradient follows the operand that won, and `abs` flips its sign
— and at them the course has to say what happens, because a slope of `1/2`
(splitting the tie between the two sides), a slope of `0` (stopping the
gradient) and a slope of `1` (letting it through) are all defensible in the
abstract and only one of them is this course's.

The convention, stated once and used by all three: **on a tie the gradient goes
to the left operand**. `max(a, b)` hands `a` the factor `[a >= b]` and `b` the
factor `[a < b]` — one comparison, read from the operands' *values*, so the two
factors can never disagree about which side a tie went to, and a tie puts the
whole gradient in the left operand and the zeros in the right one. `relu(a)` is
`max(a, 0)` in value, and its kink is that same tie read from the constant's
side: `max(0, a)` puts the constant on the left, the tie hands the gradient to
the constant — which is no one's gradient — and `relu'(0) = 0`. `abs(a)` is
`relu(a) + relu(-a)`: right of `0` the first term carries the gradient, left of
it the second one does, and at `0` neither does, so its factor is
`[a > 0] - [a < 0]` — `+1`, `-1`, and `0` at the kink, the same rule read twice.
As factors of the *operand's value* — never of the incoming gradient, never of
the node's own value — the three are one shape of code:

    max   left `1[a >= b]`      right `1[a < b]`
    relu  `1[a > 0]`
    abs   `1[a > 0] - 1[a < 0]`

Everything else is stage 1's discipline over again. The forward is `exact`'s own
algebra (`exact.max` on the broadcast of the two operands, `exact.relu`,
`exact.abs`), so a stage's forward is provably right element for element before
any gradient is examined. The graph is stage 1's `Node`, imported rather than
declared a second time, so the gradients these operations leave on their
operands are the ones stage 1's `backward` walks and stage 1's `zero_grad`
clears. Every contribution is *added* to a node's `grad` and never assigned, and
a gradient's shape is its operand's shape: the factor is built in the node's own
shape and a `max` operand the broadcast stretched gets
`exact.reduce_gradient` called on its masked gradient — for the broadcast
operand only, because for an equal-shape operand the masked gradient is already
the answer. `relu'(0) = 0` is not a detail of one call: the `mlp` fixture's
pre-activations sit exactly on the kink, so the stage that splits the tie, or
sends the gradient through the constant, cannot reproduce
`fixtures.EXPECTED_LOSS` or `fixtures.REFERENCE_GRADIENTS`.

DESIGN DECISION — where does the gradient of a tied `max` go, and what is
`relu'(0)`?
    A tie has no derivative to speak of, so the course *chooses* a side and
    writes the choice down, the same way everywhere: the gradient goes to the
    **left operand**. `max`'s two factors therefore come from a single
    comparison — `a >= b` for the left operand, its negation for the right —
    because two independent comparisons (`a >= b` and `b >= a`) would both be
    true at a tie and hand the whole gradient to *both* operands, and a strict
    `>` on the left alone would hand it to the right one instead. `relu(a)` is
    `max(a, 0)` in value, and its kink is that tie read with the constant on the
    left: the gradient goes to the constant, no one takes the constant's
    gradient, and `relu'(0) = 0`. That is the factor `[a > 0]`, so a `relu` that
    lets a zero through — the `>=` spelling, in one call — disagrees with the
    `mlp` fixture, whose pre-activations are exactly `0`, and with every other
    kink in this file.

DESIGN DECISION — why is the factor read from the operands' values and never
from the incoming gradient?
    The local derivative is a property of the *operation at the operands' point*
    — which side of the kink the forward pass was on — and the incoming gradient
    is a different number entirely: it is whatever the rest of the graph sent
    back, and it is routinely negative, larger than the operands, or zero. A
    factor computed from it (`mask(gradient)`) is a function of the wrong thing:
    it happens to agree on a fixture whose seed is `ones` and whose operands sit
    at `0` and `1`, and it disagrees the moment the seed is negative or the
    operands are fractions — silently, because the shape and the type are still
    right. The factor is also read from the *operand's* value and not from the
    node's own value: for `abs` those differ on exactly the half of the domain
    that carries the sign, and a mask read from `|x|` gives `+1` where the
    derivative is `-1`.

DESIGN DECISION — why does a `max` operand's masked gradient go through
`exact.reduce_gradient`, and only when it was broadcast?
    `exact.max` broadcasts, so a `(2, 3)` and a `(3,)` produce a `(2, 3)` node;
    both operands' factors live at the output's elements, and the masked
    gradient is therefore born in the output's shape. The `(3,)` operand is owed
    a `(3,)` gradient (§3 invariant 2), which is its masked gradient summed over
    the rows the broadcast stretched — `exact.reduce_gradient`'s whole job, the
    provided half of stage 3. The equal-shape operand must *not* be reduced: its
    masked gradient is already its own shape, and summing it would be summing a
    gradient that was never stretched. Building the masked gradient in the
    output's shape and handing it to the `(3,)` operand unreduced is the defect
    this call exists to prevent, and it is invisible on a fixture whose two
    operands have the same shape.

DESIGN DECISION — why are `relu` and `abs` their own factors instead of
`max` nodes over a constant?
    `relu(a)` could have been written as a `max` of the operand node and a leaf
    holding zeros, and then the tie rule would have decided its kink for it —
    but a constant is not an operand anyone differentiates, and a leaf would put
    a node in every graph that the backward must walk and `zero_grad` must
    clear. Worse, the node's value would then be `exact.max`'s, and this stage's
    forward must be `exact.relu`/`exact.abs` element for element. So each
    operation carries its own factor, and the convention lives in one place: the
    factor of `relu` is `[a > 0]` and the factor of `abs` is `[a > 0] - [a < 0]`
    — the same reading of the same tie, in the same file.

DESIGN DECISION — why does a local backward refuse a gradient that is not a
`Tensor` of the node's shape?
    The gradient a local backward receives is the node's accumulated gradient:
    a `Tensor` of the node's value's shape, and nothing else. A masked gradient
    is an elementwise product with that tensor, so a gradient of another shape
    has no element to be masked at — and `exact`'s elementwise operations would
    *broadcast* it rather than refuse it, silently pairing the wrong cells and
    answering with a gradient of the wrong shape. The refusal names the
    operation and both shapes, the §1 way, so the caller sees a wrong seed or a
    wrong edge instead of a plausible number.
"""

import exact

from stage_01 import Node


_ZERO = exact.Rational(0)
_ONE = exact.Rational(1)
_NEGATIVE_ONE = exact.Rational(-1)


def _tie_to_the_left(left, right):
    """`max`'s local factor at one output element, read from the two operands'
    values there.

    One comparison decides both factors: the left operand keeps the whole
    gradient where it is greater than or equal to the right one, and the right
    operand keeps it where it is strictly smaller. The `>=` *is* the convention
    — the tie belongs to the left operand — and because the right factor is its
    negation rather than a second comparison, a tie cannot land on both operands
    at once.
    """
    if left >= right:
        return _ONE, _ZERO
    return _ZERO, _ONE


def _relu_keep(value):
    """`relu`'s local factor at one element, read from the operand's value:
    `1` where the value is strictly positive, `0` everywhere else — so
    `relu'(0) = 0`, the tie at the kink being the constant's and not the
    value's.
    """
    return _ONE if value > _ZERO else _ZERO


def _abs_keep(value):
    """`abs`'s local factor at one element, read from the operand's value:
    `+1` to the right of `0`, `-1` to the left of it and `0` at it. The sign of
    the operand, and the same rule `relu` follows at its own kink — both are
    zero exactly where the operand is zero.
    """
    if value > _ZERO:
        return _ONE
    if value < _ZERO:
        return _NEGATIVE_ONE
    return _ZERO


def _cells(shape):
    """The number of cells a shape describes, `1` for the empty shape — the
    same figure `exact.Tensor.size` reports for a tensor of that shape, without
    building one to ask."""
    total = 1
    for dim in shape:
        total *= dim
    return total


def _checked_gradient(op, gradient, shape):
    """The gradient a local backward was handed, once it is a `Tensor` of the
    node's own shape; anything else is refused, naming the operation and both
    shapes.

    `exact`'s elementwise operations broadcast rather than refuse, so a gradient
    of another shape would be paired with the wrong cells and would come back as
    a plausible gradient of the wrong shape (§3 invariant 2): the check is
    cheaper than the hunt for that number.
    """
    if not isinstance(gradient, exact.Tensor):
        raise exact.AutogradError(
            "%s: the gradient %r is not an exact.Tensor" % (op, gradient))
    if gradient.shape != shape:
        raise exact.AutogradError(
            "%s: gradient shape %r and node shape %r do not match: %d and %d"
            % (op, gradient.shape, shape, gradient.size, _cells(shape)))
    return gradient


def _binary(op, a, b, forward, keep):
    """One elementwise node over two `Node` operands of broadcastable shapes:
    the operand guards, `forward`'s value, and the local backward that masks the
    incoming gradient elementwise and accumulates each operand's share.

    `keep(left_cell, right_cell)` is the pair of factors the two operands keep
    at one output element; the factors are read from the operands' values
    broadcast to the node's shape, the masked gradient is reduced back to an
    operand's shape only where the broadcast stretched it, and every
    contribution is *added* to the operand's `grad`.
    """
    if not isinstance(a, Node):
        raise exact.AutogradError("%s: a=%r is not a Node" % (op, a))
    if not isinstance(b, Node):
        raise exact.AutogradError("%s: b=%r is not a Node" % (op, b))
    value = forward(a.value, b.value)
    shape = value.shape
    left_values = exact.broadcast_to(a.value, shape).cells
    right_values = exact.broadcast_to(b.value, shape).cells

    def backward_of_op(gradient):
        gradient = _checked_gradient(op, gradient, shape)
        left_cells = []
        right_cells = []
        for index, cell in enumerate(gradient.cells):
            keep_left, keep_right = keep(left_values[index], right_values[index])
            left_cells.append(cell * keep_left)
            right_cells.append(cell * keep_right)
        left_grad = exact.Tensor(tuple(left_cells), shape)
        right_grad = exact.Tensor(tuple(right_cells), shape)
        if a.value.shape != shape:
            left_grad = exact.reduce_gradient(left_grad, a.value.shape)
        if b.value.shape != shape:
            right_grad = exact.reduce_gradient(right_grad, b.value.shape)
        a.grad = exact.add(a.grad, left_grad)
        b.grad = exact.add(b.grad, right_grad)

    return Node(value, parents=(a, b), backward=backward_of_op)


def _unary(op, a, forward, keep):
    """One elementwise node over one `Node` operand: the operand guard,
    `forward`'s value, and the local backward that masks the incoming gradient
    with the operand's own values.

    `keep(cell)` is the factor the operand keeps at one element. The node's
    shape is the operand's, so the masked gradient is already the answer — no
    reduction, and a contribution that is *added* to the operand's `grad`.
    """
    if not isinstance(a, Node):
        raise exact.AutogradError("%s: a=%r is not a Node" % (op, a))
    value = forward(a.value)
    shape = value.shape
    values = a.value.cells

    def backward_of_op(gradient):
        gradient = _checked_gradient(op, gradient, shape)
        cells = []
        for index, cell in enumerate(gradient.cells):
            cells.append(cell * keep(values[index]))
        a.grad = exact.add(a.grad, exact.Tensor(tuple(cells), shape))

    return Node(value, parents=(a,), backward=backward_of_op)


def max(a, b):
    """`max(a, b)`, elementwise: one node whose value is `exact.max`'s and whose
    local backward hands each operand its share of the gradient.

    The value is `exact.max` of the two operands, so it broadcasts the way
    `exact.max` does and it is `exact`'s own figure element for element. The
    factors come from `_tie_to_the_left`: the left operand keeps the gradient
    where it is `>=` the right one and the right operand where it is `<`, so on
    a tie the whole gradient goes to the **left** operand — the course's
    convention, stated once — and never to both. A `(2, 3)` left operand against
    a `(3,)` right one owes each of them a gradient of its own shape: the
    `(3,)` operand's masked gradient is summed back over the two rows by
    `exact.reduce_gradient`, and an equal-shape operand is not reduced at all,
    its masked gradient being already its own shape. A pair of shapes that do
    not broadcast is refused by `exact.max` itself, naming both shapes and both
    numbers, and an operand that is not a `Node` is refused here, naming the
    offender.
    """
    return _binary("max", a, b, exact.max, _tie_to_the_left)


def relu(a):
    """`relu(a) = a if a > 0 else 0`, elementwise: one node whose value is
    `exact.relu`'s and whose local backward masks the gradient with `[a > 0]`.

    The kink is this stage's tie seen from the constant's side — `relu(a)` is
    `max(a, 0)`, and the tie at `a == 0` goes to the constant, whose gradient no
    one asks for — so `relu'(0) = 0`: a zero input keeps zero of the gradient,
    and so does every negative one. `abs` and `relu` agree at `0` because they
    are the same rule: the factor is zero exactly where the operand is.
    """
    return _unary("relu", a, exact.relu, _relu_keep)


def abs(a):
    """`abs(a)`, elementwise: one node whose value is `exact.abs`'s and whose
    local backward multiplies the gradient by the operand's sign.

    `d|a|/da` is `+1` to the right of `0`, `-1` to the left of it and `0` at it —
    `abs(a)` is `relu(a) + relu(-a)`, whose two terms meet at `0`, and there the
    gradient goes nowhere rather than half to each side. Read as a factor of the
    operand's value it is `[a > 0] - [a < 0]`, which is the same reading of the
    same tie `relu` uses, so `abs(0)` and `relu(0)` carry the same gradient:
    none.
    """
    return _unary("abs", a, exact.abs, _abs_keep)
