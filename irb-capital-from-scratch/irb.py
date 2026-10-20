"""irb.py — the regulator's capital policy, as data.

Provided, frozen, and never written by the course. Where `rules.py` holds the
bank's life-of-loan policy, this module holds the *IRB* policy: the tables the
capital formula is built from, and nothing else. Nothing here computes a
correlation, a maturity adjustment or a quantile from a formula — the tables
**are** the formula — and a stage that needs a value the tables do not carry
refuses by name rather than inventing one.

The tables, and what each one is for:

* `ASSET_CLASS_OF` maps every booking (a segment of the estate) to the asset
  class the formula prices and to a `treat`/`refrigerate` row. A **refrigerate**
  class is one the phase-in holds back: its downturn treatment is frozen at the
  best estimate while its own calibration is under review, so stage 5's
  multiplier does not touch it and the reporting pack still shows it inside its
  class (`"leasing"` is this estate's refrigerated booking).
* `CORRELATION_ROWS` holds the asset correlations `R`, in ten-thousandths of
  full precision — one constant row per retail class and, for `corporate`, one
  row per grid band. The **grid bands** are the PD entries of
  `QUANTILE_GRID`: the policy tabulates its correlations at the same grid
  points it tabulates the quantile, so a PD off the grid has no row and the
  stage that asks for one is refused.
* `QUANTILE_GRID` is the inverse-normal value `Phi-1(pd)` **tabulated**: the
  first column is a cumulative PD in basis points, the second the quantile as
  an integer in ten-thousandths, one row per PD the grid carries, monotone
  non-decreasing in both columns. PD `0` and PD `10000` are rows of the grid —
  the policy answers the grid's own floor and ceiling for them — and a PD
  between the rows is refused, because a value the tables do not carry must not
  be interpolated by a stage that could pick the wrong side of the step.
* The maturity adjustment: `SLOPE_ROWS` holds the slope `b`, in
  ten-thousandths per whole year away from two and a half, again on grid bands;
  `M_MIN` and `M_MAX` are the clamps between which the effective maturity of an
  exposure lives — one whole year to five.
* `DOWNTURN_MULTIPLIER_BP` holds the downturn multiplier per asset class,
  `DOWNTURN_FLOOR_BP` and `DOWNTURN_CAP_BP` the clamps a multiplied LGD may
  never leave, and `COLLATERAL_HAIRCUT_BP` the haircut the collateral may take
  before any of it — a row per collateral kind the estate holds.
* `CCF_BY_PRODUCT_BP` holds the drawn/undrawn conversion factor per product,
  in basis points, with `CCF_FLOOR_BP` and `CCF_CAP_BP` as the estimator's own
  clamps for the factor the bank derives from its defaults.
* `FLOOR_PHASE_PERCENT` is the output floor's phased-in schedule — an integer
  percent of the standardized proxy per calendar year — and
  `STANDARD_WEIGHT_BP` the per-class weights the proxy is a function of.
* `CAPITAL_SCALING_BP` is the formula's own scaling constant, `12.5` carried in
  ten-thousandths, so a capital times an exposure scale to a risk-weighted
  amount with one pinned division and no float ever arrives.

Every number in this module is an integer count of basis points, ten-
thousandths, cents or whole years. No `float` literal appears, and none is
needed: the policy's own shape is a set of step tables a reviewer reads off the
page.
"""

POLICY_VERSION = "IRB-1.0"

POLICY_ERROR = "irb: "

#: The asset classes the formula prices, in their own order.
CLASSES = ("corporate", "retail-mortgage", "revolver", "other-retail")

#: The two classification rows a booking can enter.
REFRIGERATE_KINDS = ("treat", "refrigerate")

#: Every booking (a segment of the estate) to its asset class and its row.
#: `leasing` is this estate's refrigerated booking: an exposure whose class
#: treatment the phase-in holds. The mapping is total over `rules.SEGMENTS`.
ASSET_CLASS_OF = {
    "mortgage": ("retail-mortgage", "treat"),
    "consumer": ("other-retail", "treat"),
    "sme": ("corporate", "treat"),
    "corporate": ("corporate", "treat"),
    "credit-card": ("revolver", "treat"),
    "leasing": ("corporate", "refrigerate"),
}

#: The inverse-normal quantile, tabulated: the first column is a cumulative PD
#: in basis points, the second `Phi-1(pd)` as an integer in ten-thousandths.
#: Sorted by PD, no duplicate PD, monotone non-decreasing in the quantile. The
#: first and last rows are the policy's own endpoints: a PD of nothing answers
#: the grid floor and a PD of a whole cycle the grid ceiling, and every PD
#: between the rows must fall **on** a row or be refused.
QUANTILE_GRID = (
    (0, -3439),
    (10, -2330),
    (25, -1965),
    (50, -1645),
    (75, -1440),
    (100, -1285),
    (150, -1105),
    (250, -840),
    (500, -575),
    (750, -425),
    (1000, -329),
    (1500, -195),
    (2000, -95),
    (2500, -5),
    (3000, 75),
    (3500, 150),
    (4000, 225),
    (5000, 380),
    (6000, 525),
    (7000, 670),
    (8000, 815),
    (9000, 960),
    (10000, 3439),
)

#: The name a refusal carries when it names the grid: a PD off the grid is not
#: the grid's to answer.
GRID_NAME = "pd-quantile-grid"

#: The asset correlations `R`, in ten-thousandths of full precision. The retail
#: classes carry one constant row each; `corporate` carries one row per grid
#: band, the band keyed by the PD entries of `QUANTILE_GRID` (a PD resolves to
#: the latest band whose start it has reached).
CORPORATE_CORRELATION_BP = {
    0: 1200,
    250: 1400,
    750: 1600,
    1500: 1800,
    3000: 2000,
    6000: 2200,
}

RETAIL_CORRELATION_BP = {
    "retail-mortgage": 1500,
    "revolver": 400,
    "other-retail": 300,
}

#: The maturity-adjustment slope `b`, in ten-thousandths per whole year away
#: from two and a half, on the same grid bands. Every slope is odd **on
#: purpose**: the half-year share never divides exactly, so the truncation the
#: docstring pins is forced visibly rather than hidden by a lucky division.
CORPORATE_SLOPE_BP = {
    0: 85,
    250: 95,
    750: 115,
    1500: 135,
    3000: 155,
    6000: 175,
}

RETAIL_SLOPE_BP = {
    "retail-mortgage": 105,
    "revolver": 125,
    "other-retail": 145,
}

#: The clamps between which an effective maturity lives, in whole years.
M_MIN = 1

M_MAX = 5

#: The downturn LGD multiplier per asset class, in basis points per basis
#: point: a multiplier of `13500` raises an LGD of one thousandth of the loan
#: to one and a third thousandths of it, truncated.
DOWNTURN_MULTIPLIER_BP = {
    "corporate": 11500,
    "retail-mortgage": 13500,
    "revolver": 12800,
    "other-retail": 12200,
}

#: The clamps a multiplied LGD may never leave, in basis points. The floor is
#: the policy's own statement about a well-collateralised loan: a downturn LGD
#: may not be estimated at less than half the loan and a half, however much the
#: recoveries said would come back — a loan whose grade row sits at `4500` and
#: whose class multiplies by `1.15` lands at `5175` and the floor holds it up.
DOWNTURN_FLOOR_BP = 5500

DOWNTURN_CAP_BP = 10000

#: The haircut the collateral may take, per collateral kind, in basis points.
#: The estate holds `property`, `receivables`, `equipment` and the kindless
#: booking `none`; anything else refused by name.
COLLATERAL_HAIRCUT_BP = {
    "property": 2000,
    "receivables": 3000,
    "equipment": 5000,
    "none": 10000,
}

#: The drawn/undrawn conversion factor per product, in basis points, and the
#: clamps the bank's own estimate of one is held between.
CCF_BY_PRODUCT_BP = {
    "mortgage": 5000,
    "consumer": 7500,
    "sme": 7000,
    "corporate": 5000,
    "credit-card": 9000,
    "leasing": 6500,
}

CCF_FLOOR_BP = 0

CCF_CAP_BP = 10000

#: The output floor's phased-in schedule: the percentage of the standardized
#: proxy RWA the floor holds, per calendar year, as whole integer percents. The
#: schedule runs from a quarter of the proxy in `2028` to the whole of it in
#: `2035`; a year outside it is refused by name.
FLOOR_PHASE_PERCENT = {
    2028: 25,
    2029: 40,
    2030: 50,
    2031: 60,
    2032: 70,
    2033: 80,
    2034: 90,
    2035: 100,
}

#: The standardized proxy's own weights per asset class, in basis points, as
#: the floor's schedule applies them. The proxy is a function of these rows and
#: the exposures and of nothing else.
STANDARD_WEIGHT_BP = {
    "corporate": 10000,
    "retail-mortgage": 3500,
    "revolver": 4500,
    "other-retail": 7500,
}

#: The formula's own scaling constant, `12.5`, carried in ten-thousandths. A
#: capital requirement scales to a risk-weighted amount through it, with the
#: one division the docstrings pin.
CAPITAL_SCALING_BP = 125000


class PolicyError(ValueError):
    """The policy's refusal: an input outside the tables.

    It names the offender — the booking, the asset class, the PD, the
    collateral kind, the product, the year — because a number the tables do
    not carry must say what it was asked for rather than answer one read off
    the wrong side of a row.
    """
