"""fixtures.py — the provided deterministic world of H2: the datasets, the tiny
models and their integer weights, the frozen learning rate, and the two exact
references the last stage must reproduce.

Nothing here is random and nothing here is measured: every weight of every
model is an integer literal below, every dataset is an integer table, and the
two references are derived from them by exact `Rational` arithmetic at import.
Two imports give `==` values, and a test that wants a different world writes
another fixture rather than perturbing this one.

The datasets (the constant-1 column)
------------------------------------
`AND`, `OR`, `XOR` and `PARITY` are `(inputs, targets)` — a pair of integer
`exact.Tensor`s. The inputs of the two-bit datasets (`AND`, `OR`, `XOR`) have
shape `(4, 3)` and one row per bit pattern, in binary order `(0,0)`, `(0,1)`,
`(1,0)`, `(1,1)`; `PARITY` is the **three-bit** dataset of shape `(8, 4)`, one
row per pattern `(a, b, c)` in binary order, with the target `(a + b + c) mod 2`
— it is here so that a stage has a dataset wider than the models, and because
`parity` of two bits would just be `XOR` again.

**Every input row starts with a constant `1`.** That first cell is the fixture's
explicit bias column, and it is the reason a stage's implementation of `mul` or
`matmul` arrives with a working bias: with a weight column against it, the
first row of `w1` *is* a bias term, so stage 1 (whose graph is only `add` and
`mul`) can fit an offset with no broadcast and no `add` of different shapes at
all. The models *also* carry explicit bias tensors (`b1`, `b2`, ...) because
the contract's stage-3 and stage-4 mistakes — a bias added without
broadcasting, a gradient that never went through `reduce_gradient` — need a
rank-1 operand to reduce. The consequence is deliberate and worth stating: the
first row of `w1` and `b1` receive *identical* gradients at every step (the
column is all ones), so the fixture's parameter set has one redundant
direction. That redundancy is a free self-check for stage 3: an engine whose
bias gradient disagrees with its first weight row's gradient is wrong.

The models
----------
`MODELS` maps a model name to its parameter tensors, **in the frozen order**,
and `MODEL_PARAMS` maps the same name to the tensor names in that order: one
`(weight, bias)` pair per layer, layer by layer. So `"mlp"` is
`("w1", "b1", "w2", "b2")` with shapes `(3, 4)`, `(4,)`, `(4, 1)`, `(1,)`: `w1`
is layer 1's weight, `b1` its bias, `w2` layer 2's weight, `b2` its bias. The
weights are row-major, `w` is `(in, out)` — the product is `x @ w` — and every
bias is rank 1, so `x @ w + b` is the contract's `(rows, out)` + `(out,)`.

The contract names the shapes `2 -> 1`, `2 -> 4 -> 1` and `2 -> 4 -> 4 -> 1`:
two *features* in, `h` hidden units, one out. Because of the constant-1 column
the input row has three cells and the first weight is therefore `(3, h)`; the
"2" is the feature count, not the width of the input tensor.

* ``"linear"`` — `w1 (3, 1)`, `b1 (1,)`: the perceptron `a + b - 1`, one
  product and one bias, no hidden unit. It is the fixture's *feasible long
  run*: `LEARNING_RATE` and plain SGD learn `AND` and `OR` from it within
  `STEPS` steps, with the exact loss strictly decreasing at every step, and it
  can never learn `XOR` — no linear model can, which is why `"mlp"` exists.
  Its exact loss stays within ~1200 bits over all `STEPS` steps.
* ``"mlp"`` — `w1 (3, 4)`, `b1 (4,)`, `w2 (4, 1)`, `b2 (1,)`: the 2 -> 4 -> 1
  network the frozen references are computed on, built out of four integer
  hidden units that between them *can* separate `XOR` exactly: unit 1 is
  `a - b`, unit 2 is `b - a`, unit 3 is `a + b - 1`, unit 4 is `1 - a - b`,
  and the output weights `(2, 2, 1, -1)` on them give `-1, 2, 2, 1` — one
  sign wrong on the `(1, 1)` row, every row off by exactly one. Under plain
  SGD at `LEARNING_RATE` the loss starts at exactly `1` (every residual is
  `+/-1`), decreases strictly, and by step `EXPECTED_STEPS` every prediction
  is on the correct side of `1/2`: **this fixture learns `XOR` inside the
  frozen budget**, and every unit's gradient is alive (no dead unit for the
  run to stall on). Its input rows also sit *exactly on the kink* of several
  units — the pre-activations of rows 1..4 contain `0`s — so the frozen
  gradient is sensitive to the contract's `relu'(0) = 0` convention, on
  purpose: a stage that sends the gradient through a zero pre-activation
  disagrees with `REFERENCE_GRADIENTS`.
* ``"deep"`` — `w1 (3, 4)`, `b1 (4,)`, `w2 (4, 4)`, `b2 (4,)`, `w3 (4, 1)`,
  `b3 (1,)`: the 2 -> 4 -> 4 -> 1 network, a fixed small odd pattern chosen by
  hand and not tuned, there for the stages' depth and shape probes. No frozen
  reference is computed on it.

The exactness budget (read this before freezing another run)
-----------------------------------------------------------
The two-layer fixtures are products of products: the *denominator* of a
parameter after `k` plain steps multiplies by about `4 * D**3`, i.e. its bit
length grows by a factor of about `3` per step. Measured on the `mlp` fixture
below: the loss's denominator is 1, 13, 44, 140, 428, 1292, 3884, 11660 bits
after steps 1..8. That is why `EXPECTED_LOSS` freezes **eight** steps and not
`STEPS`: an exact two-layer run stops being writable down long before it stops
being right. A linear fixture does not multiply denominators (`D` grows by a
factor of 4 per step, and the loss by its square), which is what makes
`"linear"` the one model whose whole `STEPS`-step run stays cheap.

The composite, and the two frozen references
--------------------------------------------
On `MODELS["mlp"]`, the inputs `XOR[0]` and the targets `XOR[1]`, the forward
is the fixture's own, written out with no graph engine:

    z1 = x @ w1 + b1        a1 = relu(z1)        z2 = a1 @ w2 + b2
    loss = mean( (z2 - y) ** 2 )      # the mean over the four rows, 1/4

with `relu(v) = v if v > 0 else 0`. `loss` is one scalar, an exact
`Rational`; `mean`'s `1/4` is exact and never a float.

* `EXPECTED_LOSS` is the loss **after each of the first eight steps** of plain
  SGD on that composite, `theta <- theta - LEARNING_RATE * grad(loss)`, every
  gradient taken at the current parameters and every update applied after all
  the gradients are computed (the ordering bug the capstone warns about). It
  starts at `1` and decreases strictly, and by step 8 every prediction is on
  the correct side of `1/2` — `XOR` learned, exactly, inside the budget.
  **These are the numbers stage 10's capstone must reproduce**, `Rational`
  for `Rational`.
* `REFERENCE_GRADIENTS` maps each tensor's name — `"w1"`, `"b1"`, `"w2"`,
  `"b2"` — to the exact gradient of that same loss at the *initial* weights,
  flattened row-major in the tensor's own shape, by the chain rule H1's
  `model.py` uses: a sum over the rows of `2 * (z2 - y) * relu'(z1)` times the
  local factor, with the `1/n` of the mean already inside. It carries no extra
  learning rate, so `sgd` needs no second factor: step 10's first update is
  literally `w1 - LEARNING_RATE * REFERENCE_GRADIENTS["w1"]`.

Both references are computed **inside this file** by the independent exact
implementation below — element by element, loops over the Rationals, no graph,
no `exact` forward call — so a disagreement with the engine is a disagreement
between two independent computations, and `verify_exact.py` re-derives them a
third time, brute force, from the literals.
"""

import types

import exact
from exact import Rational


# ---------------------------------------------------------------------------
# The datasets: `(inputs, targets)`, integer cells, a constant-1 first column
# ---------------------------------------------------------------------------

#: Two-bit tables, one row per pattern `(a, b)` in binary order, the leading
#: `1` being the frozen bias column.
AND = (
    exact.Tensor((1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1), (4, 3)),
    exact.Tensor((0, 0, 0, 1), (4, 1)),
)

OR = (
    exact.Tensor((1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1), (4, 3)),
    exact.Tensor((0, 1, 1, 1), (4, 1)),
)

XOR = (
    exact.Tensor((1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1), (4, 3)),
    exact.Tensor((0, 1, 1, 0), (4, 1)),
)

#: The three-bit table: eight rows `(a, b, c)` in binary order, the target the
#: parity bit `(a + b + c) % 2`.
PARITY = (
    exact.Tensor((1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1,
                  1, 1, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1), (8, 4)),
    exact.Tensor((0, 1, 1, 0, 1, 0, 0, 1), (8, 1)),
)

# ---------------------------------------------------------------------------
# The models: integer weights, in the frozen (weight, bias) per-layer order
# ---------------------------------------------------------------------------

#: The tensor names of each model, in `MODELS`' order: `("w1", "b1", "w2",
#: "b2")` means layer 1's weight, layer 1's bias, layer 2's weight, layer 2's
#: bias. `REFERENCE_GRADIENTS` is keyed by exactly these names.
MODEL_PARAMS = types.MappingProxyType({
    "linear": ("w1", "b1"),
    "mlp": ("w1", "b1", "w2", "b2"),
    "deep": ("w1", "b1", "w2", "b2", "w3", "b3"),
})

#: The parameter tensors, in the order `MODEL_PARAMS` names. Weights are
#: `(in, out)` row-major (`x @ w`), biases are rank 1 and broadcast over the
#: rows. The input width is 3 (two features plus the bias column) except for
#: the deeper layers, which take the previous layer's width.
MODELS = types.MappingProxyType({
    "linear": (
        exact.Tensor((0, 1, 1), (3, 1)),
        exact.Tensor((-1,), (1,)),
    ),
    "mlp": (
        exact.Tensor((0, 0, -1, 1,
                      1, -1, 1, -1,
                      -1, 1, 1, -1), (3, 4)),
        exact.Tensor((0, 0, 0, 0), (4,)),
        exact.Tensor((2, 2, 1, -1), (4, 1)),
        exact.Tensor((0,), (1,)),
    ),
    "deep": (
        exact.Tensor((0, 1, -1, 0,
                      1, 0, 1, -1,
                      -1, 1, 0, 1), (3, 4)),
        exact.Tensor((1, -1, 0, 1), (4,)),
        exact.Tensor((0, 1, 0, -1,
                      1, 0, -1, 0,
                      -1, 1, 1, 0,
                      0, -1, 0, 1), (4, 4)),
        exact.Tensor((0, 1, -1, 0), (4,)),
        exact.Tensor((1, -1, 1, -1), (4, 1)),
        exact.Tensor((0,), (1,)),
    ),
})

#: The one learning rate of the course: `Rational(1, 4)`, exact. Plain SGD is
#: `theta <- theta - LEARNING_RATE * grad(loss)`; with `mean`'s `1/4` already
#: inside the loss this is the stable step for the `mlp` fixture and the one
#: `EXPECTED_LOSS` is frozen under.
LEARNING_RATE = Rational(1, 4)

#: The capstone's step count. `EXPECTED_LOSS` freezes the first eight steps —
#: see the module docstring's exactness budget — and `"linear"` is the fixture
#: whose whole run is cheap enough to reproduce exactly at this length.
STEPS = 200


# ---------------------------------------------------------------------------
# The independent exact implementation: the composite and its chain rule
# ---------------------------------------------------------------------------
# Nothing below uses a graph, a `Node`, or `exact`'s forward algebra: it is
# loops over nested tuples of `Rational`s, written out element by element, so
# that the frozen references are a *second* computation of the same numbers
# the engine must produce. The only things it borrows from the fixture are the
# literals above and the `Rational` type itself.

def _dot(row, weight, column):
    """`sum(row[k] * weight[k][column] for k in range(len(row)))`."""
    total = Rational(0)
    for step in range(len(row)):
        total = total + row[step] * weight[step][column]
    return total


def _nested_params(name):
    """A model's parameters as nested tuples of `Rational`s in `MODELS` order:
    each rank-2 weight as rows of `in` cells, each rank-1 bias as a flat
    tuple of `out` cells."""
    out = []
    for tensor in MODELS[name]:
        if tensor.ndim == 2:
            out.append(tensor.to_nested())
        else:
            out.append(tensor.cells)
    return tuple(out)


def _pairs(params):
    """`params` — `(w, b)` per layer — as the tuple of pairs it already is."""
    return tuple((params[index], params[index + 1])
                 for index in range(0, len(params), 2))


def _composite(params, inputs, targets):
    """The composite's loss and its exact gradient, element by element.

    The forward is `a = relu(a @ w + b)` for every layer but the last, whose
    output is linear; the loss is the mean over the rows of the summed squared
    residual, `sum_i sum_j (out - y)**2 / rows`. The backward is the chain
    rule: `2 * (out - y) / rows` at the output, then, layer by layer, the
    weight gradient `a_prevᵀ @ delta`, the bias gradient `sum_i delta`, and
    the delta handed to the previous layer multiplied by `wᵀ` and gated by
    `relu'(z) = 1 if z > 0 else 0` — the same shape of computation H1's
    `model.reference_gradients` performs over its tokens.

    Returns `(loss, gradients)` with the gradients in `MODELS` order, each
    weight nested `(in, out)` and each bias flat `(out,)`.
    """
    x = inputs.to_nested()
    y = targets.to_nested()
    rows = len(x)
    zero = Rational(0)
    pairs = _pairs(params)
    values = [x]
    pre = []
    out = None
    for index, (weight, bias) in enumerate(pairs):
        last = index == len(pairs) - 1
        z = tuple(
            tuple(_dot(row, weight, column) + bias[column]
                  for column in range(len(bias)))
            for row in values[-1])
        pre.append(z)
        if last:
            out = z
        else:
            out = tuple(tuple(cell if cell > zero else zero for cell in row)
                        for row in z)
        values.append(out)
    total = zero
    for row in range(rows):
        for column in range(len(out[row])):
            residual = out[row][column] - y[row][column]
            total = total + residual * residual
    loss = total / Rational(rows)
    scale = Rational(2) / Rational(rows)
    delta = tuple(
        tuple(scale * (out[row][column] - y[row][column])
              for column in range(len(out[row])))
        for row in range(rows))
    grads = [None] * (2 * len(pairs))
    for index in range(len(pairs) - 1, -1, -1):
        weight, bias = pairs[index]
        source = values[index]
        grad_weight = []
        for step in range(len(weight)):
            grad_weight.append(tuple(
                sum(source[row][step] * delta[row][column]
                    for row in range(rows))
                for column in range(len(weight[step]))))
        grads[2 * index] = tuple(grad_weight)
        grads[2 * index + 1] = tuple(
            sum(delta[row][column] for row in range(rows))
            for column in range(len(bias)))
        if index:
            gated = pre[index - 1]
            handed = []
            for row in range(rows):
                handed.append(tuple(
                    sum(delta[row][column] * weight[step][column]
                        for column in range(len(weight[step])))
                    if gated[row][step] > zero else zero
                    for step in range(len(weight))))
            delta = tuple(handed)
    return loss, tuple(grads)


def _flat(grad):
    """One gradient as a flat row-major tuple of `Rational`s: a nested weight
    is unrolled row by row, a flat bias is already flat."""
    if grad and isinstance(grad[0], tuple):
        return tuple(cell for row in grad for cell in row)
    return tuple(grad)


def _gradients(name, dataset):
    """The exact gradient of `name`'s composite on `dataset`, keyed by tensor
    name, each flattened row-major in the tensor's own shape."""
    inputs, targets = dataset
    _, grads = _composite(_nested_params(name), inputs, targets)
    return dict((tensor_name, _flat(grad))
                for tensor_name, grad in zip(MODEL_PARAMS[name], grads))


def _updated(params, grads, rate):
    """`theta - rate * grad` for every tensor, all gradients computed first."""
    out = []
    for tensor, grad in zip(params, grads):
        if grad and isinstance(grad[0], tuple):
            out.append(tuple(
                tuple(cell - rate * g for cell, g in zip(row, grow))
                for row, grow in zip(tensor, grad)))
        else:
            out.append(tuple(cell - rate * g
                             for cell, g in zip(tensor, grad)))
    return tuple(out)


def _train(name, dataset, steps):
    """The exact loss after each of the first `steps` plain SGD steps on
    `name`'s composite over `dataset`, at `LEARNING_RATE`.

    Plain SGD means: the gradient is taken at the current parameters, every
    parameter is updated once, and the next loss is recomputed from the
    updated parameters — never from a stale one.
    """
    inputs, targets = dataset
    params = _nested_params(name)
    losses = []
    for _ in range(steps):
        loss, grads = _composite(params, inputs, targets)
        losses.append(loss)
        params = _updated(params, grads, LEARNING_RATE)
    return tuple(losses)


def _loss(name, dataset):
    """The composite's loss at the fixture's own weights."""
    inputs, targets = dataset
    return _composite(_nested_params(name), inputs, targets)[0]


#: How many steps `EXPECTED_LOSS` freezes. Eight, not `STEPS`: see the module
#: docstring's exactness budget — the two-layer loss's denominator is already
#: 11661 bits by step 8 and multiplies by about `4 * D**3` per step.
EXPECTED_STEPS = 8

#: The exact loss of `MODELS["mlp"]` on `XOR` after each of the first
#: `EXPECTED_STEPS` plain SGD steps at `LEARNING_RATE`, starting from
#: `MODELS["mlp"]` itself: `(1, ...)`, strictly decreasing. **These are the
#: numbers stage 10's capstone must reproduce, `Rational` for `Rational`.**
EXPECTED_LOSS = _train("mlp", XOR, EXPECTED_STEPS)

#: The exact gradient of the `"mlp"` composite on `XOR` at the initial
#: weights, keyed by `MODEL_PARAMS["mlp"]`, each a flat row-major tuple of
#: `Rational`s in that tensor's shape. It already carries the mean's `1/4`, so
#: the first SGD update is `w1 - LEARNING_RATE * REFERENCE_GRADIENTS["w1"]`.
REFERENCE_GRADIENTS = types.MappingProxyType(_gradients("mlp", XOR))
