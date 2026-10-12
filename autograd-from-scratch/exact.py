"""exact.py — the provided exact arithmetic of H2: the rational, the tensor it
lives in, the shape calculus, and the whole forward algebra.

This module is the *world* the course's autodiff engine is measured against.
Every value is an exact `Rational` — a `(numerator, denominator)` pair of ints
reduced by `gcd` with a **positive denominator** and the sign on the numerator
— so two independent computations of the same quantity are `==`, as pairs,
with no tolerance anywhere. There are no floats in this file: not as a value,
not as a literal, not as a type annotation. Every division is `//` on ints or
an exact `Rational`.

Nothing here is random and nothing here is stateful: two calls return `==`
values, and the module holds constants and functions only. There is no
registry to grow and no cache to warm.

What the engine must reproduce
------------------------------
The forward algebra below (`add`, `sub`, `mul`, `div`, `pow`, `neg`, `matmul`,
`transpose`, `reshape`, `sum`, `mean`, `max`, `abs`, `relu`, `zeros`, `ones`,
`full`) is *provided*, so a stage's forward output is provably right before
any gradient is examined; the stages write the graph and the backward. The
one piece of the backward that is provided is `reduce_gradient`, the shape
calculus that sums a broadcast gradient back to the shape it is owed to.

The two errors
--------------
`ExactError` is raised by this module — a malformed shape, a bad broadcast, a
`reshape` that does not preserve the size, an arithmetic refusal (a zero
divisor, a negative exponent) — and by every shape refusal of the engine.
`AutogradError` is the *graph* refusal the stages raise: a backward through a
detached node, a seed of the wrong shape, a node with no local backward. Both
name the offender and both numbers. Both are `ValueError`s.

The shape convention (frozen here, called by stage 3)
-----------------------------------------------------
Shapes are right-aligned, `1` stretches, anything else refuses. So `(3, 4)`
and `(4,)` broadcast to `(3, 4)`; `(3, 4)` and `(5,)` do not: the message
names both shapes, both offending numbers and the axis.

A gradient owes its *operand* its shape, never the output's. The engine's rule
is one line: for a broadcast operand `p` of a node with output gradient `g`,

    d p = reduce_gradient(g, p.shape)

which sums `g` over exactly the axes where the broadcast stretched `p` — the
leading axes the operand does not have, and every axis where `p` has extent
`1`. `reduce_gradient` refuses a gradient that could not have come from that
shape (a `(4,)` gradient for an operand of shape `(3, 4)` is refused: the sum
cannot recover the three rows). `sum(t, axis)` and `mean(t, axis)` reduce one
axis of a *forward* value; `reduce_gradient` reduces every stretched axis of a
*gradient*. They are not the same function, and stage 3 is graded on calling
the right one, at the right moment, for the right operand only.
"""

from math import gcd


class ExactError(ValueError):
    """An exact arithmetic or shape refusal, naming the offender and both
    numbers: a zero divisor, a negative exponent, two shapes that do not
    broadcast, an axis outside a shape, a `reshape` that changes the size."""


class AutogradError(ValueError):
    """A graph refusal, naming the offender: a backward through a detached
    node, a seed of the wrong shape, a node with no local backward. The engine
    raises this; this module never does."""


# ---------------------------------------------------------------------------
# The house guards: an int is an int, a shape is a shape, a tensor a tensor
# ---------------------------------------------------------------------------

def _iabs(n):
    """`abs(n)` without touching the builtin `abs` this module shadows."""
    return n if n >= 0 else -n


def _prod(dims):
    """The number of cells of `dims`: `1` for the empty shape (a scalar)."""
    total = 1
    for dim in dims:
        total *= dim
    return total


def _require_int(value, what, *, minimum=None):
    """The house guard: a `bool` is not an int, and neither is a string.

    `minimum` is inclusive when given; a value below it is refused with the
    offending field's name interpolated.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExactError("%s=%r is not an int" % (what, value))
    if minimum is not None and value < minimum:
        raise ExactError("%s=%d is below %d" % (what, value, minimum))
    return value


def _require_shape(shape, what="shape"):
    """A tuple of non-negative ints, or the refusal naming `what` and the
    offending axis."""
    if not isinstance(shape, tuple):
        raise ExactError("%s=%r is not a tuple of ints" % (what, shape))
    for axis, dim in enumerate(shape):
        if isinstance(dim, bool) or not isinstance(dim, int):
            raise ExactError(
                "%s=%r has a non-int %r at axis %d" % (what, shape, dim, axis))
        if dim < 0:
            raise ExactError(
                "%s=%r has a negative extent %d at axis %d"
                % (what, shape, dim, axis))
    return shape


def _require_tensor(value, what):
    """A `Tensor`, or the refusal naming `what`."""
    if not isinstance(value, Tensor):
        raise ExactError("%s=%r is not a Tensor" % (what, value))
    return value


def _coerce(value):
    """`value` as a `Rational`, or `None` when it is not one.

    An int (never a bool) is promoted to `Rational(value, 1)`; anything else
    returns `None`, which makes the caller return `NotImplemented` rather than
    raise, so `Rational(1, 2) == "x"` is `False` and not a crash.
    """
    if isinstance(value, Rational):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Rational(value)
    return None


# ---------------------------------------------------------------------------
# Rational — the only rational in the course
# ---------------------------------------------------------------------------

class Rational:
    """An exact rational, normalized on construction and immutable.

    `Rational(2, 4)`, `Rational(-3, -6)` and `Rational(1, 2)` are the same
    pair `(1, 2)`: the denominator is positive, the sign is on the numerator,
    and `gcd` removed the common factor (with `gcd(0, n) == n`, so `0/5` is
    `0/1` and `Rational(0)` is an integer). `==` compares those two ints, so
    every operation below is checked as a *pair* — `r.numerator`,
    `r.denominator` — and never as a float.

    Arithmetic is closed: `+`, `-`, `*`, `/` and `** int` of `Rational`s are
    `Rational`s. So is comparison against a `Rational` or an int. `/` by zero
    is refused, naming both operands. `** int` is exact for a negative
    exponent too (`Rational(2, 3) ** -1 == Rational(3, 2)`), and refuses a
    non-int exponent and zero to a negative power.

    The attributes are read-only properties: there is no setter, so an
    instance cannot be renormalized out of its pair.
    """

    __slots__ = ("_numerator", "_denominator")

    def __init__(self, numerator, denominator=1):
        _require_int(numerator, "numerator")
        _require_int(denominator, "denominator")
        if denominator == 0:
            raise ExactError(
                "Rational(%r, 0): the denominator is zero" % (numerator,))
        if denominator < 0:
            numerator, denominator = -numerator, -denominator
        common = gcd(_iabs(numerator), denominator)
        if common > 1:
            numerator //= common
            denominator //= common
        self._numerator = numerator
        self._denominator = denominator

    @property
    def numerator(self):
        """The signed numerator of the reduced pair."""
        return self._numerator

    @property
    def denominator(self):
        """The positive denominator of the reduced pair."""
        return self._denominator

    def is_integer(self):
        """`True` when the reduced denominator is `1`."""
        return self._denominator == 1

    def __add__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return Rational(
            self._numerator * other._denominator
            + other._numerator * self._denominator,
            self._denominator * other._denominator)

    __radd__ = __add__

    def __sub__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return Rational(
            self._numerator * other._denominator
            - other._numerator * self._denominator,
            self._denominator * other._denominator)

    def __rsub__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return other.__sub__(self)

    def __mul__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return Rational(self._numerator * other._numerator,
                        self._denominator * other._denominator)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        if other._numerator == 0:
            raise ExactError(
                "Rational(%d, %d) / %r: the divisor is zero"
                % (self._numerator, self._denominator, other))
        return Rational(self._numerator * other._denominator,
                        self._denominator * other._numerator)

    def __rtruediv__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        if self._numerator == 0:
            raise ExactError(
                "%r / Rational(%d, %d): the divisor is zero"
                % (other, self._numerator, self._denominator))
        return Rational(other._numerator * self._denominator,
                        other._denominator * self._numerator)

    def __pow__(self, exponent):
        _require_int(exponent, "exponent")
        if exponent == 0:
            return Rational(1)
        if exponent > 0:
            return Rational(self._numerator ** exponent,
                            self._denominator ** exponent)
        if self._numerator == 0:
            raise ExactError(
                "Rational(0, 1) ** %d: zero to a negative power" % (exponent,))
        return Rational(self._denominator ** -exponent,
                        self._numerator ** -exponent)

    def __neg__(self):
        return Rational(-self._numerator, self._denominator)

    def __abs__(self):
        return Rational(_iabs(self._numerator), self._denominator)

    def __eq__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return (self._numerator == other._numerator
                and self._denominator == other._denominator)

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    def __lt__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return (self._numerator * other._denominator
                < other._numerator * self._denominator)

    def __le__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return (self._numerator * other._denominator
                <= other._numerator * self._denominator)

    def __gt__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return (self._numerator * other._denominator
                > other._numerator * self._denominator)

    def __ge__(self, other):
        other = _coerce(other)
        if other is None:
            return NotImplemented
        return (self._numerator * other._denominator
                >= other._numerator * self._denominator)

    def __bool__(self):
        return self._numerator != 0

    def __hash__(self):
        return hash((self._numerator, self._denominator))

    def __repr__(self):
        return "Rational(%d, %d)" % (self._numerator, self._denominator)


# ---------------------------------------------------------------------------
# The row-major index calculus the Tensor and every shape function share
# ---------------------------------------------------------------------------

def _strides(shape):
    """The row-major strides of `shape`: the step one index of each axis is
    worth in the flat cell tuple."""
    out = [0] * len(shape)
    step = 1
    for axis in range(len(shape) - 1, -1, -1):
        out[axis] = step
        step *= shape[axis]
    return tuple(out)


def _flat(offsets, strides):
    """The flat cell index of a multi-index, given the shape's strides."""
    index = 0
    for axis, offset in enumerate(offsets):
        index += offset * strides[axis]
    return index


def _indices(shape):
    """Every multi-index of `shape`, in row-major order, one at a time."""
    if _prod(shape) == 0:
        return
    offsets = [0] * len(shape)
    while True:
        yield tuple(offsets)
        for axis in range(len(shape) - 1, -1, -1):
            offsets[axis] += 1
            if offsets[axis] < shape[axis]:
                break
            offsets[axis] = 0
        else:
            return


# ---------------------------------------------------------------------------
# Tensor — a row-major cell tuple plus the shape it is read in
# ---------------------------------------------------------------------------

class Tensor:
    """One tensor: a tuple of `Rational`s in row-major order plus its shape.

    `Tensor(cells, shape)` is immutable: `cells` and `shape` are read-only
    properties and `__slots__` admits no new attribute, so a value, once
    built, cannot be edited in place — an engine that wants a new value builds
    a new `Tensor`. An int cell is promoted to `Rational(cell, 1)` on
    construction, which is why the fixtures' integer weights are written as
    ints, and `cells` is always a tuple of `Rational`s afterwards.

    `__eq__` is by value: two tensors are equal when their shapes and every
    cell are equal as pairs. `to_nested()` and `from_nested()` are the
    hand-checkable round trip, and `like(other)` is the fresh-buffer idiom.
    """

    __slots__ = ("_cells", "_shape")

    def __init__(self, cells, shape):
        shape = _require_shape(shape, "shape")
        if not isinstance(cells, tuple):
            raise ExactError("cells=%r is not a tuple" % (cells,))
        out = []
        for index, cell in enumerate(cells):
            if isinstance(cell, Rational):
                out.append(cell)
            elif isinstance(cell, int) and not isinstance(cell, bool):
                out.append(Rational(cell))
            else:
                raise ExactError(
                    "cells=%r has a non-Rational %r at index %d"
                    % (cells, cell, index))
        size = _prod(shape)
        if len(out) != size:
            raise ExactError(
                "cells=%d do not fill shape=%r (%d cells)"
                % (len(out), shape, size))
        self._cells = tuple(out)
        self._shape = shape

    @property
    def cells(self):
        """The row-major cells: a tuple of `Rational`s."""
        return self._cells

    @property
    def shape(self):
        """The shape the cells are read in."""
        return self._shape

    @property
    def ndim(self):
        """The rank: `len(shape)`, `0` for a scalar tensor."""
        return len(self._shape)

    @property
    def size(self):
        """The number of cells: `prod(shape)`, `1` for a scalar tensor."""
        return _prod(self._shape)

    def get(self, index):
        """The cell at a multi-index: a tuple of one offset per axis, or a
        bare int for a rank-1 tensor. Every offset is checked, naming the
        shape and the axis; a negative offset is refused, not wrapped."""
        if isinstance(index, bool):
            raise ExactError("index=%r is not an int" % (index,))
        if isinstance(index, int):
            if self.ndim != 1:
                raise ExactError(
                    "get: index=%d is an int but shape=%r is not rank 1"
                    % (index, self._shape))
            offsets = (index,)
        elif isinstance(index, tuple):
            if len(index) != self.ndim:
                raise ExactError(
                    "get: index=%r has %d axes but shape=%r has %d"
                    % (index, len(index), self._shape, self.ndim))
            offsets = index
        else:
            raise ExactError("get: index=%r is neither an int nor a tuple"
                             % (index,))
        for axis, offset in enumerate(offsets):
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise ExactError(
                    "get: index=%r has a non-int offset %r at axis %d"
                    % (index, offset, axis))
            if offset < 0 or offset >= self._shape[axis]:
                raise ExactError(
                    "get: index=%r is out of range for shape=%r at axis %d "
                    "(%d is not in [0, %d))"
                    % (index, self._shape, axis, offset, self._shape[axis]))
        return self._cells[_flat(offsets, _strides(self._shape))]

    def to_nested(self):
        """The cells as nested tuples, one level per axis: a rank-2 `(2, 2)`
        becomes `((r, r), (r, r))`, and a rank-0 tensor returns its cell."""
        if self.ndim == 0:
            return self._cells[0]
        shape = self._shape

        def build(axis, offset):
            if axis == self.ndim - 1:
                return tuple(self._cells[offset:offset + shape[axis]])
            step = _prod(shape[axis + 1:])
            return tuple(build(axis + 1, offset + i * step)
                         for i in range(shape[axis]))

        return build(0, 0)

    @staticmethod
    def from_nested(nested):
        """`from_nested(nested)` — the module function, offered on the class.

        Nested tuples (or numbers) with an inferred shape; a ragged nesting or
        an empty tuple is refused, naming the offending position and both
        shapes.
        """
        return from_nested(nested)

    def same_shape(self, other):
        """`True` when `other` (a `Tensor` or a shape) is shaped like this."""
        shape = other.shape if isinstance(other, Tensor) else other
        return self._shape == _require_shape(shape, "other")

    def like(self, other):
        """A fresh zero tensor shaped like `other` (a `Tensor` or a shape).

        The buffer idiom: `grad = exact.zeros(param.shape)` is
        `grad = param.like(param.shape)`, and `param.like(loss)` is the zeros
        of the shape `loss` has — never of `self`'s own shape, which is what
        makes it useful when the two differ (a scalar and its operand).
        """
        shape = other.shape if isinstance(other, Tensor) else other
        shape = _require_shape(shape, "other")
        return Tensor((Rational(0),) * _prod(shape), shape)

    def __eq__(self, other):
        if not isinstance(other, Tensor):
            return NotImplemented
        return self._shape == other._shape and self._cells == other._cells

    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal

    def __hash__(self):
        return hash((self._shape, self._cells))

    def __repr__(self):
        cells = self._cells
        if len(cells) <= 8:
            body = ", ".join(repr(cell) for cell in cells)
        else:
            body = ", ".join(repr(cell) for cell in cells[:4])
            body += ", ... %d more" % (len(cells) - 4)
        return "Tensor(shape=%r, cells=(%s))" % (self._shape, body)


def from_nested(nested):
    """The `Tensor` a nested tuple describes, with the shape inferred.

    A number is a scalar cell (`from_nested(Rational(1, 2))` is the rank-0
    tensor of shape `()`); a tuple is one axis, and every item of a tuple must
    have the same nested shape, or the refusal names the position and the two
    shapes it disagrees with.
    """
    cells = []

    def walk(value, where):
        if isinstance(value, Rational) or (isinstance(value, int)
                                           and not isinstance(value, bool)):
            cells.append(value if isinstance(value, Rational)
                         else Rational(value))
            return ()
        if not isinstance(value, tuple):
            raise ExactError(
                "from_nested: %s=%r is neither a tuple nor a number"
                % (where, value))
        if not value:
            raise ExactError(
                "from_nested: %s=%r is empty, so its axis has no extent"
                % (where, value))
        head = walk(value[0], "%s[0]" % where)
        for position, item in enumerate(value[1:], 1):
            sub = walk(item, "%s[%d]" % (where, position))
            if sub != head:
                raise ExactError(
                    "from_nested: %s is ragged at its outer axis: %s[0] has "
                    "shape %r and %s[%d] has shape %r"
                    % (where, where, head, where, position, sub))
        return (len(value),) + head

    shape = walk(nested, "nested")
    return Tensor(tuple(cells), shape)


# ---------------------------------------------------------------------------
# The shape algebra: right-aligned, `1` stretches, nothing else
# ---------------------------------------------------------------------------

def shape_of(tensor):
    """The shape of a `Tensor` (a shape tuple is returned as it is)."""
    if isinstance(tensor, Tensor):
        return tensor.shape
    return _require_shape(tensor, "tensor")


def _broadcast_shapes(a, b, op):
    """The broadcast shape of two shapes, or the refusal naming `op`, both
    shapes, both offending numbers and the axis (counted from the right, as in
    `axis=-1` for the last one)."""
    a = _require_shape(a, "a")
    b = _require_shape(b, "b")
    rank = len(a) if len(a) > len(b) else len(b)
    left = (1,) * (rank - len(a)) + a
    right = (1,) * (rank - len(b)) + b
    out = []
    for axis in range(rank):
        x, y = left[axis], right[axis]
        if x == y:
            out.append(x)
        elif x == 1:
            out.append(y)
        elif y == 1:
            out.append(x)
        else:
            raise ExactError(
                "%s: %r and %r do not broadcast: %d and %d at axis %d"
                % (op, a, b, x, y, axis - rank))
    return tuple(out)


def broadcast_shape(a, b):
    """The shape two shapes broadcast to, right-aligned; `1` stretches."""
    return _broadcast_shapes(a, b, "broadcast_shape")


def broadcast_to(tensor, shape):
    """`tensor` read in `shape`, with every stretched axis repeating its one
    cell.

    `shape` must be `tensor`'s shape right-aligned with leading axes added and
    every stretched extent `1`; anything else is refused, naming both shapes,
    both offending numbers and the axis.
    """
    tensor = _require_tensor(tensor, "tensor")
    shape = _require_shape(shape, "shape")
    if len(shape) < tensor.ndim:
        raise ExactError(
            "broadcast_to: shape=%r is rank %d, below %r of rank %d"
            % (shape, len(shape), tensor.shape, tensor.ndim))
    pad = (1,) * (len(shape) - tensor.ndim) + tensor.shape
    for axis, (src, dst) in enumerate(zip(pad, shape)):
        if src != dst and src != 1:
            raise ExactError(
                "broadcast_to: %r cannot become %r: %d and %d at axis %d"
                % (tensor.shape, shape, src, dst, axis - len(shape)))
    strides = _strides(tensor.shape)
    offset = len(shape) - tensor.ndim
    out = []
    for offsets in _indices(shape):
        index = 0
        for axis in range(tensor.ndim):
            if tensor.shape[axis] != 1:
                index += offsets[offset + axis] * strides[axis]
        out.append(tensor.cells[index])
    return Tensor(tuple(out), shape)


def reduce_gradient(gradient, shape):
    """`gradient` summed back to the shape it is owed to — the provided half
    of the hard part of stage 3.

    `shape` is the *operand's* shape; `gradient` (the node's output gradient)
    must be exactly `shape` broadcast, i.e. right-aligned with leading axes
    added and every stretched extent `1`. The result sums `gradient` over
    every axis the broadcast stretched: the leading axes `shape` does not
    have, and every axis where `shape` has extent `1`.

        reduce_gradient((3, 4) gradient, (4,))            -> (4,)
        reduce_gradient((2, 3, 4) gradient, (3, 1))       -> (3, 1)
        reduce_gradient((3, 4) gradient, (3, 4))          -> (3, 4)

    A gradient that could not have come from that shape is refused, naming
    both shapes, both offending numbers and the axis — a `(4,)` gradient for
    an operand of `(3, 4)` cannot recover the three rows the `(3, 4)` added,
    so the caller has the wrong operand, not a rounding error. The engine
    calls this for a *broadcast* operand only: for an equal-shape operand the
    gradient is already the answer, and summing it would be wrong.
    """
    gradient = _require_tensor(gradient, "gradient")
    shape = _require_shape(shape, "shape")
    if gradient.ndim < len(shape):
        raise ExactError(
            "reduce_gradient: gradient shape=%r has %d axes, fewer than "
            "shape=%r with %d" % (gradient.shape, gradient.ndim, shape,
                                  len(shape)))
    lead = gradient.ndim - len(shape)
    pad = (1,) * lead + shape
    for axis, (src, dst) in enumerate(zip(pad, gradient.shape)):
        if src != dst and src != 1:
            raise ExactError(
                "reduce_gradient: shape=%r cannot sum back from gradient "
                "shape=%r: %d and %d at axis %d"
                % (shape, gradient.shape, src, dst, axis - gradient.ndim))
    if gradient.shape == shape:
        return gradient
    strides = _strides(shape)
    total = [Rational(0)] * _prod(shape)
    for offsets in _indices(gradient.shape):
        index = 0
        for axis in range(lead, gradient.ndim):
            if pad[axis] != 1:
                index += offsets[axis] * strides[axis - lead]
        total[index] = total[index] + gradient.cells[
            _flat(offsets, _strides(gradient.shape))]
    return Tensor(tuple(total), shape)


# ---------------------------------------------------------------------------
# The forward algebra, elementwise: exact, no gradients
# ---------------------------------------------------------------------------

def _elementwise(op, a, b, combine):
    """`combine(left, right, index)` over the broadcast of two tensors: the
    one place broadcasting is applied by every elementwise operation."""
    a = _require_tensor(a, "a")
    b = _require_tensor(b, "b")
    shape = _broadcast_shapes(a.shape, b.shape, op)
    left = broadcast_to(a, shape)
    right = broadcast_to(b, shape)
    out = []
    for index in range(len(left.cells)):
        out.append(combine(left.cells[index], right.cells[index], index))
    return Tensor(tuple(out), shape)


def add(a, b):
    """Elementwise sum of the broadcast of `a` and `b`."""
    return _elementwise("add", a, b, lambda x, y, index: x + y)


def sub(a, b):
    """Elementwise difference of the broadcast of `a` and `b`."""
    return _elementwise("sub", a, b, lambda x, y, index: x - y)


def mul(a, b):
    """Elementwise product of the broadcast of `a` and `b`."""
    return _elementwise("mul", a, b, lambda x, y, index: x * y)


def div(a, b):
    """Elementwise exact quotient of the broadcast of `a` and `b`.

    A zero in the divisor is refused, naming both operands, the output index
    and the output shape — never a silent `0` and never an integer `//`.
    """
    a = _require_tensor(a, "a")
    b = _require_tensor(b, "b")
    shape = _broadcast_shapes(a.shape, b.shape, "div")
    left = broadcast_to(a, shape)
    right = broadcast_to(b, shape)
    out = []
    for index, cell in enumerate(right.cells):
        if cell.numerator == 0:
            raise ExactError(
                "div: %r / %r divides by zero at output index %d of shape %r"
                % (a, b, index, shape))
        out.append(left.cells[index] / cell)
    return Tensor(tuple(out), shape)


def pow(t, n):
    """Elementwise `t ** n` for an int `n >= 0`: exact, and refusing a
    negative exponent (an engine that needs `t ** -1` wants `div`) naming it.
    """
    t = _require_tensor(t, "t")
    _require_int(n, "n")
    if n < 0:
        raise ExactError(
            "pow: n=%d is negative in %r ** n" % (n, t.shape))
    return Tensor(tuple(cell ** n for cell in t.cells), t.shape)


def neg(t):
    """Elementwise `-t`."""
    t = _require_tensor(t, "t")
    return Tensor(tuple(-cell for cell in t.cells), t.shape)


def max(a, b):
    """Elementwise `max` of the broadcast of `a` and `b`.

    On a tie the *left* operand is the value — indistinguishable in the
    value, decisive in the backward, where the contract's convention sends the
    gradient to the left operand (stage 8).
    """
    return _elementwise("max", a, b,
                        lambda x, y, index: x if x >= y else y)


def abs(t):
    """Elementwise absolute value, exact (`abs(-3/2) == 3/2`)."""
    t = _require_tensor(t, "t")
    return Tensor(tuple(cell.__abs__() for cell in t.cells), t.shape)


def relu(t):
    """Elementwise `relu(x) = x if x > 0 else 0`: the kink at `0` gives `0`,
    so `relu(Rational(0)) == Rational(0)` and `relu(-1) == 0` are one rule
    (stage 8's convention)."""
    t = _require_tensor(t, "t")
    zero = Rational(0)
    return Tensor(tuple(cell if cell > zero else zero for cell in t.cells),
                  t.shape)


def zeros(shape):
    """The all-zero tensor of `shape`."""
    shape = _require_shape(shape, "shape")
    return Tensor((Rational(0),) * _prod(shape), shape)


def ones(shape):
    """The all-one tensor of `shape` — the seed `backward` starts from."""
    shape = _require_shape(shape, "shape")
    return Tensor((Rational(1),) * _prod(shape), shape)


def full(shape, value):
    """The tensor of `shape` filled with `value` (an int or a `Rational`)."""
    shape = _require_shape(shape, "shape")
    if isinstance(value, Rational):
        cell = value
    elif isinstance(value, int) and not isinstance(value, bool):
        cell = Rational(value)
    else:
        raise ExactError("full: value=%r is neither an int nor a Rational"
                         % (value,))
    return Tensor((cell,) * _prod(shape), shape)


# ---------------------------------------------------------------------------
# The forward algebra, shaped: matmul, transpose, reshape, reductions
# ---------------------------------------------------------------------------

def matmul(a, b):
    """The rank-2 matrix product, exact.

    `a` is `(rows, inner)` and `b` is `(inner, cols)`; both must be rank 2 and
    the two inner extents must match, or the refusal names both shapes and
    both numbers and the two axes that disagree. Non-square operands are the
    point: `(4, 3) @ (3, 1)` is the fixture the engine's VJPs are graded on,
    and neither operand is its own transpose.
    """
    a = _require_tensor(a, "a")
    b = _require_tensor(b, "b")
    if a.ndim != 2 or b.ndim != 2:
        raise ExactError(
            "matmul: %r and %r are not both rank 2" % (a.shape, b.shape))
    rows, inner = a.shape
    inner2, cols = b.shape
    if inner != inner2:
        raise ExactError(
            "matmul: %r and %r do not contract: %d and %d at axis 1 of a and "
            "axis 0 of b" % (a.shape, b.shape, inner, inner2))
    out = []
    for row in range(rows):
        for col in range(cols):
            total = Rational(0)
            for step in range(inner):
                total = total + (a.cells[row * inner + step]
                                 * b.cells[step * cols + col])
            out.append(total)
    return Tensor(tuple(out), (rows, cols))


def transpose(t, axes=None):
    """`t` with its axes permuted; `axes=None` reverses them.

    `axes` must be a permutation of `range(t.ndim)`; anything else — the wrong
    length, a repeat, an axis outside the shape — is refused, naming both the
    axes and the shape.
    """
    t = _require_tensor(t, "t")
    rank = t.ndim
    if axes is None:
        axes = tuple(range(rank - 1, -1, -1))
    else:
        if not isinstance(axes, tuple) or len(axes) != rank:
            raise ExactError(
                "transpose: axes=%r is not a permutation of the %d axes of %r"
                % (axes, rank, t.shape))
        seen = set()
        for offset, axis in enumerate(axes):
            if isinstance(axis, bool) or not isinstance(axis, int):
                raise ExactError(
                    "transpose: axes=%r has a non-int %r at position %d of "
                    "%r" % (axes, axis, offset, t.shape))
            if axis < 0 or axis >= rank or axis in seen:
                raise ExactError(
                    "transpose: axes=%r does not permute the axes of %r: %d "
                    "at position %d" % (axes, t.shape, axis, offset))
            seen.add(axis)
    new_shape = tuple(t.shape[axis] for axis in axes)
    strides = _strides(t.shape)
    out = []
    for offsets in _indices(new_shape):
        source = [0] * rank
        for position, axis in enumerate(axes):
            source[axis] = offsets[position]
        out.append(t.cells[_flat(tuple(source), strides)])
    return Tensor(tuple(out), new_shape)


def reshape(t, shape):
    """`t`'s cells re-read in `shape`, row-major.

    Only the *size* must agree; a mismatch is refused, naming both shapes and
    both sizes over every axis. No cell is reordered and none is copied out of
    the tuple: a reshape is a view of the same row-major order.
    """
    t = _require_tensor(t, "t")
    shape = _require_shape(shape, "shape")
    if t.size != _prod(shape):
        raise ExactError(
            "reshape: %r has size %d and %r has size %d: they disagree over "
            "every axis" % (t.shape, t.size, shape, _prod(shape)))
    return Tensor(t.cells, shape)


def _axis_of(axis, shape, op):
    """A normalized in-range axis of `shape`, or the refusal naming both."""
    _require_int(axis, "axis")
    if len(shape) == 0 or axis < -len(shape) or axis >= len(shape):
        raise ExactError(
            "%s: axis=%d is outside the %d axes of shape=%r"
            % (op, axis, len(shape), shape))
    return axis % len(shape)


def sum(t, axis=None):
    """The sum of `t`, over one axis or over every axis.

    `axis=None` sums every cell and returns a rank-0 tensor of shape `()`;
    an int axis sums that axis away, so `sum((3, 4), axis=0)` is `(4,)`.
    An axis outside the shape is refused, naming the axis and the shape.
    """
    t = _require_tensor(t, "t")
    if axis is None:
        total = Rational(0)
        for cell in t.cells:
            total = total + cell
        return Tensor((total,), ())
    axis = _axis_of(axis, t.shape, "sum")
    keep = t.shape[:axis] + t.shape[axis + 1:]
    strides = _strides(keep)
    total = [Rational(0)] * _prod(keep)
    shape_strides = _strides(t.shape)
    for offsets in _indices(t.shape):
        index = 0
        position = 0
        for source in range(t.ndim):
            if source == axis:
                continue
            index += offsets[source] * strides[position]
            position += 1
        total[index] = total[index] + t.cells[
            _flat(offsets, shape_strides)]
    return Tensor(tuple(total), keep)


def mean(t, axis=None):
    """The exact mean of `t`: `sum(t, axis) / n`, with `n` the extent summed.

    `axis=None` averages every cell with `1 / size`; an int axis averages that
    axis with `1 / shape[axis]`. The reciprocal is an exact `Rational`, never
    a float and never `//`. An empty axis (extent `0`) is refused, naming the
    axis and the shape, because `1/0` has no meaning here.
    """
    t = _require_tensor(t, "t")
    if axis is None:
        if t.size == 0:
            raise ExactError(
                "mean: shape=%r is empty, so no axis has anything to average"
                % (t.shape,))
        return Tensor((sum(t).cells[0] / Rational(t.size),), ())
    axis = _axis_of(axis, t.shape, "mean")
    extent = t.shape[axis]
    if extent == 0:
        raise ExactError(
            "mean: axis=%d has extent 0 in shape=%r, nothing to average"
            % (axis, t.shape))
    reduced = sum(t, axis)
    scale = Rational(extent)
    return Tensor(tuple(cell / scale for cell in reduced.cells),
                  reduced.shape)
