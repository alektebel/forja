"""Agent Metrics From Scratch — stage 2: The window, and the fold.

A metric is not a measurement; it is a *fold over a window*, and the window is
the decision. This stage writes the window down — the half-open interval
`[start, end)` over ticks — and the three folds every later stage is built from:
how many events there are, what a field adds up to, and what a field averages to.
Nothing here is clever, and that is the point: an event at `tick == start` is in
and an event at `tick == end` is out, once and everywhere, so two windows that
overlap agree on the overlap and a tumbling set of windows is a *partition*.

    WindowError  a window this stage refuses, or a fold with no sample to fold
    window       the events in `[start, end)`, in the order they came
    count        how many events, or how many of them carry a field
    total        the sum of an int field over the events that carry it
    mean         the sum over the carriers as an exact reduced pair

DESIGN DECISION — why is the interval half-open, `[start, end)`, instead of
closed at both ends?
    Because a dashboard is a series of windows, and the only series that adds up
    is the one where the boundary belongs to exactly one window. If `end` were
    in, an event that finished at tick 20 would be counted in the window that
    ends at 20 *and* in the window that starts at 20, and the minute's total
    would be the sum of its windows plus every event on a boundary. Half-open
    makes the windows [0,20) [20,40) [40,60) a partition: every event in the
    interval belongs to exactly one of them, and summing any two of them can
    never double count. The rule is written down once here and read everywhere
    above, so a fold and a fixture cannot disagree about a boundary.

DESIGN DECISION — why is a window with no width refused, when it would just
answer with an empty tuple?
    Because `end <= start` is not an empty window, it is a caller who has not
    decided what they are asking. "A point has no fold": a window of one tick is
    a perfectly good request (it is how a gauge's value at an instant is
    computed), but a window of *zero* ticks is a question with no interval in
    it, and answering `()` would hide the arithmetic that produced it. So the
    boundary is validated: `end <= start` is refused, a bound that is not a
    non-negative int is refused naming which bound it was, and a one-tick window
    is accepted like any other.

DESIGN DECISION — why does a fold refuse an unmeasured field, instead of
answering zero?
    Because an unmeasured field and a field whose value is zero are different
    facts and a metric that confuses them is a metric nobody can act on. An
    event whose kind does not carry `tokens_out` spells it `-`, and that `-`
    means "this field was not measured for this event" — the event did not
    spend zero tokens, it did not spend anything, because it never finished.
    `total` sums only the events that carry the field and refuses when *none*
    does ("no event here carries tokens_out"); `mean` refuses the same way ("a
    mean of no samples is not zero"). This refusal is the whole course in one
    line: an absence is not a measurement of zero.

DESIGN DECISION — why is a mean an exact reduced pair instead of a number?
    Because a ratio that is not exact is a ratio that was rounded before anyone
    decided where to round it, and this course refuses to decide that for the
    reader. `mean` answers `(numerator, denominator)`, reduced by the greatest
    common divisor so there is one spelling of every value — `(4, 6)` is not an
    answer because `(2, 3)` is — and a caller that wants a scalar floors it into
    basis points at the edge, on purpose. No float appears anywhere: `1 / 2` is
    a float in Python 3, and a float that reaches a total is a number that no
    longer adds up to a whole.

DESIGN DECISION — why does a fold never sort the events it is given?
    Because the order of the events is a fact the fold was handed and not one it
    gets to invent. Two events at the same tick happen in a fixed order
    (`admitted`, `started`, `finished`, `retried`, `dropped`), and a fold that
    sorted by tick alone would reshuffle exactly those ties — which is the one
    place the order carries information. So `window` filters and keeps the
    original order (`count` counts what it is given, `total` and `mean` add what
    they are given), and a caller who wants a sorted window sorts it themselves,
    where the choice is visible.

TODO: implement `window`, `count`, `total` and `mean`.
"""

import stage_01
import telemetry

#: The twelve fields of an event, in the order a line writes them. A refusal
#: that names a field nobody has uses this closed vocabulary to suggest the one
#: it probably meant.
_FIELDS = telemetry.EVENT_KEYS

#: What a field nobody measured is spelled. `-` is a silence, not a zero, and
#: the difference is the whole reason `total` and `mean` refuse an empty set.
_ABSENT = stage_01.ABSENT


class WindowError(stage_01.TelemetryError):
    """A window this stage refuses, or a fold with no sample to fold.

    The refusal names the offender — the bound that is not a tick, the field
    that no event carries — and, when the field is within edit distance two of
    an event field, the name it probably meant.
    """


def window(events, start, end):
    """The events whose tick is in `[start, end)`, in the order they came.

    `start` and `end` are non-negative int ticks; anything else is refused
    naming which bound it was. A window with no width (`end <= start`) is
    refused — a point has no fold — while a one-tick window is an ordinary
    window. The events keep their original order: a fold never sorts.
    """
    raise NotImplementedError("stage 2: implement window()")


def count(events, field=None):
    """How many events, or how many of them carry `field`.

    With no field, every event counts. With a field, only the events that
    measured it count: a field spelled `-` is not carried, so an event whose
    kind does not carry the field is not one of the carriers. This is the one
    fold that answers zero when nothing was measured, because "how many" has an
    honest answer of none.
    """
    raise NotImplementedError("stage 2: implement count()")


def total(events, field):
    """The sum of an int field over the events that carry it.

    Refuses when no event carries the field ("no event here carries
    tokens_out"): an unmeasured field is not a field whose value is zero. A
    carrier whose value is not an int is refused by name, so no float sneaks
    into a total.
    """
    raise NotImplementedError("stage 2: implement total()")


def mean(events, field):
    """The mean of an int field over the carriers, as an exact reduced pair.

    The numerator is the same sum `total` returns and the denominator is the
    number of carriers, reduced by their greatest common divisor. Refuses when
    nothing carries the field — "a mean of no samples is not zero" — and never
    divides before it is asked to: the pair is the answer, not a float.
    """
    raise NotImplementedError("stage 2: implement mean()")
