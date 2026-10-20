"""IRB and Regulatory Capital — stage 7: Risk weight and the RWA.

A capital requirement prices an exposure at a **risk weight**, and the risk
weight is where the whole formula lands: the series K of stage 4, the maturity
adjustment of stage 3, and the scaling constant the policy holds for itself —
`12.5` carried in ten-thousandths as `CAPITAL_SCALING_BP` — multiplied
together and set against the exposure at default the stage-6 arithmetic
answers. The record arrives exactly as the supervisor wants to read it: the
loan, the asset class it prices to, the weight in basis points, and the
risk-weighted amount in cents — `rw_bp * ead_cents // 10000`, one division,
pinned.

The whole book is then a total, and the stage makes the total defensible: it
runs over the loans on the book at the reporting date that still have a
remaining term, and it answers the per-class split of the same rows — the
sum of the very risk weights it just computed, keyed by `irb.CLASSES`, with a
class that prices nothing in the estate still answered as a zero row rather
than dropped, so a reader sees the empty class rather than missing it.

What this stage refuses is a loan that is not on the book at all (a
derecognised holding carries no RWA), a loan past its remaining term (no term,
no weight), and a date the book does not cover — by name, as everywhere in
this course.
TODO: implement `risk_weight` and `total_rwa` in this file: the formula's
weight one loan's TTC grade and asset class scale to, and the whole book's
risk-weighted amount at a reporting date."""

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

#: The asset classes the formula prices, in their own order.
CLASSES = irb.CLASSES

#: The scaling constant, `12.5` in ten-thousandths: the policy's own number.
CAPITAL_SCALING_BP = irb.CAPITAL_SCALING_BP

#: The clamps an effective maturity lives between, in whole years.
M_MIN = irb.M_MIN

M_MAX = irb.M_MAX

#: The drawn/undrawn conversion factors, as the policy carries them.
CCF_BY_PRODUCT_BP = irb.CCF_BY_PRODUCT_BP

#: The fields of one risk-weight record, in order.
RW_KEYS = ("loan", "asset_class", "rw_bp", "ead_cents", "rwa_cents")

#: The fields of the whole-book total, in order.
RWA_KEYS = ("at", "exposures", "total_rwa_cents", "by_class")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class RwaError(PolicyError):
    """The refusal this stage raises: something that cannot be a risk weight.

    It names the offender — the loan the book does not hold, one not on the
    book at the reporting date, one past its remaining term, the date the book
    does not cover, the artifact the stage would need and does not find —
    because a weight the formula cannot stand behind must say what it was asked
    for rather than answer one a reviewer cannot walk.
    """


# -- the stage's own surface ------------------------------------------------

def risk_weight(book, loan, at):
    """The risk weight of `loan` at `at`: K, the maturity adjustment and `12.5`.

    The weight is the capital series of stage 4 — the year-by-year sum of
    marginal PDs, downturn LGDs and discounted shares — lifted by the maturity
    adjustment `10000 + (2 * m - 5) * b // 2` at the whole years the loan has
    left, scaled by the policy's own `12.5` in ten-thousandths with one
    truncated division: `k_bp * mf * CAPITAL_SCALING_BP // (10000 * 10000)`.
    The record carries the weight, the exposure stage 6 answers and the
    risk-weighted amount `rw_bp * ead_cents // 10000`.

    A loan not on the book at `at`, a loan past its remaining term, a date the
    book does not cover, or an asset class the policy does not price is
    refused by name.
    """
    raise NotImplementedError("stage 7: implement risk_weight()")


def total_rwa(book, at):
    """The whole book's risk-weighted amount at `at`, and its split by class.

    The loans on the book at `at` that still have a remaining term — a matured
    holding is out of the estate's own risk, at least until someone writes a
    policy for it — each priced at `risk_weight`, and the answer is the sum and
    the per-class split **of those same rows**: no row is recomputed at a
    different rate, no class is keyed on anything but `irb.CLASSES`, and a
    class that prices nothing answers a zero row instead of being dropped, so a
    reader sees the empty class rather than missing it.

    A date the book does not cover is refused by name; so is the artifact the
    stage would need and does not find.
    """
    raise NotImplementedError("stage 7: implement total_rwa()")
