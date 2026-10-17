"""rules.py — the bank's rulebook, as data.

Provided, frozen, and never written by the course. Nothing here computes a
provision, a bucket or a rate from a loan — it is somebody else's *decision*, and
the whole course is held to it. The policy's own numbers are what make the ten
stages answerable at all: the buckets and their day bounds, the materiality test
two halves, the probation a default must survive before it cures, the SICR test's
multiplier and its absolute floor, the scenarios and their weights, the LGD and
CCF floors and caps, the collateral haircuts, and the fixed-point scale every
basis point is divided by.

Two constants deserve a word before they are used:

* `MATERIALITY_ABSOLUTE_CENTS` and `MATERIALITY_RELATIVE_BP` are **two halves of
  one test, and both must pass** for arrears to count towards days past due. A
  loan whose arrears sit below €100 does not accrue days past due however long
  they have been sitting there, and neither does one whose arrears are under 1%
  of its exposure — and a stage that takes either half alone is wrong.
* `CHI2_CRITICAL_X100` is a **provided table**: a critical value comes from a
  statistical table, not from this course's arithmetic. `384` is the 95% critical
  value for one degree of freedom, times one hundred, so stage 10's statistic can
  stay in integers.

`period_rate(rate_bp, basis)` is the one function here, because the *period* is
the world's decision, not a stage's: a monthly period is thirty days, so a rate
per year becomes `rate_bp * 30 // 360` under `thirty-360` and `rate_bp * 30 // 365`
under `actual-365`, truncated. The two bases therefore never agree, which is what
makes the basis a real input rather than decoration.
"""

GRADES = ("A", "B", "C", "D", "E", "F", "default")

SEGMENTS = ("mortgage", "consumer", "sme", "corporate", "credit-card", "leasing")

BUCKETS = ("performing", "1-30", "31-60", "61-90", "default")

BUCKET_DAYS = (0, 30, 60, 90)

DEFAULT_DAYS_PAST_DUE = 90

MATERIALITY_ABSOLUTE_CENTS = 10000

MATERIALITY_RELATIVE_BP = 100

CURE_MONTHS = 3

UTP_FLAGS = ("forbearance", "distressed-restructuring", "cross-default", "bankruptcy")

SICR_MULTIPLIER_BP = 20000

SICR_ABSOLUTE_BP = 300

SICR_DAYS_PAST_DUE = 30

SICR_RETURN_PERIODS = 2

SCENARIOS = ("base", "adverse", "upside")

SCENARIO_WEIGHTS_BP = {"base": 5000, "adverse": 2500, "upside": 2500}

SCENARIO_PD_MULTIPLIER_BP = {"base": 10000, "adverse": 18000, "upside": 7000}

COLLATERAL_HAIRCUT_BP = {"cash": 0, "receivables": 3000, "property": 2000,
                         "equipment": 5000, "none": 10000}

LGD_FLOOR_BP = 0

LGD_CAP_BP = 10000

CCF_FLOOR_BP = 0

CCF_CAP_BP = 10000

MAX_EIR_BP = 10000

EIR_TOLERANCE_BP = 1

CHI2_CRITICAL_X100 = {1: 384, 2: 599, 3: 781, 4: 949, 5: 1107, 6: 1259}

DISCOUNT_SCALE = 10000

PERIODS_PER_YEAR = 12

POLICY_VERSION = "credit-lifecycle-v1"

#: The day count the book's own records are kept on. A stage still has to answer
#: for both of `dates.BASES`.
DEFAULT_BASIS = "actual-365"

#: The policy's own view of a month: thirty days. A rate per year is scaled by it
#: to reach a period rate, under whichever day count the caller names.
PERIOD_DAYS = 30

_BASIS_YEAR_DAYS = {"thirty-360": 360, "actual-365": 365}

RULES_ERROR = "rules: "


class RuleError(ValueError):
    """The rulebook's refusal: a rate or a basis it cannot scale."""


def period_rate(rate_bp, basis):
    """The rate **per monthly period**, in basis points, under `basis`.

    A period is thirty days, so `thirty-360` scales the year by `30/360` and
    `actual-365` by `30/365`, and both truncate. `period_rate(1200, "thirty-360")`
    is `100`; `period_rate(1200, "actual-365")` is `98`. A `rate_bp` that is not a
    whole number, or a basis the policy does not know, is refused by name.
    """
    if isinstance(rate_bp, bool) or not isinstance(rate_bp, int):
        raise RuleError(RULES_ERROR + ("the rate %r is a %s, not a whole number of "
                                       "basis points" % (rate_bp, type(rate_bp).__name__)))
    if basis not in _BASIS_YEAR_DAYS:
        raise RuleError(RULES_ERROR + ("%r is not one of the bases %r"
                                       % (basis, tuple(_BASIS_YEAR_DAYS))))
    return rate_bp * PERIOD_DAYS // _BASIS_YEAR_DAYS[basis]
