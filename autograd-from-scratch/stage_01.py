"""Autograd From Scratch — stage 1: The graph and the order

Below this stage is the provided world: `exact.py` — the exact `Rational`, the
`Tensor` it lives in, and the whole forward algebra, with no gradients — and
`fixtures.py`, the deterministic datasets and models the last stage must
reproduce. Neither remembers anything. This stage is the engine's core, the two
things every later stage stands on: the **graph** (`Node`) and the **order** a
backward walks it in.

A `Node` holds a value (an `exact.Tensor`), the parents it was built from, a
local backward closure, and its own `grad` — the zeros of the value's shape
until a backward visits it. `add` and `mul` build one such node from two: the
value is `exact`'s forward algebra (`exact.add`, `exact.mul`), so a stage's
forward is provably right before any gradient is examined, and the node's
closure is the local derivative that hands the incoming gradient on to the
operands. `backward(root, seed=None)` starts from `ones` (or from the given
seed), walks the graph in **reverse topological order** — children before
parents, so a node's gradient has fully arrived before it is handed on — and
calls each node's closure with its *accumulated* gradient. `zero_grad(*nodes)`
clears the whole graph above every node it is given.

Nothing here assigns a gradient: every contribution is added to what is
already there, so a node used twice gets the sum of its paths and a second
`backward` without `zero_grad` doubles every gradient. Nothing here touches a
float: a gradient is a `Tensor` of `Rational`s, compared with `==` as pairs,
and there is no tolerance to choose.

DESIGN DECISION — why does the backward walk an order instead of recursing from
the root?
    A recursion that expands a node's parents without remembering which nodes
    it has already expanded visits a shared node once per path out of the root
    — twice for a diamond, exponentially for a chain of diamonds — and it still
    returns the right answer on a tree, which is what lets the bug survive a
    first test. An explicit order visits every node exactly once, so a diamond
    costs what a tree costs, and the order is itself the statement that a node
    is handed on only after every contribution to it has arrived. The order is
    a DFS **post-order**, reversed: a post-order visits parents before
    children, and the backward needs children before parents.

DESIGN DECISION — why is a `Node` mutable when `exact.Tensor` is not?
    A value must not change under a graph: `exact.Tensor` is immutable, built
    once, and every operation makes a new one (so a plan cannot be edited in
    place and a stage's forward is the same tensor twice). A gradient must
    change, and that is the opposite requirement: a node used twice receives
    two contributions and the second has to reach what the first left, so
    `grad` lives on the node and is accumulated into. The container is
    provided complete — its fields, `__init__`, `__repr__` and `__eq__` by
    identity — because every later stage composes this one object and nothing
    about it is the exercise.

DESIGN DECISION — why does a call add the gradient it computed to the fields
instead of assigning it?
    Accumulation, never assignment, is the invariant (§3.3) that the second
    `backward` tests: a call without `zero_grad` must land on top of what the
    last one left, so a second call doubles every gradient — the seed at the
    root included. A call that *assigned* what it computed — `node.grad =
    this_call` — would return the first call's numbers for ever, which trains a
    model with gradients that never grow and looks perfectly healthy at a
    single step.

DESIGN DECISION — why does stage 1 refuse two operands of different shapes
instead of calling `exact.reduce_gradient`?
    `reduce_gradient` is the provided half of stage 3 and it is only right for
    an operand the broadcast stretched: applied to an equal-shape operand it is
    a no-op, and applied to the wrong operand it returns the wrong shape
    silently. This stage's graph has one shape per node, so it names both
    shapes and refuses — and stage 3 adds the reduction exactly where the
    broadcast is, for the broadcast operand only.

DESIGN DECISION — why is a node with parents and no local backward refused?
    A leaf has no parents and no closure: the walk stops there and its `grad`
    is the answer. A node with parents and no closure is a broken edge in the
    graph — the gradient can go no further, and the caller would silently get
    zeros above it — so the walk raises `exact.AutogradError` naming the node
    instead of reading a missing derivative as zero.

DESIGN DECISION — why does `backward` refuse a root with `requires_grad` set
to `False`?
    Asking for the gradient of a node that does not want one is exactly the
    detached-node refusal of §2, and it is cheaper to name it at the root than
    to hunt for the zeros it silently produced. The field is stored on every
    node here; stage 7 gives it its full meaning (a detach that returns a copy
    with no parents, and a `no_grad` that does not accumulate).

TODO: implement `add`, `mul`, `backward` and `zero_grad`.
"""

import exact


class Node:
    """One node of the graph: a value, the parents it was built from, the
    local backward that hands its gradient on, and the gradient itself.

    The container is **mutable**, which is the whole point: `exact.Tensor` is
    immutable because a value must not change under a graph, and `Node` is
    mutable because a gradient *accumulates* into it — the second contribution
    to a node used twice must reach the `grad` the first one left, not replace
    it. The fields are plain attributes (`value`, `parents`, `backward`,
    `requires_grad`, `grad`), `__eq__` is identity — two nodes with the same
    value are different nodes — and `__repr__` shows the value and the
    gradient, so a graph can be read at a prompt.

    `grad` starts as the zeros of the value's shape, so a node that a backward
    never reaches still holds the shape it owes its operand (§3 invariant 2)
    instead of having no gradient at all. `backward` is a closure that takes
    the node's *accumulated* gradient and accumulates into each parent's
    `grad`; a leaf carries `None`.
    """

    def __init__(self, value, parents=(), backward=None, requires_grad=True):
        if not isinstance(value, exact.Tensor):
            raise exact.AutogradError(
                "Node: value %r is not an exact.Tensor" % (value,))
        self.value = value
        self.parents = tuple(parents)
        self.backward = backward
        self.requires_grad = requires_grad
        self.grad = exact.zeros(value.shape)

    def __repr__(self):
        return "Node(value=%r, parents=%d, requires_grad=%r, grad=%r)" % (
            self.value, len(self.parents), self.requires_grad, self.grad)

    def __eq__(self, other):
        return self is other

    __hash__ = object.__hash__


def add(a, b):
    """`a + b`, elementwise: one node whose value is `exact.add`'s and whose
    local backward hands the incoming gradient to both operands unchanged.

    `a` and `b` are `Node`s of the same shape (this stage does not broadcast),
    each one's accumulated gradient grows by the whole of the node's gradient,
    and an operand that is not a `Node` — or a pair of shapes that differ — is
    refused, naming the offender and both numbers.
    """
    raise NotImplementedError("stage 1: implement add()")


def mul(a, b):
    """`a * b`, elementwise: one node whose value is `exact.mul`'s and whose
    local backward hands each operand the gradient times the *other* operand.

    `d(a * b)/da` is `b` and `d(a * b)/db` is `a`, so the pair of gradients is
    `(gradient * b.value, gradient * a.value)` — the product rule, with the
    two operands the wrong way round being a defect that only a fixture with
    two different values can see.
    """
    raise NotImplementedError("stage 1: implement mul()")


def backward(root, seed=None):
    """The gradient of `root`'s value with respect to everything above it.

    The seed is the `ones` of `root`'s shape — the VJP contract against which
    a non-scalar root is seeded in stage 6 — or the given seed, whose shape
    must be `root`'s, or `exact.AutogradError` names both.

    A call computes the gradient of *its own* seed and **adds** it to what the
    nodes' `grad` fields already hold, never assigning: the fields accumulate
    across calls, so a second `backward` without `zero_grad` doubles every
    gradient instead of returning the same numbers. The walk is the reverse of
    a DFS post-order over the root's ancestors: every node with a local
    backward is called exactly once, with the gradient accumulated so far —
    which is the whole of it, because every node that contributes to it comes
    later in the walk. Returns nothing: the result is in the `grad` fields.
    """
    raise NotImplementedError("stage 1: implement backward()")


def zero_grad(*nodes):
    """Clear the gradient of every node reachable from each of `nodes` by
    walking the parents — the whole graph above a loss, or above a parameter.

    Zeroing is idempotent, so a node reachable from two of the arguments is
    cleared once and a node in an unrelated graph is left alone. A `grad` is
    set back to `exact.zeros(node.value.shape)`, which is the shape it must
    keep (§3 invariant 2) and the value it started with, so the next
    `backward` accumulates from zero and not from the last step's numbers.
    Returns nothing.
    """
    raise NotImplementedError("stage 1: implement zero_grad()")
