"""IRB and Regulatory Capital — stage 2: The normal quantile as tabulated data.

The IRB formula's one statistical animal is the inverse normal: a PD maps to a
point on a curve, the asset-class correlation weights it, and what comes out is
not a number a bank recomputes to the cent but a *tabulated* one. The policy in
`irb.py` refuses to let the course compute the curve — the tables **are** the
formula — so this stage reads the table with the discipline a table demands
and none of the arithmetic a formula would tempt.

A cumulative PD in basis points resolves to the exact row that carries it:
`slope`-style monotone data is not interpolable, because a PD between two rows
has no answer the policy stands behind and a stage that picked a side would
answer a number its reviewer cannot reproduce from the page. So the stage
answers only the rows the grid carries — including its own two endpoints, a PD
of nothing and a PD of the whole cycle, which the policy answers at its floor
and its ceiling — and refuses every other PD by name, naming the grid.

The grid itself is data with duties. This stage exposes it as its own answer:
the rows come back sorted, strictly increasing in PD with no duplicate, and
non-decreasing in the quantile, so a later stage that keys a band on the grid
is reading a table someone has already checked the shape of.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import irb
from irb import PolicyError

#: The name the refusals carry when they name the grid — the policy's own name.
GRID_NAME = irb.GRID_NAME

#: The two ends every PD lives between: a basis-point PD on `0..PD_MAX_BP`.
PD_MIN_BP = 0

PD_MAX_BP = 10000


class QuantileError(PolicyError):
    """The refusal this stage raises: something that cannot be a quantile.

    It names the offender — the PD that is not a whole count, the PD outside
    `PD_MIN_BP..PD_MAX_BP`, the PD that is not a row of the grid — and every
    refusal names the grid (`GRID_NAME`) too, because a refused PD must say
    which table it was asking and the grid is the table it belongs to.
    """


def _whole(value, what):
    """`value` as a whole number, or a refusal naming the field it arrived in."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuantileError("the %s %r is a %s, not a whole number"
                            % (what, value, type(value).__name__))
    return value


def grid():
    """The quantile grid as the policy carries it, with its shape proved, not claimed.

    The rows come back as `((pd_bp, quantile), ...)`, sorted by PD, with the PD
    column strictly increasing — no duplicated row — and the quantile column
    non-decreasing. A table that arrived otherwise would be refused, not
    tolerated: a grid whose own shape is broken must not be handed to a stage
    that keys bands on it, because the bands would be keyed on a lie.
    """
    rows = tuple((row[0], row[1]) for row in irb.QUANTILE_GRID)
    for step in range(1, len(rows)):
        if rows[step][0] <= rows[step - 1][0]:
            raise QuantileError("the %s carries the PD %d out of order after %d"
                                % (GRID_NAME, rows[step][0], rows[step - 1][0]))
        if rows[step][1] < rows[step - 1][1]:
            raise QuantileError("the %s descends from %d at PD %d to %d at PD %d"
                                % (GRID_NAME, rows[step - 1][1], rows[step - 1][0],
                                   rows[step][1], rows[step][0]))
    return rows


def quantile(pd_bp):
    """The exact quantile `pd-quantile-grid` carries for a PD, or a refusal naming it.

    `pd_bp` is a cumulative PD in basis points on `PD_MIN_BP..PD_MAX_BP`, and it
    must fall **on** a row of the grid: the search walks the rows, keeps the
    bracket, and answers the row it lands on — an off-grid PD is refused with
    the grid's own name in the message, never interpolated. The two endpoints
    the grid itself carries (a PD of nothing and a PD of `PD_MAX_BP`) are rows
    too, so they are answered at the policy's own floor and ceiling.
    """
    checked = _whole(pd_bp, "pd in basis points")
    if checked < PD_MIN_BP or checked > PD_MAX_BP:
        raise QuantileError("the %s answers PDs of %d..%d basis points, and %d is "
                            "outside them" % (GRID_NAME, PD_MIN_BP, PD_MAX_BP, checked))
    rows = grid()
    if checked < rows[0][0] or checked > rows[-1][0]:
        raise QuantileError("the %s begins at PD %d and ends at PD %d, and %d is "
                            "outside the open ends"
                            % (GRID_NAME, rows[0][0], rows[-1][0], checked))
    low = 0
    high = len(rows)
    while low < high:
        middle = (low + high) // 2
        if rows[middle][0] >= checked:
            high = middle
        else:
            low = middle + 1
    row = rows[low]
    if row[0] != checked:
        raise QuantileError("the %s carries no row for PD %d; it is refused rather "
                            "than read off the side of the step at PD %d"
                            % (GRID_NAME, checked, row[0]))
    return row[1]


if __name__ == "__main__":
    rows = grid()
    print("rows: %d, first %r, last %r" % (len(rows), rows[0], rows[-1]))
    print("pd  | quantile")
    for key in (0, 50, 500, 1000, 2500, 5000, 8000, 10000):
        print("%5d | %+d" % (key, quantile(key)))
    try:
        quantile(5200)
    except QuantileError as refused:
        print("off-grid: %s" % (refused,))
