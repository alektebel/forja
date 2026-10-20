"""IRB and Regulatory Capital — stage 10: The audit the supervisor files.

Everything the course has built becomes one filing. The pack carries, per
asset class and per through-the-cycle grade, the exposures that price into it
— the on-book loans with a remaining term — with each row's exposure count,
its EAD, its capital (the K of stage 4 times the exposure), its risk-weighted
amount (stage 7's rows) and its *applied* risk-weighted amount (stage 8's
floor, at the year the filing names — the greater of the bank's own weight and
the floor's share, exposure by exposure). A coverage ratio per grade closes
the pack: the grade's IFRS 9 provision over its applied RWA, in basis points,
truncated — the one number that says whether the provision column and the
capital column are at all comparable, with the rows where the two cannot agree
carried (stage 9 named them) rather than hidden.

The filing has duties, and this stage enforces them the way a supervisor's
review would. A loan is priced once: every on-book, remaining-term exposure
appears in exactly one (class, grade) row, and the rows' exposure counts add
to the pack's own count. Per class the rows sum to the class, and the classes
sum to the pack's own totals — no column may claim a cent its rows cannot
explain. And the disagreement rows the pack files are exactly the ones stage
9's contract named — same grade, same reason — even when that means filing
nothing, because a pack reconciling quietly would fail loudly only years
later, where a supervisor needs it now.
TODO: implement `capital_pack` in this file: the pack at one reporting date and
one floor phase — its rows, its duties and its coverage — which the packed
arithmetic must survive before a reader may trust it."""

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

#: The asset classes the pack groups by, in the policy's own order.
CLASSES = irb.CLASSES

#: The grades the pack groups by, in the world's own order.
GRADES = rules.GRADES

#: The fields of one exposure row, in order.
ROW_KEYS = ("asset_class", "grade", "exposures", "ead_cents", "capital_cents",
            "rwa_cents", "applied_rwa_cents")

#: The fields of the pack itself, in order.
PACK_KEYS = ("at", "floor_year", "percent", "exposures", "total_rwa_cents",
             "applied_rwa_cents", "capital_cents", "rows", "coverage_bp",
             "disagreements")

#: The fields of a coverage row: the grade and its basis points of coverage.
COVERAGE_KEYS = ("grade", "coverage_bp")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class AuditError(PolicyError):
    """The refusal this stage raises: something that cannot be a filing.

    It names the offender — the year outside the floor's schedule, the date the
    book does not cover, the artifact the pack's capital column would need and
    does not find, a duty the pack's own rows broke and the loan that broke it
    — because a filing a supervisor must be able to walk must say what it was
    asked for rather than file one no row can explain.
    """


def phase(year):
    """The schedule row of `stage 8`, read by this stage as the filing's percent."""
    raise NotImplementedError("stage 10: implement phase()")


def capital_pack(book, at, floor_year):
    """The pack the supervisor files: exposures, weights, floor, capital, coverage.

    `floor_year` names the year's floor answer (the schedule row `phase`
    answers); `at` names the reporting date the pack prices at. The pack's
    rows are keyed `(asset_class, grade)` in the order the two tables are
    pinned in — `irb.CLASSES` then `rules.GRADES` — so a reader and a program
    agree on what row one is and every class and grade the estate prices into
    is answered. Per row: the exposure count, the EAD the loans carry, the
    capital K prices in cents (`k_bp * ead_cents // 10000`), the risk-weighted
    amount and the applied amount after the floor's share, exposure by
    exposure.

    `coverage_bp` answers, per grade, its IFRS 9 provision over its applied
    RWA in basis points — `provision * 10000 // applied`, truncated, and a
    grade the floor and the weights price at nothing answers zero — and
    `disagreements` carries the stage 9 contract's reason rows, recomputed
    here by the same contract, not imported from a stage of this course.

    A year outside the floor's schedule, a date the book does not cover, an
    artifact column the pack cannot read, or a duty the pack's own rows break
    — a loan priced twice, a row claiming a cent its loans do not carry — is
    refused by name.
    """
    raise NotImplementedError("stage 10: implement capital_pack()")
