"""Autograd From Scratch — stage 10: The capstone: the step (implementation)

Nine stages built the engine: the graph and its order, the local derivatives,
the reduction of a broadcast gradient, the chain rule through a matrix, the
accumulation and the reuse, the seed, the detach, the kink, the oracle. This
file spends all of it on one training run and does no arithmetic of its own:
every value is `exact`'s, every gradient is the walk's, no shape is chosen here
and no tolerance exists to choose. What it adds is the *step* — the moves that
turn a graph into learning: read the gradients, move each parameter once,
rebuild the loss from the moved parameters, remember the loss the step was
taken at.

`sgd(params, *, learning_rate)` is the move: `theta <- theta - learning_rate *
grad`, for every parameter, exactly. The learning rate is an `exact.Rational`
(an `int` is promoted — `Rational(2)` is `2/1` — and a float has no exact pair
and is refused), the product is `exact`'s, and every gradient is read *before*
any update is produced: that ordering is part of the contract. `sgd` returns
the updated values; it does not write them, so the caller owns the transaction
and `train` is the one place a parameter's `value` is replaced.

`train(model, data, *, steps, learning_rate)` is the loop. A model is a
`(params, forward)` pair: the parameter leaves in `MODELS`' order, and the
callable the earlier stages already wrote — `stage_04.mlp` takes exactly
`(params, x)` and returns the pre-loss output node, for one layer or three,
with every extent read from `params` and never from a hard-coded shape. `data`
is the fixture's `(inputs, targets)` as `exact.Tensor`s. Every step builds a
**fresh** graph: the output, the residual `out - targets`, and the mean of its
square, `mean(mul(residual, residual))` — the fixture's own composite, with
`mean`'s `1/4` already inside it, so `sgd` needs no second factor. Then
`zero_grad`, `backward`, `sgd`, and the new values are written back into the
leaves. The loss is recorded **before** the update, so the tuple is the loss
at the parameters each step started from — its first entry is the loss at the
fixture's own weights, exactly `1` for the 2 -> 4 -> 1 model on `XOR` — and the
next step's loss is rebuilt from the updated values, never from a stale node.

`reproduce_reference()` is the interlock with the rest of the repository: the
same run, at `fixtures.LEARNING_RATE` and `fixtures.EXPECTED_STEPS`, on the
fixture the references are frozen on, against both references `fixtures`
holds. It checks the initial loss (exactly `1`), the initial gradients
(`Rational` for `Rational`, cell by cell) and every loss of the run step for
step, and it returns the gradients it reproduced — the engine's own answer,
computed by `backward`, never the fixture's numbers echoed back.

DESIGN DECISION — why does `sgd` produce every update before writing anything?
    A step is `theta <- theta - learning_rate * grad`, with the gradient taken
    at the parameters the step *started* from. `backward` has already filled
    the `grad` fields, so the ordering is not a race here — but it is the
    contract, and it is what makes `sgd` a pure function of its arguments: it
    reads every gradient, builds every updated value and returns them, leaving
    the parameter nodes exactly as it found them. `train` is then the only
    writer, in one loop over the returned tuple, so no parameter is skipped and
    none is moved twice.

DESIGN DECISION — why is the loss rebuilt from the engine at every step?
    A node's value is fixed at the moment it was built, so a loop that kept the
    first loss node would report the initial loss at every step, and a loop
    that kept the whole graph would accumulate into the parameters' `grad`
    fields a second time. Each step therefore builds its own graph from the
    current leaves: a fresh `Node` over the fixture's inputs, the model's
    output, the residual and the mean. The loss is recorded before the update
    — it belongs to the parameters the step was taken at — and the *next*
    loss is the one built from the updated leaves, which is what "the loss
    falls strictly" means in this course.

DESIGN DECISION — why is the loss the mean of the squared residual?
    The fixture's composite is `mean((out - y)**2)` over the rows, and the
    `1/4` of the mean is *inside* the loss, which is why `fixtures.LEARNING_RATE`
    is the stable step and why `sgd` applies no second factor. A sum instead of
    a mean is `n` times too large — the step is `n` times too long and the run
    diverges — and a mean over the wrong count (`axis=0` over four rows) is
    right only when the counts coincide, which they never do. The claim the
    stage is graded on is exact: the loss at the fixture's weights is exactly
    `1`, and `reproduce_reference` compares every one of the eight to the
    fixture's own independent computation.

DESIGN DECISION — why must `learning_rate` be an `exact.Rational`?
    Because a float has no exact pair, and the whole course is compared with
    `==` and never with a tolerance. `0.25` is not `Rational(1, 4)`: the first
    has no `numerator` and no `denominator`, its product with a `Rational` is a
    float, and the first step that passes through it makes every later gradient
    a rounded number — the run still trains, and the numbers stop being exact.
    An `int` is promoted at the door (`Rational(2)`), a `bool` is refused (an
    `int` that means "yes"), and a float is refused by name, the same refusal
    the oracle makes for a step (§1).

DESIGN DECISION — why does `reproduce_reference` verify instead of merely
returning?
    Returning the engine's gradients is not the interlock: the interlock is the
    *agreement* of two independent computations — the fixture's own, written
    out element by element in `fixtures.py`, and the engine's — and an
    agreement nobody checks is a claim. So the function compares the run with
    `fixtures.EXPECTED_LOSS` step for step and each tensor's gradient with
    `fixtures.REFERENCE_GRADIENTS` cell by cell, naming the tensor, the index
    and both exact pairs at the first disagreement, and returns the gradients
    only once every one of them agrees. A tolerance, a float comparison or a
    comparison of a length would each be a decision to accept a wrong answer,
    and the reference exists precisely so that no such decision is available.
"""

import exact
import fixtures
import stage_01
import stage_03
import stage_04

#: The fixture the two frozen references are computed on. `fixtures` keys both
#: references by this model's tensor names, so the name is the one place the
#: capstone and the fixture can disagree about *which* model is reproduced.
_REFERENCE_MODEL = "mlp"
#: The two numbers this file compares against, as exact `Rational`s.
_ONE = exact.Rational(1)
_HALF = exact.Rational(1, 2)


def _pair(cell):
    """A `Rational` written `numerator/denominator`: a refusal names both
    numbers of a pair, never a rounded one of them."""
    return "%d/%d" % (cell.numerator, cell.denominator)


def _rate(op, learning_rate):
    """The learning rate as an exact `Rational`, or the refusal naming it.

    An `int` is promoted the way `exact` promotes one everywhere — exactly,
    `Rational(2)`, never a division — and anything else (a float, a string, a
    `bool`, `None`) has no exact pair and is refused, because a float in the
    step would make every gradient of the run a rounded number.
    """
    if isinstance(learning_rate, exact.Rational):
        return learning_rate
    if isinstance(learning_rate, int) and not isinstance(learning_rate, bool):
        return exact.Rational(learning_rate)
    raise exact.ExactError(
        "%s: learning_rate=%r is neither an int nor an exact.Rational"
        % (op, learning_rate))


def _parameters(op, params):
    """The parameters to update: a non-empty sequence of distinct, trainable
    `Node`s whose gradients have their operands' shapes, or the refusal naming
    the offender and both numbers.

    The four guards are the four ways a step goes wrong quietly: a parameter
    that is not a node has no gradient to read, a frozen one (`requires_grad`
    is `False` — the stop node stage 5 hands back) must not move, a parameter
    named twice would be moved twice in one step, and a gradient whose shape is
    not its value's would broadcast into the update instead of subtracting
    element by element (§3 invariant 2).
    """
    if not isinstance(params, (tuple, list)):
        raise exact.AutogradError(
            "%s: params=%r is not a sequence of Nodes" % (op, params))
    nodes = tuple(params)
    if not nodes:
        raise exact.AutogradError(
            "%s: params is empty, and a step has parameters to move" % (op,))
    for index, node in enumerate(nodes):
        if not isinstance(node, stage_01.Node):
            raise exact.AutogradError(
                "%s: params[%d]=%r is not a Node" % (op, index, node))
        if not node.requires_grad:
            raise exact.AutogradError(
                "%s: params[%d] is frozen (requires_grad=False), and a frozen "
                "parameter is not updated" % (op, index))
        if node.grad.shape != node.value.shape:
            raise exact.AutogradError(
                "%s: params[%d] has value shape %r and grad shape %r, and a "
                "gradient has its operand's shape"
                % (op, index, node.value.shape, node.grad.shape))
        if any(other is node for other in nodes[:index]):
            raise exact.AutogradError(
                "%s: params[%d] is %r, which params already names, and a "
                "parameter is updated once" % (op, index, node))
    return nodes


def _model(op, model):
    """The `(params, forward)` pair, once both halves are what they must be."""
    if not isinstance(model, (tuple, list)) or len(model) != 2:
        raise exact.AutogradError(
            "%s: model=%r is not a (params, forward) pair" % (op, model))
    params, forward = model
    if not callable(forward):
        raise exact.AutogradError(
            "%s: the model's forward %r is not callable" % (op, forward))
    return _parameters(op, params), forward


def _data(op, data):
    """The `(inputs, targets)` pair of rank-2 `exact.Tensor`s, or the refusal.

    Both are rank 2 because both are batches: the targets are subtracted from
    the output element by element, so a rank-1 target would broadcast against
    the output's columns instead of subtracting — a `(4, 1)` output and a
    `(4,)` target make a `(4, 4)` residual that runs, trains and computes the
    wrong loss.
    """
    if not isinstance(data, (tuple, list)) or len(data) != 2:
        raise exact.AutogradError(
            "%s: data=%r is not an (inputs, targets) pair" % (op, data))
    inputs, targets = data
    for name, tensor in (("inputs", inputs), ("targets", targets)):
        if not isinstance(tensor, exact.Tensor):
            raise exact.AutogradError(
                "%s: the data's %s %r is not an exact.Tensor"
                % (op, name, tensor))
    for name, tensor in (("inputs", inputs), ("targets", targets)):
        if len(tensor.shape) != 2:
            raise exact.ExactError(
                "%s: the data's %s have shape %r, and a batch is rank 2: %d"
                % (op, name, tensor.shape, tensor.size))
    return inputs, targets


def sgd(params, *, learning_rate):
    """The plain SGD step: `theta - learning_rate * grad`, for every parameter,
    returned in the order `params` gives them and written nowhere.

    `params` is a non-empty sequence of distinct, trainable `stage_01.Node`s
    whose gradients are already filled — by `backward`, at the parameters this
    step started from — and `learning_rate` is an `exact.Rational` (an `int` is
    promoted; a float, a `bool` and anything else are refused). Every gradient
    is read into `gradients` *before* the loop, every updated value is built
    from the value the node had and the gradient it carries, and the tuple
    comes back without one node's `value` or `grad` having changed: a
    parameter appears once, is moved once, and the step is a function of its
    arguments.

    A gradient whose shape is not its value's, a parameter named twice, a
    frozen parameter and a parameter that is not a node are each refused,
    naming the offender and both numbers.
    """
    nodes = _parameters("sgd", params)
    rate = _rate("sgd", learning_rate)
    gradients = tuple(node.grad for node in nodes)
    updates = []
    for node, gradient in zip(nodes, gradients):
        scale = exact.full(gradient.shape, rate)
        updates.append(exact.sub(node.value, exact.mul(gradient, scale)))
    return tuple(updates)


def _loss(forward, params, inputs, targets):
    """One exact squared-error loss of `forward(params, inputs)` against
    `targets`, as a fresh graph of this stage's own making.

    `x` and `y` are fresh leaves over the fixture's tensors, the output is the
    forward the caller handed in (never a model this module knows), and the
    loss is the fixture's composite `mean((out - y) ** 2)` — `stage_03.sub`,
    `stage_03.mul` and `stage_03.mean`, so the `1/n` of the mean is inside the
    value and `sgd` needs no second factor. The output must be a `Node` and
    must be shaped like the targets: anything else is refused here, naming both
    shapes and both numbers, instead of broadcasting into a residual of the
    wrong shape.
    """
    x = stage_01.Node(inputs)
    y = stage_01.Node(targets)
    out = forward(params, x)
    if not isinstance(out, stage_01.Node):
        raise exact.AutogradError(
            "the model's forward returned %r instead of a Node, and a training "
            "run differentiates a graph" % (out,))
    if out.value.shape != targets.shape:
        raise exact.AutogradError(
            "the model's output has shape %r and the targets have shape %r: "
            "%d and %d cells"
            % (out.value.shape, targets.shape, out.value.size, targets.size))
    residual = stage_03.sub(out, y)
    return stage_03.mean(stage_03.mul(residual, residual))


def train(model, data, *, steps, learning_rate):
    """One exact training run: `steps` plain SGD steps on `model` over `data`,
    and the loss at the parameters each step started from, in order.

    `model` is a `(params, forward)` pair — the trainable `stage_01.Node`
    leaves, in the fixture's `(weight, bias)` per-layer order, and the callable
    that turns them and an input node into the output node (`stage_04.mlp`
    does, for any number of layers) — and `data` is `(inputs, targets)`, rank-2
    `exact.Tensor`s. `steps` is a non-negative `int` and `learning_rate` an
    `exact.Rational`.

    Each step: build the loss from the *current* leaves, record its value
    (a `Rational`, before the update), clear the graph, `backward`, take the
    updated values from `sgd`, and write them back into the leaves. The result
    is a tuple of `steps` exact `Rational`s — the first is the loss at the
    fixture's own weights — and the leaves end holding the trained weights, so
    the caller can read the model afterwards.
    """
    nodes, forward = _model("train", model)
    rate = _rate("train", learning_rate)
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise exact.ExactError(
            "train: steps=%r is not a non-negative count" % (steps,))
    inputs, targets = _data("train", data)
    losses = []
    for _ in range(steps):
        loss = _loss(forward, nodes, inputs, targets)
        if loss.value.shape != ():
            raise exact.AutogradError(
                "train: the loss has shape %r, and a step differentiates a "
                "scalar" % (loss.value.shape,))
        losses.append(loss.value.cells[0])
        stage_01.zero_grad(loss)
        stage_01.backward(loss)
        updated = sgd(nodes, learning_rate=rate)
        for node, value in zip(nodes, updated):
            node.value = value
    return tuple(losses)


def _same_initial_loss(loss):
    """The loss at the fixture's own weights, which the fixture freezes as
    exactly `1`: every residual of the 2 -> 4 -> 1 model on `XOR` is `+/-1`
    before the first step."""
    if loss != _ONE:
        raise exact.AutogradError(
            "reproduce_reference: the loss at fixtures.MODELS[%r]'s own weights "
            "is %s, not exactly 1" % (_REFERENCE_MODEL, _pair(loss)))


def _same_gradients(reproduced):
    """Every tensor's gradient against `fixtures.REFERENCE_GRADIENTS`, cell by
    cell, as exact `Rational` pairs.

    The first cell that disagrees is named with its tensor, its index and both
    exact numbers plus their exact difference; a tensor whose cell count
    differs from the reference's is named too. There is no tolerance anywhere
    in this course, so the comparison is `==` on the pairs.
    """
    for name in fixtures.MODEL_PARAMS[_REFERENCE_MODEL]:
        got = reproduced[name]
        want = tuple(fixtures.REFERENCE_GRADIENTS[name])
        if got == want:
            continue
        for index, (cell, reference) in enumerate(zip(got, want)):
            if cell != reference:
                raise exact.AutogradError(
                    "reproduce_reference: the gradient of %s disagrees with "
                    "the reference at index %d of %d: %s and %s, off by %s"
                    % (name, index, len(want), _pair(cell), _pair(reference),
                       _pair(cell - reference)))
        raise exact.AutogradError(
            "reproduce_reference: the gradient of %s has %d cells and the "
            "reference has %d" % (name, len(got), len(want)))


def _same_losses(losses):
    """Every loss of the run against `fixtures.EXPECTED_LOSS`, step for step:
    the loss at the parameters the step started from, exactly."""
    expected = tuple(fixtures.EXPECTED_LOSS)
    if len(losses) != len(expected):
        raise exact.AutogradError(
            "reproduce_reference: the run has %d losses and the reference "
            "freezes %d" % (len(losses), len(expected)))
    for index, (got, want) in enumerate(zip(losses, expected)):
        if got != want:
            raise exact.AutogradError(
                "reproduce_reference: the loss at index %d of %d is %s and the "
                "reference has %s, off by %s"
                % (index, len(expected), _pair(got), _pair(want),
                   _pair(got - want)))


def _learned(forward, nodes, inputs, targets):
    """Every trained prediction on the correct side of `1/2` — what "XOR
    learned inside `EXPECTED_STEPS`" means, read off the trained leaves."""
    out = forward(nodes, stage_01.Node(inputs))
    if not isinstance(out, stage_01.Node) or out.value.shape != targets.shape:
        raise exact.AutogradError(
            "reproduce_reference: the trained model returned %r against targets "
            "of shape %r" % (out, targets.shape))
    for index, (cell, target) in enumerate(zip(out.value.cells, targets.cells)):
        if (cell > _HALF) != (target > _HALF):
            raise exact.AutogradError(
                "reproduce_reference: the prediction for row %d is on the wrong "
                "side of 1/2 (the target is %s), and the reproduction holds "
                "only when every prediction is on the correct side of 1/2"
                % (index, _pair(target)))


def reproduce_reference():
    """The fixture's own training run, by the engine, against both of the
    fixture's frozen references; returns the reproduced gradients.

    The run is `fixtures.MODELS["mlp"]` on `fixtures.XOR`, at
    `fixtures.LEARNING_RATE` for `fixtures.EXPECTED_STEPS` steps, built by
    `train` from `stage_04.mlp` — no shape, no count and no learning rate of
    this module's own beyond the fixture's. The initial loss must be exactly
    `1`; the gradients `backward` leaves on the four leaves must equal
    `fixtures.REFERENCE_GRADIENTS`, `Rational` for `Rational`; every loss of
    the run must equal `fixtures.EXPECTED_LOSS`, step for step; and the trained
    leaves must classify `XOR` — every prediction on the correct side of `1/2`
    inside eight steps. The return value is the engine's own answer: a mapping
    from each tensor's name to its flat, row-major tuple of `Rational`s, equal
    to `fixtures.REFERENCE_GRADIENTS`.
    """
    names = fixtures.MODEL_PARAMS[_REFERENCE_MODEL]
    nodes = tuple(stage_01.Node(tensor)
                  for tensor in fixtures.MODELS[_REFERENCE_MODEL])
    inputs, targets = fixtures.XOR
    loss = _loss(stage_04.mlp, nodes, inputs, targets)
    _same_initial_loss(loss.value.cells[0])
    stage_01.zero_grad(loss)
    stage_01.backward(loss)
    reproduced = dict((name, tuple(node.grad.cells))
                      for name, node in zip(names, nodes))
    _same_gradients(reproduced)
    losses = train((nodes, stage_04.mlp), fixtures.XOR,
                   steps=fixtures.EXPECTED_STEPS,
                   learning_rate=fixtures.LEARNING_RATE)
    _same_losses(losses)
    _learned(stage_04.mlp, nodes, inputs, targets)
    return reproduced
