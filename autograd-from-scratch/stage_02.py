"""Autograd From Scratch — stage 2: The local derivatives

Stage 1 gave the engine its graph (`stage_01.Node`) and the order a backward
walks it in (`stage_01.backward`), and with `add` and `mul` it gave it two
operations. This stage gives it the four that are still missing — `sub`, `div`,
`pow` and `neg` — and, with them, the thing every later stage composes: the
**local derivative**. A node is not just a value with parents; it carries the
closed form of its own derivative, a closure that takes the node's accumulated
gradient and hands each parent that gradient *times* the operation's local
derivative — `1` and `-1` for a difference, `1/b` and `-a/b**2` for a quotient,
`n·a**(n-1)` for a power, `-1` for a negation.

The value is never re-derived. Every forward below is `exact`'s own algebra —
`exact.sub`, `exact.div`, `exact.pow`, `exact.neg` — so a stage's output is
provably the provided forward, element for element, before a single gradient is
examined. What is yours is the closed form and the discipline around it: the
gradient accumulates into the parent's `grad` and is never assigned there, and
a gradient keeps the shape of *its own* operand and never the output's.

This stage is also where the engine's refusals get specific, and each of them
is a build-time refusal:

    * two operands of different shapes — stage 3 owns the broadcast, and a
      stage that quietly let `exact` broadcast would hand the stretched operand
      the output's shape;
    * a divisor with a zero in it — refused naming both operands, the output
      index and the shape, so no node ever exists whose quotient is undefined;
    * an exponent that is negative or not an int — naming it.

Nothing here touches a float and nothing here chooses a tolerance: every
derivative is a `Rational` pair and every comparison is `==` on pairs.

DESIGN DECISION — why is the local derivative a closed form registered on the
node, instead of a numerical or a symbolic one?
    A numerical derivative needs a step, and a step is a tolerance in disguise:
    the answer becomes "close to" the analytic one and the whole course loses
    the property that makes it worth writing. A symbolic expression would have
    to be built, kept and re-evaluated for every node and every call, when the
    derivative of each of these four operations is one line of arithmetic on
    the values the node already holds. The closed form is also the only one of
    the three that can carry something the value cannot: `pow`'s exponent `n`.
    `a**n` does not tell you what `n` was — `2**2` and `4**1` are the same
    value and have different derivatives — so the closure captures `n` at build
    time and the local derivative is written once, exactly.

DESIGN DECISION — why is a zero divisor refused when the node is built instead
of when the backward divides by it?
    Because the backward's second term is `-g·a/b**2` and a zero `b` is a
    division by zero there too — but by then the value exists, the graph
    exists, and the refusal arrives in the middle of a walk with half the
    gradients already accumulated. Refusing at build time names the operands
    while the caller still holds them. And it is the same fact as the forward:
    `3 / 0` has no value, so a node claiming one is a lie about the arithmetic
    that no later stage can repair. `exact.div` already refuses it, naming both
    operands, the output index and the shape — this stage must call it and must
    not paper over it.

DESIGN DECISION — why is `div` its own operation, when `a * pow(b, -1)` is
shorter to write?
    They are not the same function. `exact.pow` refuses a negative exponent —
    that refusal is the contract of stage 2's `pow` — so `a * pow(b, -1)` does
    not divide at all: it raises. The tempting repair is to hand-roll the
    reciprocal, and the tempting repair of *that* is to divide the ints with
    `//`, which answers `1` for `3/2`, `0` for `1/3` and silently turns an exact
    course into an integer one. The quotient rule is two divisions and a square,
    and writing it directly is what keeps `1/3` a `Rational`.

DESIGN DECISION — why does the local backward of `pow` special-case `n == 0`?
    The closed form is `n·a**(n-1)`, and at `n == 0` it wants `a**(-1)`, which
    `exact.pow` refuses (a negative exponent) — so the general formula cannot be
    evaluated at zero exponent at all. The mathematics is unambiguous: `a**0`
    is one everywhere, so its derivative is zero everywhere, and the `n·a**(n-1)`
    form is a removable singularity, not a case with an answer. The zeros of the
    *operand's* shape are that zero, and the operand's shape is the shape the
    gradient owes it.

DESIGN DECISION — why does every contribution keep the operand's shape, and
why does this stage refuse a shape mismatch instead of broadcasting it?
    A gradient's shape is its operand's shape (§3 invariant 2), never the
    output's and never the broadcast's: the caller accumulates into
    `parent.grad`, and a `(3,)` parent handed a `(2, 3)` contribution would
    either crash on the addition or — worse, if the addition broadcast — grow a
    gradient that no longer means what the operand means. In this stage every
    operand has one shape, so the two shapes coincide and the rule is invisible;
    it stops being invisible the moment stage 3 adds a `(4,)` to a `(3, 4)`,
    which is why the discipline is stated and enforced here, at the boundary
    where a mismatched pair is refused naming both shapes.

TODO: implement `sub`, `div`, `pow` and `neg`.
"""

import exact
import stage_01


def sub(a, b):
    """`a - b`, elementwise: one node whose value is `exact.sub`'s and whose
    local backward hands the gradient to `a` and its negation to `b`.

    `d(a - b)/da` is `1` and `d(a - b)/db` is `-1`, so the pair of
    contributions is `(gradient, -gradient)` — the sign is the whole content of
    the operation, and it is lost the moment the subtrahend is handed
    `+gradient`. `a` and `b` are `stage_01.Node`s of the same shape; a
    mismatched pair is refused naming both shapes, and an operand that is not a
    node is refused naming it.
    """
    raise NotImplementedError("stage 2: implement sub()")


def div(a, b):
    """`a / b`, elementwise: one node whose value is `exact.div`'s and whose
    local backward is the quotient rule.

    `d(a / b)/da` is `1 / b` and `d(a / b)/db` is `-a / b**2`, each multiplied
    by the incoming gradient — the second one is where the sign and the square
    both live, and a rule written as `-a / b` (or as `+a / b**2`) is right only
    where the quotient is right-handed anyway. A zero divisor is refused naming
    both operands, the output index and the shape, so no node exists whose
    quotient is undefined; `a * pow(b, -1)` is *not* this function.
    """
    raise NotImplementedError("stage 2: implement div()")


def pow(a, n):
    """`a ** n`, elementwise, for a non-negative int `n`: one node whose value
    is `exact.pow`'s and whose local backward is `n * a**(n - 1)`.

    The exponent is the operand the value cannot recover, so the closure
    captures `n`: `d(a**n)/da` applied with `a**n` in the place of `a**(n - 1)`
    is a different number for every `n` other than one. `n == 0` is the zeros
    of the operand's shape — `a**0` is one everywhere and its derivative is
    zero — because the general form would ask `exact.pow` for `a**(-1)`. A
    negative or non-int exponent is refused naming it.
    """
    raise NotImplementedError("stage 2: implement pow()")


def neg(a):
    """`-a`, elementwise: one node whose value is `exact.neg`'s and whose local
    backward hands the parent the negated gradient.

    `d(-a)/da` is `-1`, so the parent's contribution is `-gradient`. The node
    is *built*, not mutated into its operand: a `neg` that negated `a.value` in
    place and returned `a` would have no parent to accumulate into, and every
    other node that reads the operand would read a value the fixture never
    wrote.
    """
    raise NotImplementedError("stage 2: implement neg()")
