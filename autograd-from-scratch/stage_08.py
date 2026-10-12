"""Autograd From Scratch — stage 8: The kink

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
    **left operand**. `max`'s two factors therefore have to come from a single
    comparison — `a >= b` for the left operand, its negation for the right —
    because two independent comparisons (`a >= b` and `b >= a`) would both be
    true at a tie and hand the whole gradient to *both* operands, and a strict
    `>` on the left alone would hand it to the right one instead. The choice is
    the *operand order of the call*, not anything about the values: on a tie the
    two values are equal, so no test of them can prefer either side, and
    `max(a, b)` and `max(b, a)` must therefore differ in exactly which node is
    left. `relu(a)` is `max(a, 0)` in value, and its kink is that tie read with
    the constant on the left: the gradient goes to the constant, no one takes
    the constant's gradient, and `relu'(0) = 0`. That is the factor `[a > 0]`,
    so a `relu` that lets a zero through — the `>=` spelling, in one call —
    disagrees with the `mlp` fixture, whose pre-activations are exactly `0`, and
    with every other kink in this file.

DESIGN DECISION — why must the factor be read from the operands' values and
never from the incoming gradient?
    The local derivative is a property of the *operation at the operands' point*
    — which side of the kink the forward pass was on — and the incoming gradient
    is a different number entirely: it is whatever the rest of the graph sent
    back, and it is routinely negative, larger than the operands, or zero. A
    factor computed from it is a function of the wrong thing: it happens to
    agree on a fixture whose seed is `ones` and whose operands sit at `0` and
    `1`, and it disagrees the moment the seed is negative or the operands are
    fractions — silently, because the shape and the type are still right. The
    factor is also read from the *operand's* value and not from the node's own
    value: for `abs` those differ on exactly the half of the domain that carries
    the sign, and a mask read from `|x|` gives `+1` where the derivative is
    `-1`.

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

DESIGN DECISION — why are `relu` and `abs` their own factors instead of `max`
nodes over a constant?
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

TODO: implement `max`, `relu` and `abs`.
"""

import exact

from stage_01 import Node


def max(a, b):
    """`max(a, b)`, elementwise: one node whose value is `exact.max`'s and whose
    local backward hands each operand its share of the gradient.

    The value is `exact.max` of the two operands, so it broadcasts the way
    `exact.max` does and it is `exact`'s own figure element for element. The
    factors follow the documented convention: the left operand keeps the
    gradient where it is `>=` the right one and the right operand where it is
    `<`, so on a tie the whole gradient goes to the **left** operand — stated
    once, and the same everywhere — and never to both. A `(2, 3)` left operand
    against a `(3,)` right one owes each of them a gradient of its own shape, so
    the `(3,)` operand's masked gradient is summed back over the rows the
    broadcast stretched. A pair of shapes that do not broadcast is refused,
    naming both shapes and both numbers, and an operand that is not a `Node` is
    refused naming the offender.
    """
    raise NotImplementedError("stage 8: implement max()")


def relu(a):
    """`relu(a) = a if a > 0 else 0`, elementwise: one node whose value is
    `exact.relu`'s and whose local backward masks the gradient with `[a > 0]`.

    The kink is this stage's tie seen from the constant's side — `relu(a)` is
    `max(a, 0)`, and the tie at `a == 0` goes to the constant, whose gradient no
    one asks for — so `relu'(0) = 0`: a zero input keeps zero of the gradient,
    and so does every negative one. `abs(0)` and `relu(0)` must follow the same
    rule: the factor is zero exactly where the operand is.
    """
    raise NotImplementedError("stage 8: implement relu()")


def abs(a):
    """`abs(a)`, elementwise: one node whose value is `exact.abs`'s and whose
    local backward multiplies the gradient by the operand's sign.

    The factor is `+1` to the right of `0`, `-1` to the left of it and `0` at
    it: `abs(a)` is `relu(a) + relu(-a)`, whose two terms meet at `0`, and there
    the gradient goes nowhere rather than half to each side. An operand that is
    not a `Node` is refused, naming the offender.
    """
    raise NotImplementedError("stage 8: implement abs()")
