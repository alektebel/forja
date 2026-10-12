"""Autograd From Scratch — stage 2: The local derivatives (implementation)

Stage 1 built the graph and the order a backward walks it in; this stage is the
per-operation half of the backward — the closed form of each local derivative,
registered on the node that produced the value. `sub`, `div`, `pow` and `neg`
are the four operations a loss and a learning rate need and stage 1 does not
have. Nothing here re-derives a value: every forward is `exact`'s own algebra,
so the forward is provably right before any gradient is examined. Nothing here
walks a graph either: the local backward is a closure that takes the node's
accumulated gradient, multiplies it by the operation's closed-form derivative,
and accumulates the result into each parent's `grad` — the same discipline
stage 1's `add` and `mul` use, and the reason a node used twice gets the sum of
its paths.

The operands of a binary operation have one shape here (stage 3 owns the
broadcast), a divisor is not zero, and an exponent is a non-negative int. Each
of those is refused at *build* time, naming the offender and both numbers: a
node whose value cannot exist cannot carry a derivative either, and a refusal
that arrives while the backward is running arrives after the value it should
have protected.

The four closed forms, with `g` the node's accumulated gradient:

    sub   d(a - b)/da = g            d(a - b)/db = -g
    div   d(a / b)/da = g / b        d(a / b)/db = -g * a / b**2
    pow   d(a**n)/da  = g * n * a**(n - 1)      (n == 0: 0)
    neg   d(-a)/da    = -g

Each of them is a `Rational` pair times a `Rational` pair: exact, no tolerance,
and the same pair whatever order the arithmetic is written in.
"""

import exact
import stage_01


def _operand(op, name, node):
    """One operand that is a `stage_01.Node`, or the refusal naming it.

    `name` is the operand's own name — `a` for a unary operation, `a` or `b`
    for a binary one — so the message says which side was wrong and shows what
    was passed instead.
    """
    if not isinstance(node, stage_01.Node):
        raise exact.AutogradError("%s: %s=%r is not a Node" % (op, name, node))
    return node


def _joined(op, a, b):
    """Two operands of *one* shape, or the refusal naming both shapes.

    `exact` would broadcast a `(2, 3)` against a `(3,)` for free, and that is
    precisely what must not happen here: the operand the broadcast stretched
    owes the reduction of stage 3, so a stage-2 node that quietly accepted the
    broadcast would hand the `(3,)` operand a `(2, 3)` gradient — the output's
    shape instead of the operand's, which is the invariant a gradient may never
    break. The refusal names both shapes *and* both sizes, so an operand pair
    that differs only in how it is laid out is still refused.
    """
    _operand(op, "a", a)
    _operand(op, "b", b)
    if a.value.shape != b.value.shape:
        raise exact.ExactError(
            "%s: a has shape %r and b has shape %r, and stage 2 does not "
            "broadcast: %d and %d"
            % (op, a.value.shape, b.value.shape, a.value.size, b.value.size))
    return a, b


def _binary(op, a, b, forward, local):
    """One binary node: the operand guards, `forward`'s value, and the closure
    that accumulates `local`'s pair of gradients into the two parents.

    `local(gradient, left_value, right_value)` is the closed form, the only
    per-operation code below; the guards and the accumulation are the same for
    every binary operation, so they live here and not twice at the call sites.
    The closure accumulates and never assigns: a parent that already holds a
    contribution from another path keeps it.
    """
    a, b = _joined(op, a, b)
    value = forward(a.value, b.value)

    def backward_of_op(gradient):
        left, right = local(gradient, a.value, b.value)
        a.grad = exact.add(a.grad, left)
        b.grad = exact.add(b.grad, right)

    return stage_01.Node(value, parents=(a, b), backward=backward_of_op)


def _unary(op, a, forward, local):
    """One unary node: one parent, one closed-form derivative.

    A unary operation has no second operand to guard and no shape to compare,
    so this is the whole of it: the operand is a node, the value is `exact`'s,
    and the closure accumulates `local(gradient, value)` into the one parent.
    """
    _operand(op, "a", a)
    value = forward(a.value)

    def backward_of_op(gradient):
        a.grad = exact.add(a.grad, local(gradient, a.value))

    return stage_01.Node(value, parents=(a,), backward=backward_of_op)


def sub(a, b):
    """`a - b`, elementwise: one node whose value is `exact.sub`'s and whose
    local backward hands the gradient to `a` and its negation to `b`.

    The derivative of a difference is one for the minuend and minus one for
    the subtrahend, so the pair is `(gradient, -gradient)`. The sign is the
    whole content of the operation and the one place it can be lost: a backward
    that handed the subtrahend `+gradient` — or the minuend `-gradient` — would
    still be right wherever the two contributions cancel, which is exactly what
    an equal-shaped fixture with opposite gradients cannot see.
    """
    return _binary("sub", a, b, exact.sub,
                   lambda gradient, left, right: (gradient, exact.neg(gradient)))


def div(a, b):
    """`a / b`, elementwise and exact: `exact.div`, which refuses a zero
    divisor naming both operands, the output index and the shape.

    `div` is not `a * pow(b, -1)`, and the difference is not a formality:
    `exact.pow` refuses a negative exponent (the whole reason `div` exists),
    and an implementation that hand-rolled the reciprocal instead — or worse,
    that divided the numerators with `//` — would answer `1` for `3 / 2` and
    train on a loss that is not the loss.
    """
    return _binary("div", a, b, exact.div, _quotient)


def _quotient(gradient, left, right):
    """The quotient rule, exact and in its closed form.

    `d(a / b)/da = 1 / b` and `d(a / b)/db = -a / b**2`, each multiplied by the
    incoming gradient. Written as divisions rather than as multiplications by a
    reciprocal: `right` is not zero (the forward refused it), so the divisions
    are exact, and the square is the divisor times itself — dividing by `b`
    once where the rule wants `b**2` is a defect that only a divisor other than
    `±1` can see.
    """
    return (exact.div(gradient, right),
            exact.div(exact.neg(exact.mul(gradient, left)),
                      exact.mul(right, right)))


def pow(a, n):
    """`a ** n` for a non-negative int `n`: `exact.pow`'s value, and the
    derivative `n * a**(n - 1)`.

    `exact.pow` refuses a negative exponent and a non-int one, naming it, so
    the forward refuses before any node exists: an engine that needs `a ** -1`
    wants `div`. The exponent is the operand the local derivative needs and the
    value it cannot recover — `a**n` is a different number for every `n` — so
    the closure captures `n` and not the value.

    `n == 0` is its own case: `a**0` is one everywhere, its derivative is zero,
    and the closed form would want `a**(-1)`, which `exact.pow` refuses. So the
    exponent zero contributes the zeros of the *operand's* shape, which is the
    shape every gradient owes its operand.
    """
    _operand("pow", "a", a)
    value = exact.pow(a.value, n)

    def backward_of_pow(gradient):
        if n == 0:
            a.grad = exact.add(a.grad, exact.zeros(a.value.shape))
        else:
            a.grad = exact.add(
                a.grad,
                exact.mul(gradient,
                          exact.mul(exact.full(a.value.shape, n),
                                    exact.pow(a.value, n - 1))))

    return stage_01.Node(value, parents=(a,), backward=backward_of_pow)


def neg(a):
    """`-a`, elementwise: one node whose value is `exact.neg`'s and whose local
    backward hands the parent the negated gradient.

    `neg` builds a new node — it does not negate its operand's value in place.
    An `exact.Tensor` is immutable and a leaf's value is what the fixture said
    it was; a `neg` that wrote `a.value = exact.neg(a.value)` and returned `a`
    would look right at the prompt (the value is negated) while corrupting
    every other node that reads the operand, and a second `neg` of the same
    operand would flip it back.
    """
    return _unary("neg", a, exact.neg,
                  lambda gradient, value: exact.neg(gradient))
