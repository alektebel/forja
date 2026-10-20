"""IRB and Regulatory Capital — stage 4: The capital requirement K, the exact series.

The IRB formula is not evaluated in closed form here. It is one **integer
series** over the loan's remaining term: for each whole year the loan is
expected to run, the marginal default probability of that year — the difference
of two consecutive cumulative rows on the through-the-cycle grade's own PD
term structure — times the loan's downturn loss given default, discounted by
one more step per year at the loan's own contract rate. The series is summed
with its pinned truncation, and the sum is the answer.

A requirement that arrived as one closed form would hide where the money is
won and lost: a reviewer of a capital pack is handed the year-by-year walk, the
year the marginals go quiet (the artifact's cumulative row ends), the share of
the loss each year discounts to. So the stage returns the whole series — the
marginals in basis points, the discounted contribution each year carries, and
the sum — and every division in the walk is pinned: the LGD share first
(`marginal * lgd_bp // 10000`), then that share discounted
(`share * factor // 10000`), the factor stepping
`factor = factor * 10000 // (10000 + rate_bp)` with the loan's own annual
contract rate, once per year.

One year of term is the series' degenerate but honest case — a single
marginal, a single step — and a grade whose cumulative row is all zeros
answers a series of zeros: a capital of nothing is an answer, not a refusal.
The one thing the stage refuses is a loan that stands past its remaining term,
or is not on the book at all: no term, no series.
TODO: implement `k_requirement` in this file: the discounted, loss-weighted
marginal default one loan's TTC grade and PD row turn it into, at the reporting
date, under the artifact in force."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import dates
import irb
import rules
from book import BookError
from irb import PolicyError

#: The asset classes the multiplier is keyed on, in their own order.
CLASSES = irb.CLASSES

#: The clamps an effective maturity lives between, in whole years.
M_MIN = irb.M_MIN

M_MAX = irb.M_MAX

#: The scale every rate, pd and LGD basis point is held at.
BP_SCALE = 10000


class KError(PolicyError):
    """The refusal this stage raises: something that cannot be a capital series.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the loan past its remaining term, the artifact that carries
    no grade or no PD row for the loan, the artifact field that is not there —
    because a capital the formula cannot stand behind must say what it was
    asked for rather than answer a series the reviewer cannot walk.
    """


def k_requirement(book, loan, at, artifact=None):
    """The exact series: the year-by-year IRB capital of `loan` at `at`.

    `artifact` names the artifact to price with — the check's own fixtures hand
    one; a stage reading the bank prices with `model_in_force` when `artifact`
    is left at `None`. The record carries the grade, the downturn LGD the
    series is priced with, the whole years the loan has left (clamped by
    `irb.M_MIN..irb.M_MAX`), the marginal PD of each year — the difference of
    two consecutive rows of the grade's cumulative PD series, read off the
    through-the-cycle grade, everything past the series' end being zero — and
    the discounted share each year carries:
    `(marginal * lgd_bp // 10000) * factor // 10000`, with the factor stepping
    `factor = factor * 10000 // (10000 + rate_bp)` at the loan's own annual
    contract rate, once per year. `k_bp` is the series summed.

    A loan not on the book at `at`, one past its remaining term, an artifact
    that carries no grade or no PD row for the loan, or a date the book does
    not cover is refused by name.
    """
    raise NotImplementedError("stage 4: implement k_requirement()")
