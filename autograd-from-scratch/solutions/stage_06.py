"""Autograd From Scratch — stage 6: The seed of a non-scalar output (implementation)

Stage 1's `backward(root, seed=None)` already took the seed and already
defaulted it to `ones`; the default was honest for every graph the earlier
stages build, because every one of them ends in a **scalar** — a loss, a sum,
the one number a training step differentiates. This stage is the other case: a
`root` whose value has more than one cell. There the seed is not a default, it
is the **vector the VJP contracts against**, `sum_i seed_i * d(root_i)/dx`, and
`ones` is one choice among many made silently.

So this file is small on purpose. `backward(root, seed=None)` decides the one
thing stage 1 could not know: a root with exactly one cell keeps the default —
the `ones` of the root's *own shape*, whatever that shape is — and a root with a
non-scalar value is refused unless the caller supplies the seed, with
`exact.AutogradError` naming the shape and what is missing. Everything else the
seed needs (it is an `exact.Tensor`, its shape is the root's exactly, a seed
that would broadcast is not a seed) is stage 1's check, reached through stage 1's
walk: `backward` here is the same walk, called with the seed this stage argued
for. `sum_to_scalar(t)` is the other half — the explicit way to make a
non-scalar output a scalar, a node the caller writes into the graph, whose
`()` value is `exact.sum`'s and whose local backward hands the scalar gradient
back to every cell it came from.

Nothing here does arithmetic on a value and nothing here chooses a tolerance:
the forward is `exact`'s, the walk is stage 1's, and every gradient that comes
out is an exact `Rational` pair.

DESIGN DECISION — why does a non-scalar root refuse a `backward` with no seed
instead of defaulting the seed to `ones`?
    Because `ones` is not the identity of a VJP; it is a *choice*, and for a
    non-scalar output it is a wrong one. `backward` on a `(2,)` root seeded
    `ones` returns `(dr0/dx, dr1/dx)` summed — the gradient of `r0 + r1` —
    while a caller who wanted the derivative of the second output alone has no
    way to see that the two were added. The call *runs*: the shapes all match,
    a training loop built on it goes down, and the numbers are the derivative
    of a different function. A scalar root has no such freedom (the VJP of a
    scalar is the gradient), so `ones` is the whole answer there; a non-scalar
    root has to say which vector it is contracting against, and the refusal
    names the shape it has no seed for instead of guessing.

DESIGN DECISION — why is "scalar" `size == 1` here, and not `shape == ()`?
    What makes the default legitimate is that there is only one cell to
    differentiate: `size == 1`. The shape question is answered by the seed,
    which must be the root's shape exactly, so a `(1,)` or a `(1, 1)` root is
    seeded `ones` of *that* shape and the one number in it is differentiated
    once — refusing those shapes would refuse graphs that are scalar in every
    way that matters (a reshape parts a `(2,)` into a `(1, 2)`, and the single
    operand of a parted axis is a natural `(1,)`). What this stage must not do
    is seed the `ones` of `()` for a `(1, 1)` root, or seed `ones` for a
    `(2,)` root because its cells happen to be few.

DESIGN DECISION — why must the seed be exactly the root's shape, and not
something that broadcasts into it?
    The seed is compared to the root, not merged with it: this is the one place
    in the engine where `exact.broadcast_shape` must *not* be consulted. A
    `(3,)` seed for a `(2, 3)` root has the right number of columns and the
    wrong number of rows, so accepting it would contract the same three numbers
    against both rows and hand back the gradient of a function nobody wrote; a
    `(2, 4)` seed for a `(2, 3)` root would have to be trimmed, and trimming is
    silently dropping a coordinate. Accepting a seed because its cell count
    fits, or because it broadcasts, is the engine choosing an interpretation;
    refusing it names both shapes and lets the caller write the seed the caller
    meant.

DESIGN DECISION — why does this stage run stage 1's `backward` instead of
carrying a walk of its own?
    Because the walk is stage 1's and there is exactly one of it. A second
    implementation of "reverse topological order, seed at the root, accumulate
    into the parents, never assign" is a second place for the order, the
    accumulation and the scratch to be got right: it agrees with stage 1 on the
    graphs somebody tries it on and drifts on the diamond, on the second call
    without `zero_grad`, or on the node reached by two paths. The seed is the
    *argument* stage 1's `backward` already takes; this stage supplies it, and
    the walk that consumes it is the tested one, so the two stages cannot
    disagree about a graph.

DESIGN DECISION — why is `sum_to_scalar` a node the caller builds, and not
something `backward` does when it finds a non-scalar root?
    Because summing is a *graph decision*, and the graph is the caller's. If
    `backward` collapsed a non-scalar root to a scalar for the caller, every
    non-scalar output would silently acquire a sum node the caller never asked
    for: the graph would not show the node the decision rests on, the gradient
    would be the gradient of the sum, and a caller who wanted a weighted
    contraction (a seed) could no longer ask for one. `sum_to_scalar` puts the
    node *in* the graph instead — a `Node` whose `()` value is `exact.sum`'s and
    whose local backward broadcasts the scalar gradient back to every cell it
    came from — so the caller who wants a scalar writes it and the caller who
    wants a contraction passes a seed.
"""

import exact
import stage_01
from stage_01 import Node


def _default_seed(root):
    """The seed of a root that has one cell: the `ones` of the root's shape.

    One cell is the whole reason `ones` may be assumed, so this is also the
    refusal: a root with more than one cell is named together with its shape
    and the seed that is missing, because the silent alternative — seeding
    `ones` and returning the gradient of the root's sum — is a wrong answer
    that runs.
    """
    if root.value.size != 1:
        raise exact.AutogradError(
            "backward: root has shape %r and %d cells, and no seed was given: "
            "a non-scalar output is contracted with an explicit seed of the "
            "root's shape, and this stage will not invent ones for it"
            % (root.value.shape, root.value.size))
    return exact.ones(root.value.shape)


def backward(root, seed=None):
    """The gradient of `root`'s value under the seed the root is contracted
    against, computed by stage 1's walk.

    A scalar root — one cell, whatever its shape — keeps stage 1's default, the
    `ones` of the root's own shape; a non-scalar root with no seed is refused,
    naming the shape and the missing seed. A given seed travels to stage 1's
    `backward` unchanged, which is what enforces the rest of the contract: it
    must be an `exact.Tensor`, its shape must be the root's exactly (a seed
    that would broadcast into it, or whose cells only happen to be as many, is
    refused with both shapes named), and it is the vector the VJP contracts
    against, not a value merged into the root. Returns nothing: the gradients
    are in the `grad` fields, accumulated exactly as stage 1 leaves them, so a
    second call without `zero_grad` still doubles every one of them.
    """
    if not isinstance(root, Node):
        raise exact.AutogradError("backward: root %r is not a Node" % (root,))
    if seed is None:
        seed = _default_seed(root)
    return stage_01.backward(root, seed=seed)


def sum_to_scalar(t):
    """`t`'s value summed into one cell: the explicit scalar the engine will
    not make for you.

    The value is `exact.sum`'s — a rank-0 tensor of shape `()`, element for
    element — and `t` is the node's one parent, so the node sits in the graph
    like any other and `t`'s gradient accumulates this path with every other
    one. The local backward is the derivative of a sum: the incoming scalar
    gradient goes to every cell of `t`, so it hands `t` the `exact.full` of
    `t`'s shape at that scalar. `backward` on this node needs no seed (its
    value has one cell), and `t`'s gradient is whole again: a `(2, 3)` operand
    is owed a `(2, 3)` gradient, not the `(3,)` a single axis would leave.
    An argument that is not a `Node` is refused, naming it.
    """
    if not isinstance(t, Node):
        raise exact.AutogradError("sum_to_scalar: %r is not a Node" % (t,))
    value = exact.sum(t.value)

    def backward_of_sum(gradient):
        t.grad = exact.add(t.grad, exact.full(t.value.shape, gradient.cells[0]))

    return Node(value, parents=(t,), backward=backward_of_sum)
