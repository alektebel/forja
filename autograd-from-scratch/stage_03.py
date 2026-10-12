"""Autograd From Scratch — stage 3: Broadcasting and the reduction

Stages 1 and 2 built one node per shape: two operands of different shapes were
refused, and every local backward handed its contribution to an operand whose
shape it already was. This stage removes that restriction for the three
elementwise binary operations — `add`, `sub`, `mul` now take operands that
broadcast, `(3, 4)` against `(4,)`, `(3, 4)` against `(1, 4)`, `(3, 1)` against
`(4,)`, a tensor against a scalar — and it adds the two reductions, `sum(t,
axis)` and `mean(t, axis)`.

The forward is `exact`'s own algebra: `exact.add`, `exact.sub`, `exact.mul`,
`exact.sum` and `exact.mean` broadcast and reduce exactly as the node's value
must, so a stage is proved right element for element before any gradient is
examined. What the stage adds is the **backward of a broadcast**, and that is
where a subtle defect lives: the local derivative of an elementwise operation
is a factor per *element of the output*, so an operand the broadcast stretched
receives a gradient born in the output's shape and owes one in its own. The
provided `exact.reduce_gradient(contribution, operand.shape)` is the half of
the job that sums a gradient back over every axis the broadcast stretched; this
stage's job is to call it *at the right moment* and *for the right operand
only*. The symmetric half is the reduction's backward: a `sum` over an axis
removes that axis, so the gradient that comes back has it removed too and has
to be put back as an extent `1` and stretched — `sum`'s own broadcast, written
the other way round.

Two things must not be lost in the process. Nothing is assigned: every
contribution is added to the operand's `grad`, so a node used twice gets the
sum of its paths and a second `backward` without `zero_grad` doubles every
gradient (§3.3). And every gradient is a `Tensor` of `Rational`s of its own
operand's shape (§3.2), compared with `==` as pairs — there is no tolerance
anywhere in this course, and `mean`'s `1/n` is an exact `Rational`, never a
float and never `//`.

DESIGN DECISION — why is `exact.reduce_gradient` called for the broadcast
operand only?
    A local derivative is stated per element of the *output*: for `mul` the left
    operand's factor is the right operand read at that output element, and that
    factor is born in the output's shape whatever the left operand's shape is.
    For an operand the broadcast stretched, the output's shape is larger than
    the operand's and the contributions `[i, j]` of one operand cell are
    distinct gradient entries; the operand is owed their *sum*, which is
    `reduce_gradient`'s whole job. For an operand the broadcast did *not*
    stretch — the equal-shape case, and the common case — the contribution is
    already that operand's shape and reducing it is either a no-op or, worse, a
    sum over a shape it never had. Applied unconditionally the call is
    *invisible*: `reduce_gradient` returns its argument unchanged when the two
    shapes agree, so an engine that reduces everything passes every fixture
    whose operands have equal shapes, and it is wrong only where the broadcast
    happened — which is exactly where the fixture's bias is added, one stage
    later.

DESIGN DECISION — why does `sum`'s backward put the summed axis back and
stretch it, instead of reshaping the gradient straight to the operand's shape?
    `sum(t, axis)` maps a `(3, 4)` to a `(4,)`: one output cell is the sum of
    three of the operand's cells, so the derivative of each of those three
    w.r.t. the output cell is `1` and the operand's gradient is the output's
    gradient repeated along the summed axis. The output is the operand with
    that axis *removed*, and the operand's shape is not a `reshape` of the
    output's — the sizes differ — so the axis has to be put back as an extent
    `1` first (a rank-`n` shape becoming rank-`n+1`, which `reshape` accepts
    because the size is unchanged) and then stretched by `exact.broadcast_to`.
    `axis=None` is the same move at full rank: the reduction returns a scalar
    and the gradient is the scalar broadcast to every cell. A backward that
    reshaped the gradient into the operand's shape directly would refuse on the
    size — and one that stretched it along the wrong axis, or the last axis
    whatever the call said, is a plausible gradient of the wrong number of
    cells that only a seed with distinct values can tell from the right one.

DESIGN DECISION — why is the axis validated against the operand's shape, and
why is the normalized axis what the forward sees?
    An axis names one of the *operand's* axes; the reduction's own result is one
    rank shorter, so `sum(t, axis=1)` on a `(2, 3)` names an axis the result
    does not have and asking the result's shape would refuse a valid call.
    Normalizing the axis here, once — refusing a non-int, an axis below
    `-rank` and an axis at or above `rank` in the same breath — is also what
    keeps `axis=2` on a rank-2 tensor from being *accepted*: the `%` that wraps
    a negative axis wraps an out-of-range positive one onto a valid axis too
    (`2 % 2` is `0`), so the bounds check has to happen before the wrap and the
    wrapped value is what the forward and the backward are both given. A
    negative axis is the same axis as its positive twin (`-1` is the last one),
    and it must land on that axis in the value *and* in the expansion.

DESIGN DECISION — why does `mean`'s gradient carry the exact `1/n`?
    `mean(t, axis)` is `sum(t, axis) / n` with `n` the extent that was summed —
    `t.size` for `axis=None`, `shape[axis]` otherwise — so its backward is
    `sum`'s expansion scaled by exactly `1/n`. The scale is a `Rational(1, n)`,
    never a float and never `//`; `n` is the extent of *that* call, so an
    implementation that scales every reduction by the whole size is right on
    `axis=None`, right whenever the tensor is one axis, and wrong by a rational
    factor on every other call. Dropping the scale altogether — the backward of
    `mean` that is the backward of `sum` — is a factor of `n` wrong: it is
    invisible on a fixture whose seed is chosen so that the missing `n`
    cancels, and it is the defect the mean's own probes exist to name.

DESIGN DECISION — why does this stage import stage 1's `Node` instead of
declaring its own?
    The engine has one `Node`, one `backward`, one `zero_grad`: a second
    container in this file would produce graphs that stage 1's walk cannot
    enter, so `add`'s node here must be *the* node stage 1 knows, and its
    `grad` field is accumulated by the same walk. The forward is `exact`'s and
    the container is stage 1's; what is written here is the pair of things that
    make a broadcast differentiable — the reduction of the operand the
    broadcast stretched, and the expansion of the axis a reduction removed.

TODO: implement `add`, `sub`, `mul`, `sum` and `mean`.
"""

import exact
import stage_01


def add(a, b):
    """`a + b`, elementwise, over operands of broadcastable shapes: one node
    whose value is `exact.add`'s and whose local backward hands each operand
    the whole of the gradient — reduced back to that operand's own shape when
    the broadcast stretched it.

    `d(a + b)/da` is `1` and `d(a + b)/db` is `1`, so both contributions are the
    incoming gradient. `a` and `b` are `stage_01.Node`s; a pair of shapes that
    do not broadcast is refused by `exact.add` itself, naming the operation,
    both shapes, both numbers and the axis, and an operand that is not a `Node`
    is refused naming the offender.
    """
    raise NotImplementedError("stage 3: implement add()")


def sub(a, b):
    """`a - b`, elementwise, over operands of broadcastable shapes: one node
    whose value is `exact.sub`'s and whose local backward hands `a` the
    gradient and `b` its negation — each reduced back to its own shape when the
    broadcast stretched it.

    `d(a - b)/da` is `1` and `d(a - b)/db` is `-1`; the sign is lost the moment
    the subtrahend is handed `+gradient`, and a `(3, 4)` against a `(4,)` adds
    the second, shape-sensitive mistake: the negated contribution is born in
    the `(3, 4)` and the `(4,)` operand is owed its sum over the rows.
    """
    raise NotImplementedError("stage 3: implement sub()")


def mul(a, b):
    """`a * b`, elementwise, over operands of broadcastable shapes: one node
    whose value is `exact.mul`'s and whose local backward hands each operand
    the gradient times the *other* operand — reduced back to its own shape when
    the broadcast stretched it.

    `d(a * b)/da` is `b` and `d(a * b)/db` is `a`, each *read at the output's
    element*, so the contribution is born in the output's shape and an operand
    the broadcast stretched owes the sum of its cells over the stretched axes.
    Two operands the wrong way round, or a contribution that is not reduced,
    are both invisible on a fixture whose operands are equal in shape and value
    — which is the fixture this stage must not be tested with.
    """
    raise NotImplementedError("stage 3: implement mul()")


def sum(t, axis=None):
    """The sum of `t`, over one axis or over every axis: one node whose value is
    `exact.sum`'s and whose local backward puts the summed axis back as an
    extent `1` and stretches the gradient over the operand's shape.

    `axis=None` sums every cell and returns a rank-0 node, whose gradient is the
    seed broadcast to every cell. An int axis sums that axis away —
    `sum((3, 4), axis=0)` is `(4,)` — and its gradient is the seed with the axis
    re-inserted and stretched, so the operand's `grad` has the operand's shape
    and not the reduction's. A negative axis names the same axis as its
    positive twin. An axis the operand does not have, a non-int axis, and an
    operand that is not a `Node` are each refused, naming the offender.
    """
    raise NotImplementedError("stage 3: implement sum()")


def mean(t, axis=None):
    """The exact mean of `t`, over one axis or over every axis: one node whose
    value is `exact.mean`'s and whose local backward is `sum`'s expansion
    scaled by the exact `Rational(1, n)`.

    `n` is the extent that was summed — `t.size` for `axis=None`, the extent of
    that axis otherwise — so the gradient is the seed broadcast along the
    summed axis and divided by exactly `n`: never a float, never `//`, and
    never the whole size when only one axis was averaged. A mean over an empty
    axis is refused by `exact.mean`, naming the axis and the shape.
    """
    raise NotImplementedError("stage 3: implement mean()")
