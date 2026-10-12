"""Autograd From Scratch — stage 9: The oracle

Every stage so far has been judged by a check that already knew the answer.
This stage *is* that check: the engine's own gradients are compared with a
derivative the engine does not compute — the central difference
`(f(x + h) − f(x − h)) / 2h`, read off `exact`'s arithmetic alone, one
coordinate of `x` at a time, in exact rationals, against what `backward` leaves
on the leaf. `finite_difference(fn, x, h)` is that difference as a `Tensor` of
`x`'s value's shape — the shape a gradient has; `gradient_check(fn, x, h)` runs
both and refuses at the first cell they disagree on, naming that cell and both
exact numbers, because there is no tolerance anywhere in this course.

`fn` maps the leaf `Node` it is handed to another `Node` — a graph, not a bare
value, since the same `fn` is handed to `backward` — and that node's value must
be a scalar, the value whose gradient is a tensor of `x`'s shape. The step `h`
is an exact `Rational` (an `int` is converted, never divided with `//`) and it
is never zero: the step sets how much of a higher-order term leaks into the
answer, never what kind of number the answer is.

The fact this stage is built on: for a polynomial of degree at most two the
central difference is *exactly* the derivative, for every non-zero `h` — the
`h²` of each side cancels against the `2h` — while a cubic's central difference
is the derivative **plus exactly `h²`**, which is the amount `gradient_check`
must report when it refuses one.

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

TODO: implement `finite_difference` and `gradient_check`.
"""

import exact

from stage_01 import Node, backward, zero_grad


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
    raise NotImplementedError("stage 9: implement finite_difference()")


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
    raise NotImplementedError("stage 9: implement gradient_check()")
