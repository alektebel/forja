"""Distressed Debt Investing From Scratch — stage 3: Expected recovery from what actually happened.

The buy side of this course cannot read the world's answer key — the outcome
the close recorded is the thing the grades in stage 10 are marked against — so
it needs a recovery estimate it can defend without it. This stage builds one
out of the only facts a fund may use: what the bank's own lending on the same
segment ACTUALLY collected when it defaulted.

The book (`book.py`, the bank's own world) holds the defaulted loans, their
principal and their recovery cash flows. The stage filters that book down to
the loans that defaulted on the segment the claim rides — `loan["segment"] ==
claim["segment"]` — and only the ones with recoveries to read: a defaulted
loan that collected nothing still contributes its par, but a segment where
nothing has yet defaulted cannot answer a rate at all, and is refused by name.

Every recovery row feeds the walk. A row the book marked `collateral` rides
its loan's collateral haircut (`rules.COLLATERAL_HAIRCUT_BP`, keyed by the
loan's own collateral kind) — the recovery is on the asset, less the haircut
the policy books on it. Every row is then discounted to `at` the distance of
`months_between(at, row_date)` months, one factor step at a time the way M1's
own world discounts — `factor = factor * 10000 // (10000 + period_rate)` —
with the rate each loan was written at. A recovery collected before `at` rides
undiscounted (zero months); one collected after `at` is discounted forward,
the distance of the months between them. The answer is `discounted_cents`
over the segment's defaulted par: a rate in basis points of par, and the
cents that rate gives the claim's own face.

    FORECAST_KEYS                 the nine fields of an expected recovery, in order
    ForecastError                 the refusal this stage raises
    expected_recovery(book, claim, at)
                                  -> FORECAST_KEYS, off the bank's actuals only

DESIGN DECISION — why is the walk matched on the segment, not on the collateral?
Because the claim rides a book segment — Berthline's distressed paper is
corporate lending — and the bank's defaulted corporate loans are the actuals
any corporate claim of that borrower could cite. Matching on the collateral
kind as well would leave the unsecured and the subordinated bonds unable to
cite anything (the bank's secured corporate loan is the only defaulted one of
them), and a forecast that refuses to answer for three of the four claims
informs nobody. The haircut stays collateral-by-collateral: each recovery row
is cut by its OWN loan's collateral kind, since the haircut is a policy on the
asset backing that loan, not on the claim reading the segment.

DESIGN DECISION — why does a recovery after `at` discount, and one before ride
flat?
Because the walk discounts a recovery the distance of months it sits from the
day the forecast is made, in whichever direction: a recovery the fund expects
in five months is worth the stepped factor, and one the bank already banked is
worth its amount — it arrived. The world's actuals were collected before the
fund's entry date, so they ride undiscounted there, and a check pins the
forward direction from an earlier `at`: the same walk evaluated before the
recoveries happened must discount them, one factor step per month, and answer
the lower rate.

DESIGN DECISION — why is the factor stepped one recovery at a time and never
powered?
Because the factor is a truncated integer in ten-thousandths —
`factor = factor * 10000 // (10000 + period_rate)` — and a power would either
float it or explode it. Stepping keeps every integer inside the scale of the
recovery it is applied to, keeps the arithmetic reproducible by hand, and
lands the discount discontinuously at exactly the months the calendar says.
It is the same shape the bank's own present values took, and this course
refuses to invent a second one.

DESIGN DECISION — why is the answer both a rate and the cents the claim would
recover?
Because the record serves two callers: the stages that reason about the
segment (the three-reading stage needs the rate to lay beside the Merton and
comparables views) and the stages that reason about the claim (the thesis
needs the cents the fund's face would recover on this view). The rate is
`discounted * 10000 // par` of the segment's defaulted book — the reading that
reproduces by hand; the cents apply that rate, truncated, to the claim's own
face. Both answer to the cent, and neither is rounded a second time.

DESIGN DECISION — why is the equity refused outright?
Because an equity claim rides no par: there is no face for a recovery rate to
apply to, and the book's lending never sold claims against the sponsor's
upside. A fund that "forecast a recovery" on its equity would be pricing the
going concern, which is the valuation machinery of another world. The refusal
names the claim, so the mistake is visible at the call rather than buried in a
rate applied to zero.

TODO: implement `ForecastError` and `expected_recovery` in this file: the
segment's own defaulted book, haircutted and discounted to `at`, answering a
rate in basis points of par and the cents that rate gives the claim's face.

    The request is refused by name when the claim record carries no `kind`,
    `segment` or `face_cents`, when the kind is `equity`, when the book's
    segment has no defaulted loan with recoveries to read, and when `at` is
    not a date the calendar accepts.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import dates
import rules
import claims as market

PAR_BP = 10000

FORECAST_KEYS = ("claim", "at", "segment", "collateral_kind", "loans",
                 "par_cents", "discounted_cents", "expected_cents", "expected_bp")


class ForecastError(ValueError):
    """The refusal this stage raises: something that cannot be a forecast.

    It names the offender — the claim the book cannot read, the segment with
    no defaulted loan behind it, the date the calendar does not accept —
    because a recovery estimate nobody can trace to actuals must say what it
    was asked for rather than answer a number nobody can underwrite on.
    """


def _months_between(start, end):
    """The whole months from `start` to `end`, the calendar's clamping honoured.

    A flow landing on the day itself is zero months away, and a start on a
    day the target month does not have still answers the floor the calendar's
    own `add_months` puts under it.
    """
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months


def expected_recovery(book, claim, at):
    """The recovery rate the bank's own defaulted book gives the claim's segment.

    The walk reads every defaulted loan on `claim["segment"]` that collected
    anything: its principal counted into the segment's par, its recovery rows
    haircutted where they came from collateral and discounted to `at` at the
    loan's own rate, one truncating factor step per month of distance. The
    answer is the discounted cents over the par, in basis points of it, and
    those cents applied to the claim's own face.

    A claim of kind `equity`, a record the book cannot read, a segment with no
    defaulted loan to read and a date `at` the calendar refuses, is refused by
    name.
    """
    raise NotImplementedError("stage 3: implement expected_recovery()")
