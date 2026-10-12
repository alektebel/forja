"""Autograd From Scratch — stage 9: The oracle (implementation)

The engine is finished below this stage: `backward` walks the graph in reverse
topological order and leaves every node the gradient of the value above it, in
exact `Rational`s, accumulated and never assigned. This stage writes the thing
that checks it — the one place in the course where a derivative is obtained a
second, independent way — and it is the reason the rest of the course can be
believed. A central difference `(f(x + h) − f(x − h)) / 2h` is a derivative read
off `exact`'s own arithmetic and nothing else: it knows nothing of the graph,
the local derivatives or the chain rule, so when `gradient_check` reports an
agreement, two unrelated computations agree on the same exact pair.

The contract is deliberately narrow. `fn` maps the leaf `Node` it is handed to
another `Node` — a graph, not a bare value, because the very same `fn` is handed
to `backward` next and a value has no graph to walk — and that node's value must
be a scalar, because a gradient is what `backward` leaves on a leaf of `x`'s
shape only when the root is the scalar it seeds with `ones` (a non-scalar root
is stage 6's seed). The step `h` is an exact `Rational`: an `int` is converted
at the door and never halved with `//`, so the difference is divided by `2h`
exactly whatever `h` is. The result is a `Tensor` of `x`'s value's shape — the
shape a gradient has (§3 invariant 2) — and every cell is an exact `Rational`
pair, so the comparison is an equality and never a test of nearness.

The fact this stage is built on: for a polynomial of degree at most two the
central difference is *exactly* the derivative, for every non-zero `h` — each
side's `h²` cancels against the `2h` — while a cubic's central difference is the
derivative plus exactly `h²`. The check probes the first at two different `h`
per fixture and the second on a cubic, where the refusal's own numbers carry
the `h²` and the comparison must be exact enough to see it: at `x = 2^60` the
cubic's difference is off by exactly `1` in a number of 121 bits, which no float
and no tolerance would ever call different.

DESIGN DECISION — why is `fn` handed a `Node` and why must it hand one back?
    A gradient is read off a node, not off a value: `backward` leaves it in a
    leaf's `grad` field, and the oracle has to differentiate at *that* leaf or
    it is checking a different function. So `x` is a leaf `Node` and `fn` is a
    function from the graph's world to the graph's world — it builds its
    operations from the node it is handed, and the check can read the leaf
    afterwards. The oracle only ever *reads* values, so a `fn` returning a bare
    `exact.Tensor` would run and even answer correctly, which is exactly why it
    must be refused: the same `fn` is handed to `backward` next, where a value
    has no graph to walk and the caller would get zeros instead of a refusal.
    For the perturbed evaluations the oracle builds its own fresh leaf — the
    value `x ± h·e_at`, no parents — so the step moves the point and can never
    disturb the graph the caller built.

DESIGN DECISION — why must the node `fn` returns hold a scalar?
    `backward` seeds the root with `ones` of the root's shape, so only a scalar
    root leaves a leaf of `x`'s shape holding the derivative of the whole
    output. A non-scalar root is the seed of stage 6 — a `(2,)` output needs a
    `(2,)` seed and its gradient is a matrix — and an oracle that quietly
    differentiated the first cell of a `(2,)` output, or the sum of its cells,
    would be comparing two different functions. The refusal names the shape and
    the cell count, and the stage's `fn`s are scalar, so the oracle is
    unambiguous: one number per coordinate of `x`.

DESIGN DECISION — why central and not one-sided?
    A one-sided difference `(f(x + h) − f(x)) / h` is off by `h·f''(x)/2`
    exactly, and for a degree-two polynomial that is `h·c`: the oracle would
    fail on its own fixtures, whose whole point is an equality that holds for
    every step. The central difference is off by `h²·f'''(x)/6` — the odd terms
    cancel — so it is *exact* for every polynomial of degree at most two, at
    every `h`, which is a statement an exact-arithmetic course can prove by
    running it: the same quadratic at two different steps gives the same
    gradient, and the cubic's difference is `h²` whatever `x` is. A central
    difference costs two evaluations instead of one and buys an equality.

DESIGN DECISION — why is `h` an exact `Rational`, and why is a step of zero
refused?
    An `int` step is a `Rational` — `Rational(3)` is `3/1` — so it is converted
    once, at the door, and the difference is divided by `2h` exactly; an
    implementation that halved an int with `//` would answer `1` for `h = 3/2`,
    a step no caller asked for. A zero step is not a step: `(f(x) − f(x)) / 0`
    is `0/0`, every coordinate would come out as a refusal from deep inside
    `exact` or, worse, as zeros if a `0` in the divisor were tolerated. The
    refusal names `h` at the door, and a step that is neither an `int` nor a
    `Rational` — a bool, a string, a float — is refused for the same reason the
    course refuses them everywhere: a float has no exact pair to compare.

DESIGN DECISION — why is the comparison an equality of `Rational` pairs, and
what does a cubic's `h²` have to do with it?
    A tolerance is a decision to accept a wrong answer, and it hides the very
    thing this stage exists to show. `==` on `Rational` pairs is exact,
    symmetric, and can never be fooled by a rounded float: `3·2^120 + 1` and
    `3·2^120` are different pairs although a float comparison — or a
    numerator-only, or a `1/1000` tolerance — calls them equal. So the check
    compares the finite difference with `x.grad` cell by cell and refuses at
    the first pair that differs, naming the cell and both numbers. The
    quadratic's difference is *equal* to the derivative, for two different `h`;
    the cubic's is off by exactly `h²`, an amount proportional to `h²` and read
    off the refusal, so both halves of the equality are exercised.

DESIGN DECISION — why does `gradient_check` clear the graph before its own
backward?
    `backward` accumulates, never assigns, and that is the invariant stage 5
    proved: a second call on an uncleared graph doubles what the first left.
    The oracle's check is not a step of training, so it must not depend on
    whatever the caller's graph was holding — it clears the root's graph (and
    the leaf itself, in case `fn` never reached it) and then runs its own
    backward, so the answer is the derivative of *this* function at *this*
    point, not the sum of every backward the caller ever ran.
"""

import exact

from stage_01 import Node, backward, zero_grad


def _pair(cell):
    """A `Rational` written `numerator/denominator`.

    A refusal names both numbers of a pair, never a rounded one of them, so a
    caller reading a message can see the exact amount two gradients differ by.
    """
    return "%d/%d" % (cell.numerator, cell.denominator)


def _point(op, x):
    """The leaf the oracle differentiates at, or the refusal naming it."""
    if not isinstance(x, Node):
        raise exact.AutogradError(
            "%s: x=%r is not a Node, and a gradient is read off a node"
            % (op, x))
    return x


def _step(op, h):
    """The step as an exact `Rational`, or the refusal naming it.

    An `int` is promoted the way `exact` promotes one everywhere — exactly,
    `Rational(h)`, and never `h // 2` — and anything else (a bool, a float, a
    string) has no exact pair and is refused. A zero step would divide the
    difference by zero, so it is refused here, naming `h`, instead of being
    discovered cell by cell.
    """
    if isinstance(h, exact.Rational):
        step = h
    elif isinstance(h, int) and not isinstance(h, bool):
        step = exact.Rational(h)
    else:
        raise exact.ExactError(
            "%s: h=%r is neither an int nor an exact.Rational" % (op, h))
    if step.numerator == 0:
        raise exact.ExactError(
            "%s: h=%s is zero, and a central difference divides by 2h"
            % (op, _pair(step)))
    return step


def _function(op, fn):
    """`fn`, once it is something that can be called."""
    if not callable(fn):
        raise exact.AutogradError("%s: fn=%r is not callable" % (op, fn))
    return fn


def _graph(op, fn, x):
    """`fn(x)`, once it is the `Node` both halves of the oracle need."""
    node = fn(x)
    if not isinstance(node, Node):
        raise exact.AutogradError(
            "%s: fn returned %r instead of a Node: the oracle reads its value "
            "and the check walks its graph" % (op, node))
    return node


def _value(op, node):
    """The one cell of `node`'s value, once that value is a scalar.

    `backward` seeds a root with `ones` of the root's shape, so a gradient is
    the derivative of the whole output only where the output is a scalar; a
    node with a `(2,)` value is stage 6's seed, and reading one cell of it
    would silently differentiate a different function.
    """
    if node.value.shape != ():
        raise exact.AutogradError(
            "%s: fn returned a value of shape %r (%d cells), and the oracle "
            "differentiates a scalar: a non-scalar output is the seed of "
            "stage 6" % (op, node.value.shape, node.value.size))
    return node.value.cells[0]


def _shift(x, at, by):
    """The leaf `fn` is handed for one perturbation: `x`'s value with the one
    cell `at` moved by `by`, as a fresh leaf with no parents.

    This is `x + h·e_at` (or `x − h·e_at`): the step moves along one
    coordinate and every other coordinate stays where it was, which is what
    makes the quotient a partial derivative instead of a directional one. The
    leaf is fresh because the oracle must not touch the caller's graph.
    """
    cells = list(x.value.cells)
    cells[at] = cells[at] + by
    return Node(exact.Tensor(tuple(cells), x.value.shape))


def finite_difference(fn, x, h):
    """The central difference of `fn` at the leaf `x`, one column per
    coordinate, as a `Tensor` of `x`'s value's shape.

    `fn` takes the leaf `Node` it is handed and returns a `Node` whose value is
    a scalar (`fn(x)` is the graph whose value the derivative belongs to); `x`
    is a leaf `Node` and `h` is an `int` or an `exact.Rational` step, converted
    to a `Rational` and never zero. For every coordinate `at` of `x` the oracle
    evaluates `fn` at the leaf `x + h·e_at` and at the leaf `x − h·e_at` and
    divides the difference of the two values by `2h`, exactly, so the cell `at`
    of the result is `(f(x + h·e_at) − f(x − h·e_at)) / 2h`. Every other
    coordinate is left where it was, which is what makes the result a gradient:
    one column per coordinate, not a difference along a diagonal.

    Nothing here touches a graph's gradients: `fn` is called for its value
    only, on fresh leaves, and `x`'s own `grad` is left exactly as it was. A
    `fn` that returns something other than a `Node`, or a `Node` whose value is
    not a scalar, an `x` that is not a `Node`, a `fn` that is not callable and a
    step that is zero or not a number are refused, each naming the offender.
    """
    _point("finite_difference", x)
    step = _step("finite_difference", h)
    _function("finite_difference", fn)
    span = step + step
    cells = []
    for at in range(x.value.size):
        plus = _shift(x, at, step)
        minus = _shift(x, at, -step)
        high = _value("finite_difference", _graph("finite_difference", fn, plus))
        low = _value("finite_difference", _graph("finite_difference", fn, minus))
        cells.append((high - low) / span)
    return exact.Tensor(tuple(cells), x.value.shape)


def gradient_check(fn, x, h):
    """The finite difference and the engine's own `backward`, compared exactly.

    `fn`, `x` and `h` are `finite_difference`'s, and the leaf `x` must be the
    one `fn` builds its graph from: the oracle clears the graph, runs stage 1's
    `backward` with the root's `ones` seed, and takes the leaf's `grad` as the
    analytic gradient. It then computes `finite_difference(fn, x, h)` and
    compares the two cell by cell, as exact `Rational` pairs — no tolerance, no
    float, no rounding — returning the gradient when they agree at every cell.
    At the first cell they disagree on it raises `exact.AutogradError` naming
    that cell's index, the shape, both exact numbers and their exact
    difference, which for the stage's cubic is the `h²` the central difference
    is off by.

    A grads' shapes are checked first: the leaf's gradient and the difference
    must both be the leaf's value's shape (§3 invariant 2) — a shape alone
    proves nothing, so the shapes are a guard and the cells are the test. The
    graph is cleared before the backward, so the answer does not depend on what
    a previous `backward` left behind, and a `fn`/`x`/`h` that the oracle
    refuses is refused here too, with the same message.
    """
    _point("gradient_check", x)
    step = _step("gradient_check", h)
    _function("gradient_check", fn)
    root = _graph("gradient_check", fn, x)
    _value("gradient_check", root)
    zero_grad(root, x)
    backward(root, exact.ones(root.value.shape))
    analytic = x.grad
    numeric = finite_difference(fn, x, step)
    if analytic.shape != x.value.shape or numeric.shape != x.value.shape:
        raise exact.AutogradError(
            "gradient_check: the gradients have shapes %r and %r, and the leaf "
            "has shape %r: %d, %d and %d cells"
            % (analytic.shape, numeric.shape, x.value.shape, analytic.size,
               numeric.size, x.value.size))
    for index, (got, want) in enumerate(zip(numeric.cells, analytic.cells)):
        if got != want:
            raise exact.AutogradError(
                "gradient_check: the finite difference and backward disagree at "
                "index %d of shape %r: %s and %s, off by %s, and there is no "
                "tolerance in this course"
                % (index, x.value.shape, _pair(got), _pair(want),
                   _pair(got - want)))
    return numeric
