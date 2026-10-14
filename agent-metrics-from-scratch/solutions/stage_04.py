"""Agent Metrics From Scratch — stage 4: The percentile is an index.

A percentile is not a measurement; it is an **index** into a sorted copy of the
window's samples. With floats banned there is nothing to interpolate with and
nothing to round, so the whole of the arithmetic is `ceil(n * num / den) - 1`,
computed on ints, and the answer is always a sample somebody actually recorded.
For a window of eight samples that makes `p95` the maximum — the one result that
surprises anyone who expects an interpolation, and the property this stage is
written to make obvious.

`quantile` sorts a *copy*, so the caller's tuple is never reordered under them;
`summary` reports the window's six numbers in one frozen order; and `above` asks
the same sorted-filter question with a rate on top, floored to basis points like
every rate in this course.
"""

from collections.abc import Sequence

import stage_01

#: The six keys of a window's summary, in the order they are reported.
SUMMARY_KEYS = ("count", "min", "max", "p50", "p95", "p99")


class QuantileError(stage_01.TelemetryError):
    """A quantile this stage refuses: a fraction that is not one, a sample that
    is not an int, or a window with no samples in it at all."""


def quantile(values, numerator, denominator):
    """The `numerator/denominator` quantile of `values`, as one sample.

    Nearest-rank: sort a copy, then take the sample at `ceil(n * num / den) - 1`,
    clamped at zero. The answer is always one of the samples — never a number
    between two of them — because there is no float here to interpolate with.
    """
    ordered = _samples(values)
    if not ordered:
        raise QuantileError("a quantile of an empty sequence is a question with "
                            "no answer")
    _fraction(numerator, denominator)
    return ordered[_index(len(ordered), numerator, denominator)]


def summary(values):
    """The window's six numbers, over exactly `SUMMARY_KEYS`, in that order."""
    ordered = _samples(values)
    if not ordered:
        raise QuantileError("a summary of no samples has no minimum to report")
    return {"count": len(ordered), "min": ordered[0], "max": ordered[-1],
            "p50": quantile(ordered, 50, 100),
            "p95": quantile(ordered, 95, 100),
            "p99": quantile(ordered, 99, 100)}


def above(values, threshold):
    """How many samples are strictly above a threshold, and the rate in bp.

    Returns `{"count", "total", "bp"}`: the samples strictly greater than the
    threshold, the number of samples, and their share in floored basis points.
    A sequence with no samples has no rate — a zero denominator is refused.
    """
    ordered = _samples(values)
    _threshold(threshold)
    total = len(ordered)
    if total == 0:
        raise QuantileError("a rate above a threshold needs samples, and this "
                            "sequence has none")
    count = 0
    for value in ordered:
        if value > threshold:
            count += 1
    return {"count": count, "total": total, "bp": count * 10000 // total}


def _samples(values):
    """A sorted *copy* of a sequence of int samples, or a refusal."""
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise QuantileError("a sample set is a sequence of ints, got %r"
                            % (type(values).__name__,))
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise QuantileError("a %s sample is not an int measurement this "
                                "course can assert: %r"
                                % (type(value).__name__, value))
    return sorted(values)


def _fraction(numerator, denominator):
    """A quantile's fraction: two ints with `0 < numerator <= denominator`."""
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise QuantileError("a quantile's numerator must be an int, got %r"
                            % (numerator,))
    if isinstance(denominator, bool) or not isinstance(denominator, int):
        raise QuantileError("a quantile's denominator must be an int, got %r"
                            % (denominator,))
    if denominator <= 0:
        raise QuantileError("a quantile needs a denominator above zero, got %r"
                            % (denominator,))
    if numerator <= 0:
        raise QuantileError("a quantile needs a numerator above zero, got %r"
                            % (numerator,))
    if numerator > denominator:
        raise QuantileError("the numerator %r is above the denominator %r: a "
                            "quantile is a fraction of one"
                            % (numerator, denominator))


def _index(size, numerator, denominator):
    """`ceil(size * numerator / denominator) - 1`, by integer arithmetic only."""
    return max(0, (size * numerator + denominator - 1) // denominator - 1)


def _threshold(threshold):
    """A threshold is a measurement like any sample: an int, and not a bool."""
    if isinstance(threshold, bool) or not isinstance(threshold, int):
        raise QuantileError("a threshold is a measurement, so it must be an int, "
                            "got %s: %r" % (type(threshold).__name__, threshold))
