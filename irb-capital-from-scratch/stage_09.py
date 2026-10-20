"""IRB and Regulatory Capital — stage 9: The two books, reconciled per grade.

The estate carries two books at one reporting date and they *must* be read side
by side, per grade. The accounting book groups its provisions by the
point-in-time grade — each on-book loan's status row carries the ecl the bank
recorded, and the IFRS 9 side of a grade is the sum of those — and the capital
book groups its risk weights by the through-the-cycle grade. Same grades as
labels, different books underneath: a loan the bank has signalled as defaulted
provisions on the `default` row and still prices on the letter its artifact
carries; a loan the bank upgraded provisions on the letter and prices on the
cycle grade it was rerated to. The world's own roll-forward total is the
closing anchor — `book.rollforward(at, at)` — and the IFRS 9 side must add to
it, or the provision column is not the bank's provisions at all. That anchor is
asserted here, not claimed.

`irreconcilable` then names the rows where the two cannot agree, and the reason
code is the contract's, not the stage's: `basis` when the two sides of a grade
hold different loan ids — the loan the two books disagree about *which* column
it belongs in — and `horizon` when both books hold the same loans but money
differs, because a provision over one reporting horizon is never the same
number as a capital over the whole life. A row where the two agree, in ids and
in cents, is not a disagreement and answers nothing at all: silence is the
reconciliation that holds.
TODO: implement `per_grade` and `irreconcilable` in this file: the two sides of
the provision story by grade, and the reasons their sums disagree by, so the
tie between accounting and capital is a named thing and not a silent gap."""

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

#: The grades the reconciliation reads per, in the policy's own order.
GRADES = rules.GRADES

#: The two books the stage reads, in the order the rows name them.
KINDS = ("pit", "ttc")

#: The reason codes the contract pins, in their own order.
REASONS = ("basis", "horizon")

#: The fields of one side-by-side row, in order.
GRADE_KEYS = ("grade", "ifrs9_ids", "ifrs9_provision_cents", "irb_ids",
              "irb_capital_cents")

#: The fields of one disagreement row, in order.
RECONCILE_KEYS = ("grade", "reason", "ifrs9_ids", "irb_ids", "ifrs9_provision_cents",
                  "irb_capital_cents")

#: The scale every basis-point and rate measure is held at.
BP_SCALE = 10000


class ReconcileError(PolicyError):
    """The refusal this stage raises: something that cannot be a reconciliation.

    It names the offender — the date the book does not cover, the artifact the
    capital side needs and does not find, the grade outside `rules.GRADES` —
    because a reconciliation that cannot be built must say what it was asked
    for rather than reconcile two books one of which was never read.
    """


def per_grade(book, at):
    """Both books, per grade: the provision against the capital, side by side.

    The `ifrs9` side groups each on-book loan's own status row — its ecl, the
    provision the bank recorded — by the *point-in-time* grade the bank asserts
    at `at`; the capital side groups each loan's risk-weighted amount — stage
    7's rows, recomputed — by the *through-the-cycle* grade the artifact in
    force carries. Every grade of `rules.GRADES` is answered, an empty one as
    an empty pair of columns, so a reader sees the grade nobody sits in rather
    than missing it; within a grade the loan ids come in estate order and the
    identity of the two sides is what `irreconcilable` reads. The IFRS 9
    column adds to the world's own roll-forward closing amount — the bank's
    own books, not this stage's sum — or `ReconcileError` is raised rather
    than reconciled.

    A date the book does not cover, and an artifact the capital side cannot
    find, are refused by name.
    """
    raise NotImplementedError("stage 9: implement per_grade()")


def irreconcilable(book, at):
    """The rows the two books cannot agree on, each with one pinned reason code.

    A grade's two sides disagree on the *basis* when they hold different loan
    ids — the loan whose provision column is the defaulted row and whose
    capital column still prices on its cycle letter — and on the *horizon* when
    the ids are the same and the money differs, which is the standing fact of a
    reconciliation: a provision over one reporting horizon is not a capital
    over the whole life. A grade that agrees in both ids and cents answers
    nothing — it is not a disagreement, and a reconciliation that named
    agreeing rows would be inventing problems to look thorough.

    A date the book does not cover, and an artifact the capital side cannot
    find, are refused by name.
    """
    raise NotImplementedError("stage 9: implement irreconcilable()")
