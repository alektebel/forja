"""Autograd From Scratch — stage 7: Detach, and the graph that must not grow (implementation)

The reasoning behind the model lives in the template's docstring
(`stage_07.py`); this file is only the body. Two functions, and the whole of
this stage is the seam they cut:

* `detach(node)` returns a **new** node that carries the same `exact.Tensor` and
  owns no history: no parents, no local backward, `requires_grad=False` and its
  own zeros `grad` of the value's shape. The value is immutable, so carrying the
  same tensor is not sharing state — and the new node is a distinct object, so a
  backward that names it stops there and never reaches what was detached.
* `no_grad(fn, *args, **kwargs)` is the region. The engine's operations are
  frozen stage-1 code that attaches a node to every operand unconditionally, so
  the seam is at the **arguments**: every `Node` argument is handed to `fn` as
  its detached copy, and the argument itself is frozen (`requires_grad=False`)
  for the duration, so the engine refuses it as a root — a node with no gradient
  input cannot be seeded. Nothing the call builds from the arguments it was
  handed is attached to a node that existed before it, and no node that existed
  before the call accumulates. The flag is also the region's state, which the
  `finally` puts back.

`fn`'s return value comes back untouched and `fn`'s exception comes back
untouched; the frozen flags are put back in a `finally`, in reverse of the order
they were taken, so a region that raised leaves exactly the state it found. No
module-level register is involved: the region's state is the arguments' own
`requires_grad`, which is why a leaked region would freeze the next call's
parameters and why the restore has to be exact.

Nothing here touches a float: a detached node's value is the same
`exact.Tensor`, and the only field this stage writes is a boolean flag, which it
puts back where it found it.
"""

import exact
from stage_01 import Node


def detach(node):
    """`node`'s value as a **new** node with no parents, no local backward and
    no gradient input — a leaf that carries the value and owns no history.

    The copy is not the node it was given (`__eq__` is identity, so
    `detach(x) == x` is False and a walk cannot confuse the two) and it is not
    an alias of it either: a backward that reaches the copy stops there, because
    the copy has no `parents` to hand a gradient to and no local backward to run
    — the upstream that was detached from keeps exactly the gradient it had, not
    zero and not double. `requires_grad=False` is the same refusal stage 1 gives
    at the root: this node does not want a gradient, so `backward` refuses it
    rather than seeding it.

    An argument that is not a `Node` is refused, naming it: a detach of a tensor
    would be a value pretending to be a node, and the first operation to use it
    would fail somewhere else.
    """
    if not isinstance(node, Node):
        raise exact.AutogradError("detach: %r is not a Node" % (node,))
    return Node(node.value, parents=(), backward=None, requires_grad=False)


def no_grad(fn, *args, **kwargs):
    """Run `fn(*detached, **kwargs)` inside the no-grad region and return
    whatever it returned, byte for byte.

    For the duration of the call, every `Node` argument is handed to `fn` as its
    detached copy — a frozen leaf — and the argument itself is frozen too, with
    its previous `requires_grad` remembered. So an operation inside the call
    starts from a leaf that owns no history: the node it builds cannot be
    attached to the caller's graph, a backward through it writes the copy and
    never the frozen node, and `backward` refuses a frozen node outright. Every
    other argument is passed through as it is, unchanged.

    The state is restored in a `finally` and in reverse of the order it was
    taken: a call that raises (or that was handed the same node twice) leaves
    every node's `requires_grad` exactly as it found it, so the region cannot
    leak into the next call. The exception itself is not caught anywhere here:
    it is the caller's, and a region that swallowed it would turn a failure into
    a silent `None`. The return value is not wrapped either — an inference pass
    under `no_grad` returns the values it computed, not copies of them.

    A `fn` that is not callable is refused, naming it: a region over something
    that cannot be called is a mistake at the call site, and it is cheaper to
    name it here than to read the `TypeError` that comes out of the engine.
    """
    if not callable(fn):
        raise exact.AutogradError("no_grad: fn %r is not callable" % (fn,))
    frozen = []
    try:
        handed = []
        for arg in args:
            if isinstance(arg, Node):
                frozen.append((arg, arg.requires_grad))
                arg.requires_grad = False
                handed.append(detach(arg))
            else:
                handed.append(arg)
        return fn(*handed, **kwargs)
    finally:
        for node, wanted in reversed(frozen):
            node.requires_grad = wanted
