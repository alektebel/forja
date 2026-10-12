"""Autograd From Scratch — stage 10: The capstone: the step

Nine stages have built the engine: the graph and its order, the local
derivatives, the reduction of a broadcast gradient, the chain rule through a
matrix, the accumulation and the reuse, the seed, the detach, the kink, the
oracle. This stage spends all of it on the one thing the course exists for — a
training run, exact from end to end.

`sgd(params, *, learning_rate)` reads each parameter's gradient and moves it,
`theta <- theta - learning_rate * grad`, every parameter exactly once, with
every gradient read before any update is produced. `train(model, data, *,
steps, learning_rate)` drives the loop: a model is a `(params, forward)` pair —
the parameter leaves and the callable the earlier stages wrote (`stage_04.mlp`
takes `(params, x)` and returns the pre-loss output node) — `data` is the
fixture's `(inputs, targets)` as `exact.Tensor`s, one loss is built from the
engine at every step, `backward` fills the gradients, `sgd` moves the
parameters, and the loss each step was taken at comes back in order, each an
exact `Rational`. `reproduce_reference()` is the course's own interlock: the
2 -> 4 -> 1 model the fixtures fix, trained by this engine alone, must
reproduce `fixtures.EXPECTED_LOSS` step for step and
`fixtures.REFERENCE_GRADIENTS` `Rational` for `Rational`, and it returns the
latter.

DESIGN DECISION — why does `sgd` produce every update before writing anything?
    A step's gradient belongs to the parameters the step *started* from, and
    `backward` has already filled the `grad` fields, so the ordering is not a
    race in this engine — but it is the contract, and it is what makes `sgd` a
    pure function of its arguments: it reads every gradient, builds every
    updated value and returns them, leaving the parameter nodes exactly as it
    found them. `train` is then the only writer, in one loop over the returned
    tuple, so no parameter is skipped and none is moved twice. An
    implementation that wrote each parameter as it went would still be right on
    a graph whose gradients do not depend on the parameters' values, which is
    why the fixture is a model whose second layer reads the first.

DESIGN DECISION — why is the loss rebuilt from the engine at every step?
    A node's value is fixed at the moment it was built, so a loop that kept the
    first loss node would report the initial loss at every step, and a loop
    that kept the whole graph would accumulate into the parameters' `grad`
    fields a second time. Each step therefore builds its own graph from the
    current leaves, and the loss it records belongs to the parameters the step
    was taken at — recorded *before* the update, which is what makes the
    sequence the loss at each step's start and its first entry the loss at the
    fixture's own weights.

DESIGN DECISION — why is the loss the mean of the squared residual?
    The fixture's composite is `mean((out - y) ** 2)` over the rows, and
    `mean`'s `1/4` is *inside* the loss, which is why `fixtures.LEARNING_RATE`
    is the stable step and why `sgd` applies no second factor. A sum instead of
    a mean is `n` times too large — the step is `n` times too long and the run
    diverges — and a mean over the wrong count is right only where the counts
    happen to coincide. The claim the stage is graded on is exact: the loss at
    the fixture's weights is exactly `1`.

DESIGN DECISION — why must `learning_rate` be an exact `Rational`?
    Because a float has no exact pair, and this course compares with `==` and
    never with a tolerance. `0.25` is not `Rational(1, 4)`: it has no
    `numerator` and no `denominator`, its product with a `Rational` is a float,
    and the first step that passes through it makes every later gradient a
    rounded number — the run still trains, and the numbers stop being exact. An
    `int` is promoted at the door (`Rational(2)` is `2/1`), a `bool` is refused
    (an `int` that means "yes"), and a float is refused by name, as the oracle
    refuses a step.

DESIGN DECISION — why does `reproduce_reference` verify instead of merely
returning?
    Returning the engine's gradients is not the interlock. The interlock is the
    *agreement* of two independent computations — the fixture's own, written
    out element by element in `fixtures.py`, and the engine's — and an
    agreement nobody checks is a claim. So the function compares the run with
    `fixtures.EXPECTED_LOSS` step for step and every tensor's gradient with
    `fixtures.REFERENCE_GRADIENTS` cell by cell, naming the tensor, the index
    and both exact pairs at the first disagreement, and returns the gradients
    only once every one agrees. A tolerance, a float comparison, or a
    comparison of a length alone would each be a decision to accept a wrong
    answer, and the reference exists precisely so that no such decision is
    available.

TODO: implement `sgd`, `train` and `reproduce_reference`.
"""

import exact
import fixtures
import stage_01
import stage_03
import stage_04


def sgd(params, *, learning_rate):
    """The plain SGD step: `theta - learning_rate * grad`, for every parameter,
    returned in the order `params` gives them and written nowhere.

    `params` is a non-empty sequence of distinct, trainable `stage_01.Node`s
    whose gradients are already filled — by `backward`, at the parameters this
    step started from — and `learning_rate` is an `exact.Rational` (an `int` is
    promoted; a float, a `bool` and anything else are refused). Every gradient
    is read before the loop builds anything, so the step is a function of its
    arguments and the parameter nodes come back untouched. A gradient whose
    shape is not its value's, a parameter named twice, a frozen parameter and a
    parameter that is not a node are each refused, naming the offender and both
    numbers.
    """
    raise NotImplementedError("stage 10: implement sgd()")


def train(model, data, *, steps, learning_rate):
    """One exact training run: `steps` plain SGD steps on `model` over `data`,
    and the loss at the parameters each step started from, in order.

    `model` is a `(params, forward)` pair — the trainable `stage_01.Node`
    leaves, in the fixture's `(weight, bias)` per-layer order, and the callable
    that turns them and an input node into the output node (`stage_04.mlp`
    does, for any number of layers) — and `data` is `(inputs, targets)`, rank-2
    `exact.Tensor`s. `steps` is a non-negative `int` and `learning_rate` an
    `exact.Rational`.

    Each step: build the loss from the *current* leaves, record its value (a
    `Rational`, before the update), clear the graph, `backward`, take the
    updated values from `sgd`, and write them back into the leaves. The result
    is a tuple of `steps` exact `Rational`s — the first is the loss at the
    fixture's own weights — and the leaves end holding the trained weights.
    """
    raise NotImplementedError("stage 10: implement train()")


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
    leaves must classify `XOR` inside the budget. The return value is the
    engine's own answer: a mapping from each tensor's name to its flat,
    row-major tuple of `Rational`s, equal to `fixtures.REFERENCE_GRADIENTS`.
    """
    raise NotImplementedError("stage 10: implement reproduce_reference()")
