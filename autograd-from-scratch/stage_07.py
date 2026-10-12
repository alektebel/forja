"""Autograd From Scratch — stage 7: Detach, and the graph that must not grow

Stage 1 built the graph: a `Node` carries a value, the parents it was built
from, a local backward, and a `grad` that accumulates. Every stage since then
has been about making that graph *more* capable. This one is about the two ways
to stop it: a **detach** — the value without the history, a leaf that owns
nothing — and a **region**, `no_grad`, in which a call's operations build
nothing that is attached to the nodes the caller already holds.

`detach(node)` is not a view and not an alias. It returns a **new** `Node`
carrying the same `exact.Tensor` with no parents, no local backward and
`requires_grad=False`: a leaf. A backward that reaches it stops there, so the
node that was detached from keeps exactly the gradient it had — not zero, not
double — and a `mul(detach(w), x)` in the middle of a chain cuts the gradient
below the detach while the chain rule above it is untouched. The value is
immutable, so carrying the same tensor is not sharing state; the container is
not, so the copy is a distinct node and `__eq__` (identity) keeps it distinct.

`no_grad(fn, *args, **kwargs)` runs `fn` in a region. The engine's operations
are frozen stage-1 code and attach a node to every operand unconditionally, so
the region's seam is at the **arguments**: every `Node` argument is handed to
`fn` as its detached copy, and the argument itself is frozen for the duration,
with its previous `requires_grad` remembered. Nothing the call builds is
attached to a node that existed before it. `fn`'s return value comes back
untouched and `fn`'s exception comes back untouched, and the flags are put back
in a `finally` — a region that leaked its state would freeze the next call's
parameters.

Nothing here touches a float: a detached node's value *is* the same
`exact.Tensor`, and the only field this stage writes is a boolean flag it puts
back where it found it. A refusal is an `exact.AutogradError` naming the
offender.

DESIGN DECISION — why does a detach return a copy with no parents, instead of
the node itself or a copy that keeps them?
    A detach that returns the node it was given is not a detach at all: the next
    backward walks straight through it and the upstream node keeps growing. A
    copy that keeps the parents is worse, because it *looks* detached — the new
    node has its own `grad` — while the walk still reaches the graph above it
    through the `parents` tuple, and the derivative is handed back to a graph
    the caller believed was cut. The copy buys the cut with exactly three
    things: no parents (nothing to hand a gradient to), no local backward
    (nothing to run) and the same value (the forward is identical, element for
    element). `__eq__` is identity, so the copy is not the original — a walk
    cannot merge them, and a caller cannot accidentally gradient a node through
    the other one.

DESIGN DECISION — why does a detached node carry `requires_grad=False`?
    Because a detach is a statement about the future: this value takes no
    gradient. Stage 1's `backward` refuses a root whose `requires_grad` is
    False, exactly so that asking for the gradient of a node that does not want
    one is a refusal that names it, instead of the zeros it would silently
    produce. So the flag is not decoration: the detached leaf is the one node in
    the course whose gradient is refused rather than accumulated. It is also the
    flag the region writes, which is why the region's state and this field are
    the same field and why both must be restored exactly.

DESIGN DECISION — why is the region's seam at its arguments, rather than at the
operations?
    Because the operations are frozen: stage 1's `add` and `mul` are the given
    forward algebra's owners, they build a `Node` with their operands as parents
    on every call, and a stage may not re-declare them — this stage teaches a
    detach and a region, not a second engine. A mode the operations consulted
    would have to live in the operations, and the only alternative to that is a
    module-level register, which §1 forbids and which the next block rejects for
    a reason of its own. So the region controls the part it can see and restore
    exactly: what it hands the call. Every `Node` argument becomes its detached
    copy, so an operation inside the call starts from a leaf that owns no
    history, and the graph the call builds from those arguments cannot be
    attached to a node that existed before it — an inference pass under the
    region leaves nothing behind it that a later backward could reach. A closure
    that captured a parameter before the call is not the region's: an engine
    with no ambient register can only freeze and detach what it is handed, and a
    region that claimed to reach the rest would be claiming a mode it cannot
    restore.

DESIGN DECISION — why is the state the arguments' `requires_grad`, instead of a
module-level no-grad register?
    Because a register is ambient: it is shared between unrelated graphs, it
    survives a call that raises (there is nowhere to put it back to), and the
    first exception that escapes without a `finally` leaves the whole process in
    no-grad — the next training step silently builds no graph and the loss that
    never moves looks like a bad learning rate. The region's state here is
    exactly the flags it wrote, remembered per argument, and put back in a
    `finally`, in reverse of the order they were taken. Reverse matters: a node
    handed to the region twice is snapshotted twice, and putting the snapshots
    back forwards would leave it frozen — the restore has to undo the last write
    first. Nothing is remembered outside the call, so nothing can leak outside
    the call.

DESIGN DECISION — why is the return value passed through, and the exception let
out?
    Because a region is a statement about the graph, not about the caller's
    values or control flow. An inference pass under it hands back the values it
    computed — the tensor, or the node it built — and wrapping that return (a
    detached copy, say) would change what the caller holds and quietly hide the
    cut the region was supposed to make. And an exception belongs to the call:
    swallowing it turns a failure into a silent `None`, which is the one outcome
    a caller cannot detect. The `finally` restores the state whatever happened,
    so letting the error out costs nothing.

TODO: implement `detach` and `no_grad`.
"""

import exact
from stage_01 import Node


def detach(node):
    """`node`'s value as a **new** node with no parents, no local backward and
    no gradient input — a leaf that carries the value and owns no history.

    The copy is a distinct node (`__eq__` is identity, so a walk cannot confuse
    it with the original) and its own `grad` starts at the zeros of the value's
    shape. A backward that reaches it stops there: the node that was detached
    from keeps exactly its gradient — not zero, not double. An argument that is
    not a `Node` is refused, naming it.
    """
    raise NotImplementedError("stage 7: implement detach()")


def no_grad(fn, *args, **kwargs):
    """Run `fn` with the graph switched off at the seam: it is handed a detached
    leaf for every `Node` argument, and those arguments are frozen for the
    duration of the call.

    Every non-`Node` argument is passed through as it is. The state is restored
    in a `finally`, in reverse of the order it was taken, so a call that raises
    (or a node handed twice) leaves every `requires_grad` as it was found. The
    return value of `fn` is returned untouched and its exception is let out.
    A `fn` that is not callable is refused, naming it.
    """
    raise NotImplementedError("stage 7: implement no_grad()")
