"""Autograd From Scratch — stage 5: Accumulation and reuse

Stage 1 built the graph, the order a backward walks it in and the rule the walk
lives by: every contribution to a node is *added* to `node.grad`, never assigned
to it. This stage makes the two facts a graph of reused nodes rests on explicit.
First, **a node named by several positions is one parameter**: `x * x`, a weight
used in two layers and a diamond are all the same statement, and `shared`
already holds the node that makes it true — the very object, not a copy of it
and not two nodes that happen to hold the same tensor. Second, **a parameter
can be taken out of the graph and put back**: `trainable` freezes one — the
graph keeps its value and the backward cannot pass through it — and thaws it,
without either operation silently editing a gradient somebody else owns.

Neither function does arithmetic, and neither chooses a tolerance: `shared`
hands a node back as itself, `trainable` hands back the node the graph must use,
and every number a caller reads off the graph afterwards is the `Rational` that
was already there.

DESIGN DECISION — why does `shared` hand back the node it was given instead of
a copy of it?
    Reuse in this engine is the *identity* of a node: `backward` accumulates
    into `node.grad`, so a parameter named by two positions is one object
    reached by two paths and its gradient is the sum of both. A copy — even a
    copy with the very same value, even a copy built once and handed back twice
    — is a second node with its own `grad` field: the two positions stop
    meeting, the gradient of one never reaches the other, and the model trains
    two parameters where the caller asked for one. Nothing about that failure
    is visible in a forward pass (both copies read the same value) or in a
    shape (both owe the same shape), which is why this stage hands back the
    node itself.

DESIGN DECISION — why does `shared` refuse two distinct nodes instead of
taking the first one?
    `shared(x, y)` is the statement "these positions name one parameter"; when
    `x` and `y` are two objects it is a *false* statement, and both of the
    repairs are silent. Handing back `x` folds two parameters into one — the
    gradient of `y`'s paths is nowhere, and the caller's intention to keep them
    apart is lost. Handing back a copy replaces one parameter with two — the
    accumulation this stage is about never happens. The engine cannot rewrite a
    graph that was already built (the edges are the objects the caller is
    holding), so it names both nodes and refuses, and the fix belongs at the
    call site: build the graph from one node, or keep the two.

DESIGN DECISION — why is a frozen parameter a *different* node, and not the
same node with `requires_grad` set to `False`?
    Because the walk does not read the flag below the root: `backward` refuses
    a *root* that does not want a gradient, and then hands every other node's
    gradient on regardless. So a node whose flag is off, used inside a graph,
    would still pass its gradient to its parents — the freeze would leak — and
    would still have that gradient accumulated into its own `grad` field. What
    a freeze needs is a node the graph may *read* and the backward cannot pass
    *through*: the same value, no parents, no local backward. `trainable` builds
    exactly that and hands it back — the old graph is not attached to it, which
    is what "the backward cannot reach through it" means — while the parameter
    itself stays where it is, marked, with no gradient to apply.

DESIGN DECISION — why does the freeze clear the gradient while the thaw leaves
it alone?
    They are not symmetric because the mistakes they prevent are not. A freeze
    happens to a parameter that may have just been used: its `grad` holds the
    last step's contribution, and a step that ran after the freeze — or the
    first step after a later thaw, if the field survived — would apply a
    gradient the freeze declared irrelevant. So the freeze drops it. A thaw
    happens to a parameter whose gradient the caller owns: clearing it there
    would silently discard contributions gathered on purpose (an accumulated
    micro-batch, a hand-written seed), and "silently" is the one thing a
    refusal-free helper in this course may never be. A thawed parameter starts
    from the zero the freeze left, and the next `backward` accumulates into it.

DESIGN DECISION — why does the freeze touch no other node's gradient?
    Freezing is one parameter's business. `zero_grad` (stage 1) is the helper
    that clears a graph, and it clears exactly what is reachable from what it
    is given, through the parents; a `trainable` that cleared the subgraph
    above the node — the natural-looking "make a clean slate of the frozen
    part" — would reach parameters that are still training and wipe a gradient
    they had already gathered, so the freeze that is supposed to take one
    parameter out of the update would quietly move several.

DESIGN DECISION — why does `trainable` refuse a `requires_grad` that is not a
`bool`?
    `1`, `0`, `""` and `None` are all truthy or falsy, and a parameter that
    silently means "frozen" because someone passed `0` — or "trainable" because
    someone passed a non-empty string — is a training run whose numbers change
    for a reason the caller cannot see. The state has exactly two values, so
    the helper names the offender and the two things it may be, and the same
    refusal names a `node` that is not a `Node` in the first place.

TODO: implement `shared` and `trainable`.
"""

import exact
from stage_01 import Node


def shared(*operands):
    """The one node several positions share, handed back unchanged.

    `operands` is every place that names the same parameter. Each one must be
    a `Node`, there must be at least one of them, and they must all be *the*
    node — the same object, not two nodes with equal values — so the value
    handed back is that object and every path out of it accumulates into its
    one `grad` field. Nothing is written: sharing a parameter does not clear
    its gradient, does not thaw it and does not touch a neighbour, so the
    object that comes back compares `is` to the one that went in. A refusal
    names the offender and both numbers.
    """
    raise NotImplementedError("stage 5: implement shared()")


def trainable(node, *, requires_grad):
    """Freeze or thaw one parameter: the node the graph must use, and its state.

    `requires_grad=True` is the thaw: the parameter comes back itself, wanting
    a gradient, with whatever `grad` field it already has (a thaw is not a
    `zero_grad`). `requires_grad=False` is the freeze: the parameter is marked,
    its stale gradient is dropped — so no step can apply a contribution the
    freeze declared irrelevant — and the node handed back is a *stop*, the same
    value with no parents and no local backward, which is what keeps the old
    graph from being attached to the frozen use of it. Only the frozen node's
    own `grad` is cleared; every other node's is left exactly as it was, and a
    `requires_grad` that is not a `bool` is refused, naming it.
    """
    raise NotImplementedError("stage 5: implement trainable()")
