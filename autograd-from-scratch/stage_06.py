"""Autograd From Scratch — stage 6: The seed of a non-scalar output

Stage 1 built the graph and the walk; every graph since then has ended in a
**scalar** — a loss, a sum, the one number a training step differentiates — and
for a scalar the seed `ones` is not an invention, it is the only seed that makes
`backward` return the gradient. This stage is about the other case: a `root`
whose value has more than one cell. There the seed is not a default, it is the
**vector the VJP contracts against** — `sum_i seed_i * d(root_i)/dx` — and
`ones` is one choice among many, made silently.

So `backward(root, seed=None)` keeps stage 1's walk and makes the choice
explicit: a root with exactly one cell (whatever its shape — `()`, `(1,)`,
`(1, 1)`) still starts from the `ones` of *its own shape*, and a root with a
non-scalar value is **refused** unless the caller supplies the seed, with
`exact.AutogradError` naming the root's shape and what is missing. A seed whose
shape is not the root's shape — even one that would broadcast, even one with the
same number of cells — is refused too, by the same walk that refuses it today.
What the engine will not do is invent the seed of a non-scalar output and call
the result a gradient: `sum_to_scalar(t)` is the *explicit* way to make a
non-scalar output a scalar, and it is the caller's decision, not the engine's.

Nothing here does arithmetic on a value: the forward is `exact`'s (`exact.sum`
for the one new node), the walk is stage 1's, and every number that comes out is
an exact `Rational` pair with no tolerance anywhere.

DESIGN DECISION — why does a non-scalar root refuse a `backward` with no seed
instead of defaulting the seed to `ones`?
    Because `ones` is not the identity of a VJP; it is a *choice*, and for a
    non-scalar output it is a wrong one. `backward((2,) root)` seeded `ones`
    returns `(dr0/dx, dr1/dx)` summed — the gradient of `r0 + r1` — while the
    caller who wanted, say, the derivative of the second output alone has no
    way to see that the two were added. The call *runs*: the shapes all match,
    a loss goes down, and the numbers are the derivative of a different
    function. A scalar root has no such freedom (the VJP of a scalar is the
    gradient), so `ones` is the whole answer there; a non-scalar root has to
    say which vector it is contracting against, and the refusal names the shape
    it is missing the seed for rather than guessing.

DESIGN DECISION — why is "scalar" `size == 1` here, and not `shape == ()`?
    The seed is a tensor whose shape must equal the root's shape, so the shape
    question is answered by the seed; what makes the *default* legitimate is
    that there is only one cell to differentiate, which is `size == 1`. A
    `(1,)` or a `(1, 1)` root holds one number and the `ones` of *its* shape is
    the `ones` of the one number: refusing those shapes would refuse graphs
    that are scalar in every way that matters (the parted operand of a reshape
    is a natural `(1,)`). What the stage must not do is seed `ones` of `()`
    for a `(1, 1)` root — the shapes would differ and the first comparison
    would say so — or seed `ones` for a `(2,)` root because its cells happen to
    be few.

DESIGN DECISION — why must the seed be exactly the root's shape, and not
something that broadcasts into it?
    The seed is compared to the root, not merged with it: this is the one place
    in the engine where `exact.broadcast_shape` must *not* be consulted. A
    `(3,)` seed for a `(2, 3)` root has the right number of columns and the
    wrong number of rows, so accepting it would contract the same three numbers
    against both rows and hand back a gradient that is the derivative of a
    function nobody wrote; a `(2, 4)` seed for a `(2, 3)` root would have to be
    trimmed, and the trimming is silently dropping a coordinate. Accepting a
    seed because its cell count fits, or because it broadcasts, is the engine
    choosing an interpretation; refusing it names both shapes and lets the
    caller reshape the seed, which is a decision the caller can state.

DESIGN DECISION — why does this stage run stage 1's `backward` instead of
carrying a walk of its own?
    Because the walk is stage 1's, and there is exactly one of it. A second
    implementation of "reverse topological order, seed at the root, accumulate
    into `parents`, never assign" is a second place for the order, the
    accumulation and the scratch to be got right; it agrees with stage 1 on the
    graphs someone tries it on and drifts on the diamond, the second call, or
    the node with two paths — and a course whose stages each carried a private
    walk would be ten engines, not one. The seed is the *argument* the walk
    already takes (`backward(root, seed=None)` in stage 1); this stage supplies
    it, and the walk it calls is the tested one.

DESIGN DECISION — why is `sum_to_scalar` a node the caller builds, and not
something `backward` does when it finds a non-scalar root?
    Because summing is a *graph decision*, and the graph is the caller's. If
    `backward` collapsed a non-scalar root to a scalar for the caller, every
    non-scalar output would silently acquire a sum node the caller never asked
    for: the gradient would be the gradient of the sum, the caller's graph
    would not show the node the decision rests on, and a stage that wanted a
    weighted contraction (a seed) could no longer ask for one. `sum_to_scalar`
    puts the node *in* the graph instead: a `Node` whose value is `exact.sum`'s
    `()` and whose local backward broadcasts the scalar gradient back to every
    cell it came from. The caller who wants a scalar writes it; the caller who
    wants a contraction of a non-scalar output passes a seed.

TODO: implement `backward` and `sum_to_scalar`.
"""

import exact
import stage_01
from stage_01 import Node


def backward(root, seed=None):
    """The gradient of `root`'s value with respect to everything above it,
    under the seed the root is contracted against.

    A scalar root — one whose value has exactly one cell, whatever its shape —
    keeps stage 1's default: the `ones` of the root's *own* shape. A
    non-scalar root with no seed is refused, with `exact.AutogradError` naming
    the root's shape and the missing seed: `ones` there would run and return
    the gradient of a different function. A given seed must be an
    `exact.Tensor` and its shape must be the root's exactly — a seed that
    would broadcast, or whose cells only happen to be as many, is refused with
    both shapes named. The walk itself is stage 1's `backward`, called with
    the seed: the seed is this stage's business, the order and the accumulation
    are not.
    """
    raise NotImplementedError("stage 6: implement backward()")


def sum_to_scalar(t):
    """`t`'s value summed to one cell: a node whose value is a `()` tensor and
    whose local backward broadcasts the scalar gradient back to `t`'s shape.

    This is how a non-scalar output becomes a scalar *explicitly*: the caller
    writes the node into the graph, so the gradient that comes back is the
    gradient of `sum(t)` — each cell of `t` owed the incoming scalar gradient —
    and a `backward` from the node needs no seed. The value is `exact.sum`'s,
    element for element, and the node's parent is `t` itself, so `t`'s gradient
    accumulates every path out of it exactly as it does anywhere else. An
    argument that is not a `Node` is refused, naming it.
    """
    raise NotImplementedError("stage 6: implement sum_to_scalar()")
