"""Autograd From Scratch — stage 4: The chain rule through a matrix

Stages 1 to 3 built one node per *shape*: every operation was elementwise, and
a shape change was either a broadcast (stretched, then reduced back to the
operand) or a reduction (an axis removed, then put back and stretched). This
stage adds the first operation that *contracts* two axes at once — `matmul` —
and with it the first real model: the small MLP the fixtures define, whose
forward is a stack of `x @ w + b` with an activation between the layers.

The forward is `exact`'s own algebra again, `exact.matmul`, so the node's value
is proved right element for element before any gradient is looked at. The
backward is the chain rule through a matrix, and it has exactly two lines:

    A (rows, inner), B (inner, cols), the node (rows, cols), the gradient G
    dA = G · Bᵀ        (rows, cols) · (cols, inner) = (rows, inner)
    dB = Aᵀ · G        (inner, rows) · (rows, cols) = (inner, cols)

Each VJP has the *operand's* shape (§3.2) — not the node's, not the other
operand's — and each is accumulated into that operand's `grad`, never assigned
(§3.3), so a weight reached by two layers' paths keeps the sum of both. The
transposes are what make the contraction close: `G · Bᵀ` re-reads the gradient
against `B`'s columns, `Aᵀ · G` against `A`'s rows. A pair of operands that do
not agree on the inner extent is refused, naming both shapes and both numbers,
and so is an operand that is not rank 2 — a rank-1 operand is **not** silently
promoted to a row or a column, because the caller's intent would be a guess
(the same `(3,)` is a row to one reader and a column to the next) and every
downstream shape would inherit it.

The model is the fixture's: one `(weight, bias)` pair per layer, in the frozen
order `fixtures.MODEL_PARAMS` names — `"mlp"` is `("w1", "b1", "w2", "b2")`
with `w1 (3, 4)`, `b1 (4,)`, `w2 (4, 1)`, `b2 (1,)`; `"linear"` is `w1 (3, 1)`,
`b1 (1,)`; `"deep"` is `w1 (3, 4)`, `b1 (4,)`, `w2 (4, 4)`, `b2 (4,)`,
`w3 (4, 1)`, `b3 (1,)`. The weights are `(in, out)` row-major and the product
is `x @ w`; the input's first column is the fixture's constant `1`, which is
why `w1` starts as `(3, h)`. A layer is `z = x @ w + b` with the rank-1 bias
*broadcast over the rows* by stage 3's `add` — the call that also hands the
bias back a gradient of its own `(out,)` shape, summed over the rows the
broadcast stretched — and the activation is applied to every layer but the
last, whose output is linear. The layer count and every extent come from
`params`, never from a hard-coded shape: the same function runs the one-layer
`"linear"` model and the three-layer `"deep"` one.

Nothing here is a float and nothing here has a tolerance: a value and a
gradient are `Tensor`s of `Rational`s, compared with `==` as pairs.

DESIGN DECISION — which operand's VJP is `G · Bᵀ` and which is `Aᵀ · G`?
    The node's value is `A·B` and the gradient arrives in the node's shape,
    `(rows, cols)`. Its contribution to `A` must land in `A`'s shape,
    `(rows, inner)`, so it has to be read against `B`'s *columns* — that is
    `B`'s transpose — on the right: `G · Bᵀ`. Symmetrically, `B`'s
    contribution owes `(inner, cols)`, so `A` has to be read against its own
    rows on the left: `Aᵀ · G`. Both are forced by the shapes to within a
    transpose, and the transpose is precisely the part that a fixture cannot
    see if it is badly chosen.

DESIGN DECISION — why must the probe fixture be neither square nor symmetric?
    Swap the two VJPs, or write `G · Bᵀ` for the `B` gradient, and the shapes
    usually disagree — `(2, 4) · (3, 4)` does not contract — which is the
    refusal, not the bug. The dangerous fixture is the square one: with
    `A (2, 2)` and `B (2, 2)` every candidate has a legal shape, and with a
    *symmetric* `B` (`B = Bᵀ`) the two formulas are the same matrix, so an
    engine that transposes the wrong operand passes. A probe has to be
    rectangular (so the wrong formula has the wrong shape) *and* non-symmetric
    (so that when the shapes do agree, the cells still disagree).

DESIGN DECISION — why is the bias added by stage 3's `add` instead of by a
`matmul` against a column of ones?
    `z = x @ w + b` with `b` rank 1 and the product rank 2 is a *broadcast*, and
    stage 3 exists for exactly this call: `exact.add` reads the bias at every
    row, and the backward reduces the gradient back to the `(out,)` the bias
    owes. Building the bias in with a matrix of ones instead — `b` as a
    `(1, out)` operand, or a `matmul` against a column of ones — changes the
    value not at all and destroys the gradient: the reduction that sums the
    rows never happens, the bias's own contribution is nowhere (or is the sum
    of a matrix's rows), and the parameter that the fixture's own docstring
    says must receive the same gradient as the first row of `w1` receives
    zero. The shape of the *value* is the same either way; the shape of the
    *gradient* is the whole difference, which is why the check reads
    `b.grad.shape` and not just the loss.

DESIGN DECISION — why does this stage refuse a rank-1 operand and a
non-contracting pair itself, naming both shapes and both numbers?
    `exact.matmul` would refuse both, and it names the two shapes — but the
    stage's own refusal is where the *caller's* mistake is named: an operand of
    the wrong rank is a graph-level mistake (the caller built a node holding a
    vector where a matrix was meant), and an inner mismatch is the pair of
    dimension numbers the two layers disagree about. Silence is not an option
    in either case: NumPy-style promotion of `(3,)` to `(1, 3)` or `(3, 1)` is
    a guess between two answers whose shapes are different and whose numbers
    are both plausible, and a rank-1 operand accepted here surfaces three
    layers later as a gradient of the wrong shape. The refusal is the cheapest
    place to say which of the two operands was wrong and what its shape was.

DESIGN DECISION — why does `mlp` read its layer count and every extent from
`params`, and why is only the last layer linear?
    A model is data here: `params` *is* the architecture, and the same function
    must run the fixture's one-layer `"linear"`, its two-layer `"mlp"` and its
    three-layer `"deep"`. A loop that walked a hard-coded four-tensor model —
    `range(0, 4, 2)`, or a `(3, 4)` weight assumed — would run the fixture the
    check is written on and fail the others, and it would be invisible on the
    model whose shape it hard-coded. The last layer is the one place the
    activation must not be applied: the fixture's output is the linear `z2`,
    and its `"linear"` model's output contains a negative cell and a zero
    (both of which `relu` would clip) — so a model that activates its last
    layer is a *forward* that is wrong, visible without differentiating
    anything.

DESIGN DECISION — why does this file carry its own activation node instead of
composing the one a later stage defines?
    A stage imports only the stages below it — stage 8's `relu` sits above this
    one — so the tiny node this stage's hidden layers need is written here, with
    the course's kink convention restated: `relu'(0) = 0`, the gradient of a
    cell that is exactly zero goes nowhere. That convention is not a detail
    here: the fixture's own pre-activations contain `0`s (unit 1 is `a - b`,
    which is `0` on the row `(1, 1, 0)`), so a hidden node that let a zero
    pre-activation through disagrees with the frozen gradient — which is the
    check the fixture exists to make.

TODO: implement `matmul` and `mlp`.
"""

import exact
import stage_01
import stage_03


def matmul(a, b):
    """The rank-2 matrix product `a @ b` as one node, whose local backward is
    the chain rule through the contraction.

    `a` is `(rows, inner)` and `b` is `(inner, cols)`, so the node's value is
    `exact.matmul`'s `(rows, cols)`; either operand that is not rank 2, and a
    pair whose inner extents disagree, is refused — naming both shapes and both
    numbers, and never promoting a `(3,)` to a row or a column. The VJP of the
    left operand is `G · Bᵀ` and of the right one `Aᵀ · G`: each has its own
    operand's shape and each is *accumulated* into that operand's `grad`, so a
    weight reached by two paths keeps the sum of both.
    """
    raise NotImplementedError("stage 4: implement matmul()")


def mlp(params, x):
    """The fixture's small model: one `(weight, bias)` pair per layer, applied
    in the order `params` gives them, with the activation on every layer but
    the last.

    `params` holds the layer tensors in `fixtures.MODELS` order — `w1`, `b1`,
    `w2`, `b2`, … — as nodes, each weight `(in, out)` row-major and each bias
    rank 1; `x` is a rank-2 input node of shape `(rows, in)`. A layer is
    `z = x @ w + b` (the bias broadcast over the rows by `add`, whose backward
    reduces its gradient back to the bias's own `(out,)`) and the activation is
    applied to every layer but the last, whose output is linear. Every extent
    comes from `params`: a weight that is not rank 2, a bias that is not rank 1,
    an inner extent that does not contract, a bias extent that does not match
    the layer's output, an odd number of tensors and an input that is not rank
    2 are each refused, naming the offender and both shapes.
    """
    raise NotImplementedError("stage 4: implement mlp()")
