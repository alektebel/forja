"""IRB and Regulatory Capital — stage 1: PIT vs TTC, and where each is legal.

Before any formula runs, a bank has to say *which book* it is quoting a grade
from. The same loan carries two answers that are both honest and not equal: the
grade the bank's own signals asserted for it at a reporting date — its
point-in-time grade, the one IFRS 9 provisions against — and the grade the
regulatory artifact in force carries for it — its through-the-cycle grade, the
one the IRB formula prices from. A loan the bank has signalled as defaulted has
no letter left on its own books, and the artifact can still be carrying an `A`
for the very same loan; a loan the bank has upgraded under its stamp can still
sit on the cycle grade it was rereated to.

This stage is where the two labels are read, and where the course decides which
one a question may ask for. A capital query (the RWA pipeline, stages 4-10) may
only cite the through-the-cycle grade, because the formula is a function of a
cycle and not of one reporting date; an accounting query (the provision side of
stage 9) may only cite the point-in-time grade, because a provision is about
this loan as it stands now. Asking a use for the other kind is refused by name —
not answered, not quietly converted, refused — because the classic way a capital
pack quietly diverges from a provision stack is a grade fetched from the wrong
book and never noticed.
TODO: implement `pit`, `ttc` and `legal` in this file: the loan's two grades at
a reporting date — the bank's own signal and the artifact in force — and which
kind of query each of the course's uses may cite."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import rules
from book import BookError
from irb import PolicyError

#: The two kinds of grade this stage moves around, in their own order.
KINDS = ("pit", "ttc")

#: The uses a question can arrive under, and the kind each one may cite.
USE_KINDS = (("capital", "ttc"), ("accounting", "pit"))


class RatingError(PolicyError):
    """The refusal this stage raises: something that cannot be a rating.

    It names the offender — the loan the book does not hold, the date the book
    does not cover, the artifact that is not in force, the use outside
    `USES_KINDS`, the kind outside `KINDS` — because a grade quoted from the
    wrong book must say what it was asked for rather than answer one the reading
    cannot defend.
    """


def pit(book, loan, at):
    """The grade the bank's own signals asserted for `loan` at `at`.

    The point-in-time grade is the bank's own record: the loan's state on the
    bank's stamps — its arrears, its forbearance, its default signals, its
    cures — read as the book evaluates it at this date. Because `default` is a
    *signal* the bank asserts and removes, a loan that has since cured answers
    the letter it came back to, and a loan still defaulted answers `default`
    however the artifact prices it.

    A loan the book does not hold, or a date the book does not cover, is
    refused by name.
    """
    raise NotImplementedError("stage 1: implement pit()")


def ttc(book, loan, at):
    """The through-the-cycle grade the regulatory artifact in force carries.

    The artifact is read off the book (`model_in_force`), its `grades` table
    quoting one grade per loan, re-rated only when a new version was published:
    the artifact's grade is a property of the cycle the model was calibrated
    for, not of the bank's signals on this date. A loan the bank has signalled
    as defaulted can still carry the letter the artifact priced it at — that
    gap is the point of the stage.

    A loan the book does not hold, a date the book does not cover, or a date
    with no artifact in force yet is refused by name.
    """
    raise NotImplementedError("stage 1: implement ttc()")


def legal(query, kind):
    """Whether a `query` may cite `kind` — and refused rather than false when not.

    A `capital` query (stages 4-10) accepts only the through-the-cycle grade
    and an `accounting` query (stage 9) accepts only the point-in-time one. A
    query outside `USE_KINDS`, or a kind outside `KINDS`, is refused rather
    than answered false, so a caller learns what it was allowed to cite.
    """
    raise NotImplementedError("stage 1: implement legal()")
