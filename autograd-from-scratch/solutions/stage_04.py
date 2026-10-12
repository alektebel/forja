"""Autograd From Scratch — stage 4: The chain rule through a matrix (implementation)

Stages 1 to 3 built one node per *shape*: every operation was elementwise, and
a shape change was a broadcast — stretched on the way forward, reduced back on
the way back — or a reduction, with its axis put back and stretched. This stage
adds the first operation that *contracts* two axes at once, `matmul`, and the
first real model: the fixture's MLP, a stack of `x @ w + b` with the activation
between the layers.

The forward is `exact.matmul`, so the node's value is `exact`'s own figure
element for element before any gradient is examined. The backward is the chain
rule through the contraction, and it is two lines:

    A (rows, inner), B (inner, cols), the node (rows, cols), the gradient G
    dA = G · Bᵀ        (rows, cols) · (cols, inner) = (rows, inner)
    dB = Aᵀ · G        (inner, rows) · (rows, cols) = (inner, cols)

Each contribution is born in the *operand's* shape (§3.2) and each is
*accumulated* into that operand's `grad` and never assigned (§3.3), so a weight
reached by two paths keeps the sum of both. The two transposes are what close
the contraction, and they are what a badly chosen fixture cannot see: on a
square pair every candidate formula has a legal shape, and on a symmetric one
two of them are the *same* matrix.

`mlp` is the fixture's model: one `(weight, bias)` pair per layer, in the order
`fixtures.MODEL_PARAMS` names — `"mlp"` is `("w1", "b1", "w2", "b2")` with
`w1 (3, 4)`, `b1 (4,)`, `w2 (4, 1)`, `b2 (1,)` — with the bias broadcast over
the rows by stage 3's `add` (whose backward is what hands the rank-1 bias back
a gradient of its own shape, summed over the stretched rows) and the activation
on every layer but the last, whose output is linear. The layer count and every
extent come from `params` and never from a hard-coded shape, so the same
function runs `"linear"`, `"mlp"` and `"deep"`.

Nothing here is a float and nothing here has a tolerance: a gradient is a
`Tensor` of `Rational`s, compared with `==` as pairs.

DESIGN DECISION — which operand's VJP is `G · Bᵀ` and which is `Aᵀ · G`?
    Both are forced by the shapes once the gradient's home is fixed. The node's
    gradient arrives in the node's shape, `(rows, cols)`, and `A`'s
    contribution must land in `A`'s shape, `(rows, inner)`: the only way to read
    a `(rows, cols)` against `B`'s `(inner, cols)` and come out `(rows, inner)`
    is against `B`'s *columns*, which is `Bᵀ` on the right — `G · Bᵀ`.
    Symmetrically `B` owes `(inner, cols)`, so `A` has to be read against its
    own rows on the left: `Aᵀ · G`. `A` carries the factor `B` and `B` carries
    the factor `A`, each read at the index the other one sums over, which is the
    product rule with the two summation axes delivered as the two transposes.

DESIGN DECISION — why must the probe fixture be neither square nor symmetric?
    Transposing the wrong operand — or writing the left operand's formula for
    the right one — is a mistake that two fixtures hide. On a *rectangular*
    pair the alternative formulas usually do not even have a shape
    (`(2, 4) · (3, 4)` does not contract), so the defect surfaces as a refusal
    rather than a wrong number and a reader may dismiss it as a typing mistake.
    On a *square* pair every candidate has a legal shape, and if the right
    operand is *symmetric* (`B = Bᵀ`) the two formulas are the same matrix: the
    engine is wrong and every number is right. So the probe is rectangular,
    non-symmetric, with distinct cells — and the check seeds it with a gradient
    that is itself non-symmetric, so a transposed *cell* cannot hide behind the
    seed either.

DESIGN DECISION — why is the bias added by stage 3's `add` and not by a
`matmul` against a column of ones?
    `z = x @ w + b` with `b` rank 1 and the product rank 2 is a broadcast, and
    stage 3's `add` is exactly that call: `exact.add` reads the bias at every
    row, and the backward is `exact.reduce_gradient` back to the `(out,)` the
    bias owes. Putting the bias in some other way — as a `(1, out)` operand, as
    a hand-broadcast `(rows, out)` constant, or by concatenating a column of
    ones and widening the weight — leaves the *value* identical and destroys
    the *gradient*: the reduction that sums the rows never happens, so the
    bias's own gradient is zero, or has the product's shape, or is a matrix's
    row sums. The fixture is explicit about what must happen: `b1` receives
    exactly the gradient the first row of `w1` receives (the input's constant-1
    column makes the two one direction), which is a free self-check that is
    only true if the broadcast was stage 3's.

DESIGN DECISION — why does this stage refuse a rank-1 operand and a
non-contracting pair itself, naming both shapes and both numbers?
    `exact.matmul` refuses both, but this stage is the one that knows what the
    caller *meant*, and the callers here are layers of a model. A rank-1
    operand is not promoted: NumPy would read the same `(3,)` as a row in one
    call and a column in the next, and both answers are plausible matrices of
    different shapes — so the guess would be inherited by every gradient above
    it, silently, and the mistake would surface many layers later as a
    gradient of the wrong shape. A pair that does not contract names both
    shapes and both extents, because those two numbers *are* the mismatch:
    a layer whose input width and weight height disagree is a model that was
    assembled wrong, and saying so at the call site is the whole diagnosis.
    The refusal is an `ExactError` (an arithmetic/shape refusal) while an
    operand that is not a `Node` is an `AutogradError` (a graph refusal), which
    is the §1 split.

DESIGN DECISION — why does `mlp` read its layer count and every extent from
`params`, and why is only the last layer linear?
    `params` *is* the architecture here: the fixture's `"linear"` is one pair,
    `"mlp"` two, `"deep"` three, and the same function runs all three. A loop
    that hard-coded the model's shape — `range(0, 4, 2)`, or a bias assumed to
    have four cells — would run the fixture the check happens to use and fail
    the others, and the failure would be invisible on the model whose shape was
    hard-coded. The last layer is the one place the activation must not be
    applied: the fixture's output is the linear `z2`, and the `"linear"`
    model's output contains a negative cell and a zero, which `relu` would
    clip — so a model that activates its last layer is wrong in the *forward*,
    visible without differentiating anything, and the `"linear"` fixture (one
    layer, no ambiguity) is where it shows.

DESIGN DECISION — why does this file carry its own activation node instead of
composing the one a later stage defines?
    A stage imports only the stages below it, and the course's `relu` is stage
    8's; this stage cannot reach up for it. So the hidden layers' activation is
    written here as a node of its own, with the course's kink convention
    restated: the factor is `1[a > 0]`, so `relu'(0) = 0` and a zero
    pre-activation keeps none of the gradient. That is not a formality — the
    fixture's pre-activations contain `0`s (`a - b` on the row `(1, 1, 0)` is
    exactly `0`), so a node that let a zero through disagrees with the frozen
    `fixtures.REFERENCE_GRADIENTS`, which is the interlock the fixture exists to
    make.

DESIGN DECISION — why does the accumulation of the VJPs matter as much as
their formulas?
    `a.grad = exact.add(a.grad, left)` and not `a.grad = left`: a weight is
    routinely reached by more than one path — a shared layer, a model applied
    twice, two `matmul`s against the same operand — and each path's
    contribution must reach what the others left (§3.3). The assignment version
    is invisible on the first `backward` from a fresh graph (the field starts at
    zeros, so the first contribution and the first sum are the same tensor) and
    it is wrong from the second path on; a check therefore accumulates two
    contractions into one weight before it reads it.
"""

import exact
import stage_01
import stage_03


_ZERO = exact.Rational(0)


def _operand(op, name, node):
    """One operand that is a `stage_01.Node`, or the refusal naming the
    operation and the operand it was handed."""
    if not isinstance(node, stage_01.Node):
        raise exact.AutogradError(
            "%s: %s=%r is not a Node" % (op, name, node))
    return node


def matmul(a, b):
    """`a @ b`, rank 2: one node whose value is `exact.matmul`'s and whose local
    backward hands each operand its VJP — `G · Bᵀ` on the left, `Aᵀ · G` on the
    right — each in that operand's own shape and accumulated, never assigned.

    `a` is `(rows, inner)` and `b` is `(inner, cols)`, so the node is
    `(rows, cols)`: reading the gradient against `B`'s columns is what produces
    the `(rows, inner)` the left operand owes, and against `A`'s rows the
    `(inner, cols)` the right one owes. A rank-1 operand is refused rather than
    promoted (the same `(3,)` is a row to one reader and a column to the next)
    and a pair whose inner extents disagree is refused naming both shapes and
    both extents; an operand that is not a `Node` is refused naming it.
    """
    _operand("matmul", "a", a)
    _operand("matmul", "b", b)
    a_shape = a.value.shape
    b_shape = b.value.shape
    if len(a_shape) != 2 or len(b_shape) != 2:
        raise exact.ExactError(
            "matmul: a has shape %r and b has shape %r, and both operands must "
            "be rank 2: %d and %d"
            % (a_shape, b_shape, a.value.size, b.value.size))
    if a_shape[1] != b_shape[0]:
        raise exact.ExactError(
            "matmul: a has shape %r and b has shape %r, and their inner extents "
            "do not contract: %d and %d at axis 1 of a and axis 0 of b"
            % (a_shape, b_shape, a_shape[1], b_shape[0]))
    value = exact.matmul(a.value, b.value)

    def backward_of_op(gradient):
        left = exact.matmul(gradient, exact.transpose(b.value))
        right = exact.matmul(exact.transpose(a.value), gradient)
        a.grad = exact.add(a.grad, left)
        b.grad = exact.add(b.grad, right)

    return stage_01.Node(value, parents=(a, b), backward=backward_of_op)


def _relu(t):
    """`relu` as a node of this stage: `exact.relu`'s value and the factor
    `1[value > 0]` read from the operand's own values, so `relu'(0) = 0`.

    The hidden layers need it and stage 8 — which formalizes the kink — sits
    above this one, so the one rule is restated here: a cell that is exactly
    `0` keeps none of the gradient. The factor is read from the operand's
    values and never from the incoming gradient, which is a different number
    entirely.
    """
    value = exact.relu(t.value)
    values = t.value.cells

    def backward_of(gradient):
        cells = tuple(cell if values[position] > _ZERO else _ZERO
                      for position, cell in enumerate(gradient.cells))
        t.grad = exact.add(t.grad, exact.Tensor(cells, value.shape))

    return stage_01.Node(value, parents=(t,), backward=backward_of)


def mlp(params, x):
    """The fixture's small model: one `(weight, bias)` pair per layer, applied
    in the order `params` gives them, with the activation on every layer but
    the last.

    `params` holds the layer tensors in `fixtures.MODELS` order — `w1`, `b1`,
    `w2`, `b2`, … — as `stage_01.Node`s, each weight `(in, out)` row-major and
    each bias rank 1; `x` is a rank-2 input node of shape `(rows, in)`. A layer
    is `z = x @ w + b`, the bias broadcast over the rows by stage 3's `add`
    (whose backward reduces its contribution back to the bias's own `(out,)`),
    and the activation is applied to every layer but the last, whose output is
    linear. Every extent comes from `params` — never from a hard-coded shape —
    so the same call runs the fixture's one-, two- and three-layer models; a
    weight that is not rank 2, a bias that is not rank 1, an inner extent that
    does not contract, a bias extent that does not match the layer's output, an
    odd number of tensors and an input that is not rank 2 are each refused,
    naming the offender and both shapes.
    """
    _operand("mlp", "x", x)
    if not isinstance(params, (tuple, list)):
        raise exact.AutogradError(
            "mlp: params=%r is not a sequence of Nodes" % (params,))
    params = tuple(params)
    if len(params) == 0 or len(params) % 2 != 0:
        raise exact.AutogradError(
            "mlp: params holds %d tensors, and a model is one (weight, bias) "
            "pair per layer" % (len(params),))
    for position, param in enumerate(params):
        _operand("mlp", "params[%d]" % position, param)
    if len(x.value.shape) != 2:
        raise exact.ExactError(
            "mlp: x has shape %r, and an input must be rank 2: %d"
            % (x.value.shape, x.value.size))
    h = x
    for index in range(0, len(params), 2):
        weight = params[index]
        bias = params[index + 1]
        weight_shape = weight.value.shape
        bias_shape = bias.value.shape
        if len(weight_shape) != 2:
            raise exact.ExactError(
                "mlp: params[%d] has shape %r, and a weight must be rank 2: %d"
                % (index, weight_shape, weight.value.size))
        if len(bias_shape) != 1:
            raise exact.ExactError(
                "mlp: params[%d] has shape %r, and a bias must be rank 1: %d"
                % (index + 1, bias_shape, bias.value.size))
        if h.value.shape[1] != weight_shape[0]:
            raise exact.ExactError(
                "mlp: the layer's input has shape %r and params[%d] has shape "
                "%r, and their inner extents do not contract: %d and %d"
                % (h.value.shape, index, weight_shape,
                   h.value.shape[1], weight_shape[0]))
        if bias_shape[0] != weight_shape[1]:
            raise exact.ExactError(
                "mlp: params[%d] has shape %r and params[%d] has shape %r, and "
                "the bias's extent does not match the layer's output: %d and %d"
                % (index + 1, bias_shape, index, weight_shape,
                   bias_shape[0], weight_shape[1]))
        layer = stage_03.add(matmul(h, weight), bias)
        h = layer if index + 2 == len(params) else _relu(layer)
    return h
