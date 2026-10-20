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
"""

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


def _whole(value, what):
    """`value` as a whole number, or a refusal naming the field it arrived in."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise WeightError("the %s %r is a %s, not a whole number"
                          % (what, value, type(value).__name__))
    return value


def _checked_pd(pd_bp):
    """A PD the quantile grid carries, or a refusal naming the grid and the PD."""
    checked = _whole(pd_bp, "pd in basis points")
    for row in irb.QUANTILE_GRID:
        if row[0] == checked:
            return checked
    raise WeightError("the %s carries no row for PD %d, so no band keys on it"
                      % (GRID_NAME, checked))


def _checked_class(asset_class):
    """The asset class, or a refusal naming the one that arrived."""
    if asset_class not in CLASSES:
        raise WeightError("%r is not an asset class the policy prices; the classes "
                          "are %r" % (asset_class, CLASSES))
    return asset_class


def _band(asset_class, pd_bp):
    """The band key the PD resolves to: a grid PD for `corporate`, the class elsewhere."""
    checked = _checked_pd(pd_bp)
    if asset_class != "corporate":
        return checked, asset_class
    band = None
    for start in sorted(irb.CORPORATE_CORRELATION_BP):
        if start <= checked:
            band = start
    return checked, band


def correlation(asset_class, pd_bp):
    """The correlation row `R`, in ten-thousandths, for `asset_class` at `pd_bp`.

    A retail class answers its constant row; `corporate` answers the band the
    PD has reached — the latest grid PD start the PD sits on or above. A class
    outside `CLASSES` or a PD not on the grid is refused by name.
    """
    _checked_class(asset_class)
    _checked, band = _band(asset_class, pd_bp)
    if asset_class == "corporate":
        return irb.CORPORATE_CORRELATION_BP[band]
    return irb.RETAIL_CORRELATION_BP[asset_class]


def slope(asset_class, pd_bp):
    """The maturity-adjustment slope `b`, in ten-thousandths, on the same bands.

    The rows carry the same grid banding the correlations do — one row per grid
    band for `corporate`, one constant row per retail class — and are refused
    for the same reasons, by the same names. Every slope is odd on purpose: the
    half-year share of `(2 * m - 5) * b` never divides evenly, so the
    truncation `maturity_factor` pins is forced visibly rather than hidden by
    a lucky division.
    """
    _checked_class(asset_class)
    _checked, band = _band(asset_class, pd_bp)
    if asset_class == "corporate":
        return irb.CORPORATE_SLOPE_BP[band]
    return irb.RETAIL_SLOPE_BP[asset_class]


def _loan_id(loan):
    """The identity a loan arrives under, as the book's records name it."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


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
    loan_id = _loan_id(loan)
    try:
        live = book.on_book(at)
    except BookError as refused:
        raise WeightError("the remaining term at %s cannot be read (%s)" % (at, refused))
    if loan_id not in live:
        raise WeightError("loan %r is not on the book at %s, so it has no remaining "
                          "term" % (loan_id, at))
    try:
        flows = book.schedule(loan_id)["flows"]
    except (BookError, KeyError) as refused:
        raise WeightError("loan %r has no contract the book holds (%s)"
                          % (loan_id, refused))
    if not flows:
        raise WeightError("loan %r has no flow to time" % (loan_id,))
    last = flows[-1]["date"]
    months = 0
    while dates.add_months(at, months + 1) <= last:
        months += 1
    if months <= 0:
        raise WeightError("loan %r stands past its remaining term at %s (the last "
                          "flow is %s)" % (loan_id, at, last))
    return min(M_MAX, max(M_MIN, (months + 11) // 12))


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
    _checked_class(asset_class)
    m_years = _whole(m, "effective maturity in whole years")
    if m_years < M_MIN or m_years > M_MAX:
        raise WeightError("the effective maturity %d is outside the policy's "
                          "walls %d..%d whole years" % (m_years, M_MIN, M_MAX))
    _checked, band = _band(asset_class, pd_bp)
    if asset_class == "corporate":
        b = irb.CORPORATE_SLOPE_BP[band]
    else:
        b = irb.RETAIL_SLOPE_BP[asset_class]
    return MF_BASE + (2 * m_years - 5) * b // 2


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    rows = []
    for held in led.loans():
        for at in (led.reporting_dates[0], led.reporting_dates[24]):
            try:
                rows.append((held["loan"], at, remaining_years(led, held["loan"], at)))
            except WeightError as refused:
                rows.append((held["loan"], at, str(refused).split(" (%")[0]))
    print("loan | at          | m")
    for row in rows:
        print("%-5s | %s | %r" % row)
    print()
    for asset_class, pd_bp in (("corporate", 5000), ("retail-mortgage", 0),
                               ("revolver", 9000)):
        print("%-15s at pd %5d: R=%d b=%d  mf(1)=%d  mf(4)=%d  mf(5)=%d"
              % (asset_class, pd_bp, correlation(asset_class, pd_bp),
                 slope(asset_class, pd_bp),
                 maturity_factor(asset_class, pd_bp, 1),
                 maturity_factor(asset_class, pd_bp, 4),
                 maturity_factor(asset_class, pd_bp, 5)))
    try:
        maturity_factor("corporate", 5200, 3)
    except WeightError as refused:
        print("off-grid: %s" % (refused,))
