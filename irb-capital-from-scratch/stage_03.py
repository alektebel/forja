"""IRB and Regulatory Capital — stage 3: The correlation and the maturity adjustment.

The policy's tables are read in the order the formula will use them: the asset
class a booking prices to, the asset correlation `R` for the grade's PD, the
maturity adjustment's slope, and the effective maturity the exposure has left
to run. None of this is computed — the correlation is a table row keyed on the
*quantile grid* itself, the slope is a row on the same bands, and the maturity
is whole years, clamped by the policy's own walls — and a stage that asks for a
value the tables do not carry is refused by name.

The grid of stage 2 becomes the banding here: the corporate rows are keyed on
grid PD entries, a PD resolving to the latest band whose start it has reached,
and the retail classes carry one constant row each. Keying the bands on the
quantile grid is the policy's own decision, so a PD that is not a row of the
grid has no band at all and the refusals here name the grid — a PD between two
rows is never read off the wrong side of a step.

The maturity adjustment carries the course's one deliberately-biting
truncation: `MF = 10000 + (2 * m - 5) * b // 2`. Every slope in the table is
odd **on purpose**: the half of an odd product never splits evenly, with an `m`
below two and a half the adjustment is negative and the quotient still falls
where Python's floor division puts it — down — and a slope chosen even to hide
the truncation would be a decoration, not a policy. The stage answers the
number the formula is pinned to, truncation and all.
TODO: implement `correlation`, `slope`, `remaining_years` and `maturity_factor`
in this file: the asset-class correlation the policy tables pin, the slope
those tables pin beside it, the remaining years a contract still has to run,
and the maturity factor their union scales the formula by."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import dates
import irb
from book import BookError
from irb import PolicyError

#: The asset classes the formula prices, in their own order.
CLASSES = irb.CLASSES

#: The clamps an effective maturity lives between, in whole years.
M_MIN = irb.M_MIN

M_MAX = irb.M_MAX

#: The name the off-grid refusals carry — banding is keyed on the quantile grid.
GRID_NAME = irb.GRID_NAME

#: The base the adjustment lifts from: a weight in ten-thousandths of itself.
MF_BASE = 10000


class WeightError(PolicyError):
    """The refusal this stage raises: something that cannot be a weight.

    It names the offender — the asset class outside `CLASSES`, the PD that is
    not a row of the grid, the effective maturity outside `M_MIN..M_MAX`, the
    loan the book does not hold or is not on, the date the book does not
    cover — because a weight the tables do not carry must say what it was asked
    for rather than answer one sampled from the wrong side of a band.
    """


def correlation(asset_class, pd_bp):
    """The correlation row `R`, in ten-thousandths, for `asset_class` at `pd_bp`.

    A retail class answers its constant row; `corporate` answers the band the
    PD has reached — the latest grid PD start the PD sits on or above. A class
    outside `CLASSES` or a PD not on the grid is refused by name.
    """
    raise NotImplementedError("stage 3: implement correlation()")


def slope(asset_class, pd_bp):
    """The maturity-adjustment slope `b`, in ten-thousandths, on the same bands.

    The rows carry the same grid banding the correlations do — one row per grid
    band for `corporate`, one constant row per retail class — and are refused
    for the same reasons, by the same names. Every slope is odd on purpose: the
    half-year share of `(2 * m - 5) * b` never divides evenly, so the
    truncation `maturity_factor` pins is forced visibly rather than hidden by
    a lucky division.
    """
    raise NotImplementedError("stage 3: implement slope()")


def remaining_years(book, loan, at):
    """The effective maturity of `loan` at `at`, in whole years, clamped.

    The term left to run is the months from `at` to the loan's last contractual
    flow, counted with the world's calendar; `(months + 11) // 12` is the
    whole-year count that rounds a residual month up to its year, and it is
    then clamped by the policy's own walls `M_MIN..M_MAX` — a loan with a month
    left lives at `M_MIN` and a loan with years to spare lives at `M_MAX`.

    A loan the book does not hold, a date the book does not cover, a loan that
    is not on the book at `at`, or one past its remaining term is refused by
    name.
    """
    raise NotImplementedError("stage 3: implement remaining_years()")


def maturity_factor(asset_class, pd_bp, m):
    """`10000 + (2 * m - 5) * b // 2` at `m` whole years and the PD's own `b`.

    `m` is an effective maturity in whole years inside `M_MIN..M_MAX` — the
    clamp `remaining_years` produces — and `b` is the slope `slope` answers for
    `asset_class` at `pd_bp`. The division on the slope's product is **pinned**:
    `(2 * m - 5) * b` is odd for every whole `m` and every row the tables hold,
    so the half-basis-point share has no even answer and the quotient falls
    where Python's floor division puts it — down for the negative adjustment an
    `m` below two and a half produces and down for the positive one above it.

    An `m` outside `M_MIN..M_MAX`, a class outside `CLASSES`, or a PD the bands
    do not key is refused by name.
    """
    raise NotImplementedError("stage 3: implement maturity_factor()")
