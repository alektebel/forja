"""Distressed Debt Investing From Scratch — stage 10: The thesis, checked against what actually happened.

Every number the course computed so far was a line in one argument the fund
makes about one trade. This stage is that argument written down, and then
graded by the world against what the parties actually settled.

The thesis is the fund's underwriting book for the position it holds: the
claim, the day the fund decided, the close the argument runs to, the months
between them; the cost the sheet charged over the position's held face at
the position's own price; the three readings it bought on — the bank's
actuals on the claim's segment, the identity's distance walked through the
world's own ladder, and the comparables' trading view — with the middle one
the underwriting cleared on; the receipts the close's exchange and waterfall
recomputed, the return the fund's wall-bounded search finds over them, the
residue the whole basis points leave; the carry holding costs over the
months, the upside the view implies over the price paid, and the decision
that comparison answers — hold, or pass.

The audit grades that argument claim by claim through the world's own answer
key: per debt claim, the middle of the three readings the fund underwrote
on, the realised basis points what actually settled paid over the face, the
gap between them, and a grade — pass when the gap is inside the
 world's audit
tolerance, fail when it is not. The audit takes both worlds by hand — the
bank's `book` and the market's `claims` module — because the capstone is the
one place in the course where the two sides of the trade meet, and it is the
only stage allowed to read the answer key: the stats ledger counts every ask
of the `outcome` door, and the check counts them before and after.

    THESIS_KEYS                   the eighteen fields of the thesis, in order
    AUDIT_KEYS                    the thirteen fields of one graded claim, in order
    GRADES                        the two grades the audit may give, in order
    ThesisError                   the refusal this stage raises
    thesis(claim, at)             -> THESIS_KEYS: the fund's written argument
    audit(book, claims, at, close)
                                  -> one AUDIT_KEYS row per debt claim: the
                                     grades against what actually happened

DESIGN DECISION — why does the thesis answer for the position the fund
holds, and refuse every other claim by name? Because a thesis nobody
committed capital to is an essay, not an underwriting file: the fund's
record carries the price it actually paid and the face it actually holds,
and every cost, carry and upside in the file is computed over them. Answering
for a claim the fund never bought would be a record that looks like the
real one and audits against nothing — so the stage walks the fund's own
positions, and a claim they do not hold is refused.

DESIGN DECISION — why does the audit take the two worlds as arguments
instead of reading a passed-in thesis? Because the audit is the world
grading the FUND, not the fund grading its own homework: it recomputes the
three readings from the bank's actuals, the identity and the comparables —
the same legs the thesis used — and only then opens the answer key to grade
the middle against what settled. A thesis the audit took on faith could be
right only because it said so; recomputing the legs makes the grading trap
both files' arithmetic at once.

DESIGN DECISION — why is the realised basis point received times par over
the face, and the grade one absolute gap against the fund's own tolerance?
Because the answer key is cents and the thesis is basis points, so the two
only meet at one scale: what arrived over what was owed. The tolerance is
the fund's OWN audit_tolerance_bp — a house number, carried in the world's
fund facts and pinned by the check — because who the grader is decides how
far a miss is missed: the fund must survive its own bar, not the model's.

DESIGN DECISION — why is the capstone the only stage that reads the answer
key, and why does not one line of the thesis? Because the recovery stage's
discipline holds all the way down: the modelling stages reproduce the close
from the facts below it, the thesis is computed before the close is known,
and only the audit — after the fact, claim by claim — opens `outcome` to
grade. The ledger makes that boundary mechanical: the check counts the
`outcome` counters before and after the thesis and they must not move, and
after the audit they must stand at one ask per debt claim.

DESIGN DECISION — why is the middle the grade the realised close is compared
to, and not the best of the three readings? Because the middle is what the
fund underwrote on — the stage-5 reading the decision cleared on. Grading
the best case would flatter every trade the comps flattered, grading the
worst would fail every trade the ladders saved; the middle is the number
the trade was bought on, which is the number the audit grades.

TODO: implement `ThesisError`, `thesis` and `audit` in this file: the
fund's own book of the held position — cost, the three readings, the
middle, the receipts the close's terms pay the held face, the searched
return and its residue, the carry, the upside and the decision — and the
audit that recomputes the legs claim by claim, grades the middle against
what actually settled, and answers one row per debt claim.

    `thesis` refuses by name a record that is not a claim, the equity, a
    claim the fund holds no position on, and a date that is not the day the
    position itself was taken. `audit` refuses by name a close that is not
    the world's own close date, a date the asset path has no reading for,
    and any world or book argument it cannot read.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import book
import dates
import rules
import claims as market

PAR_BP = 10000

#: The wall the return search never crosses — carried from the entry stage's
#: discipline and pinned by the check against the world's fund facts.
MAX_RATE_BP = 60000

THESIS_KEYS = ("claim", "at", "close", "months", "face_cents", "price_bp",
               "cost_cents", "forecast_bp", "merton_bp", "comparables_bp",
               "middle_bp", "receipts_cents", "irr_bp", "pv_cents",
               "residue_cents", "carry_cents", "upside_cents", "decision")

AUDIT_KEYS = ("claim", "at", "close", "received_cents", "face_cents",
              "realised_bp", "forecast_bp", "merton_bp", "comparables_bp",
              "middle_bp", "tolerance_bp", "gap_bp", "grade")

#: The two grades the audit may give, and no others.
GRADES = ("pass", "fail")


class ThesisError(ValueError):
    """The refusal this stage raises: an underwriting file the world cannot hope."""

    # TODO stage 10: raise this with the offender in the message.


def thesis(claim, at):
    """The fund's written argument for the position it holds.

    The cost is the position's own fields over its own face; the three
    readings re-derive themselves from the worlds right here; the receipts
    are the close's exchange terms over the held face; the return is
    searched under the wall with the residue reported; the carry, the
    upside and the decision close the file.

    A record that is not a claim, the equity, a claim the fund holds no
    position on, and a date that is not the day the position was taken, are
    refused by name.
    """
    raise NotImplementedError("stage 10: implement thesis()")


def audit(book, claims, at, close):
    """The thesis's legs, claim by claim, graded against what actually settled.

    Per debt claim of the structure: the three readings recomputed at `at`,
    the middle, the realised basis points the answer key recorded over the
    face, the gap and the grade against the fund's own tolerance. This is
    the only reader of the answer key the course allows.

    A close off the world's own, a date the asset path has no reading for,
    and worlds the machinery cannot read, are refused by name.
    """
    raise NotImplementedError("stage 10: implement audit()")


if __name__ == "__main__":
    fund = market.fund()
    held = fund["positions"][0]
    structure = market.structure()
    print("the fund's thesis, the argument the whole course writes:")
    for record in structure:
        try:
            got = thesis(record, held["dated"])
            print("  %-9s at %s: triplet %d/%d/%d, middle %d, receipts %d,"
                  % (got["claim"], got["at"], got["forecast_bp"],
                     got["merton_bp"], got["comparables_bp"], got["middle_bp"],
                     got["receipts_cents"]))
            print("              return %d bp with residue %d, carry %d,"
                  " upside %d -> %s"
                  % (got["irr_bp"], got["residue_cents"], got["carry_cents"],
                     got["upside_cents"], got["decision"]))
        except ThesisError as refused:
            print("  %-9s refused: %s" % (record["claim"], refused))
    print("the audit, against what actually settled:")
    b = book.Book.build()
    for row in audit(b, market, market.ENTRY_DATE, market.CLOSE_DATE):
        print("  %-9s middle %d, realised %d, gap %+d -> %s"
              % (row["claim"], row["middle_bp"], row["realised_bp"],
                 row["gap_bp"], row["grade"]))
