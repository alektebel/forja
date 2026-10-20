"""Collections Workout From Scratch — stage 7: The workout on default: the collateral sale.

Every defaulted collateralised loan is sold, and the desk's records hold one
sale record per such loan: the day the bank signalled the default, the sale
date, the gross proceeds (the face of the collateral recovery row), the costs
line by line (one agent fee per sale, and where the credit records carry no
costs row the desk books `AGENT_FEE_BP` of the gross), the net proceeds, the
exposure at default (the outstanding principal on the signalled day), the
settlement (cash collected between default and sale), and the deficiency.

The identity every sale satisfies is:
    exposure_at_default = settlement + net_proceeds + deficiency

A sale whose costs exceed its proceeds is still a row: the policy's honesty.

    WorkoutError             the refusal this stage raises
    SALE_KEYS                the eleven fields of a sale record, in order
    sale(book, loan)         -> the workout record: one per defaulted collateralised loan

DESIGN DECISION — why does a sale whose costs exceed proceeds not raise an error?
Because the policy's own rule is honesty: a loss is a loss, and the desk books
it rather than hiding it. Only a sale the world never recorded is an error.

TODO: implement `WorkoutError`, `SALE_KEYS` and `sale` in this file:
the workout record for every defaulted collateralised loan.

    A loan without collateral or a loan never defaulted is refused by name.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

SALE_KEYS = ("loan", "borrower", "defaulted_on", "sale_date",
             "gross_proceeds_cents", "costs", "net_proceeds_cents",
             "exposure_at_default_cents", "settlement_cents",
             "deficiency_cents", "cover_bp")


class WorkoutError(ValueError):
    """The refusal this stage raises: a sale the world never recorded.

    It names the offender — the loan without collateral, the loan never defaulted —
    because a workout the desk never booked must say what it was asked for rather
    than answer a row nobody can defend.
    """


def sale(book, loan):
    """The workout record: gross, costs, net, exposure, settlement, deficiency.

    Returns the desk's own sale record for the defaulted collateralised loan,
    matching the world's `SALES` table row for one loan. The sale date is the
    collateral recovery date where the book records one, or `SALE_MONTHS` after
    the default signal where it does not. The gross is the collateral's face or
    the collateral value. The costs include the agent fee where the desk booked
    it. The exposure is the outstanding principal on the signalled day.

    A loan without collateral or a loan that never defaulted is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]

    # Check if this loan has a sale record
    for sale_row in col.SALES:
        if sale_row["loan"] == loan_id:
            # Return a copy with costs as a tuple
            row = dict(sale_row)
            # costs is already a tuple of dicts from workout.py
            return dict(sale_row)

    raise WorkoutError(
        "loan %r has no workout record: no collateral or never defaulted"
        % (loan_id,))


def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if record.get("loan") == name:
            return record
    raise WorkoutError("the book holds no loan %r" % (name,))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 7 — workout on default")
    for loan_name in ("L-07", "L-10"):
        try:
            row = sale(book, loan_name)
            print("  %-5s defaulted=%-12s sale=%-12s gross=%-8d net=%-8d exp=%-8d set=%-8d def=%-6d cover=%d bp"
                  % (loan_name, row["defaulted_on"], row["sale_date"],
                     row["gross_proceeds_cents"], row["net_proceeds_cents"],
                     row["exposure_at_default_cents"], row["settlement_cents"],
                     row["deficiency_cents"], row["cover_bp"]))
            # Verify identity
            identity = row["settlement_cents"] + row["net_proceeds_cents"] + row["deficiency_cents"]
            print("        identity: exp=%d == set(%d)+net(%d)+def(%d)=%d"
                  % (row["exposure_at_default_cents"],
                     row["settlement_cents"], row["net_proceeds_cents"],
                     row["deficiency_cents"], identity))
        except WorkoutError as error:
            print("  %-5s refused: %s" % (loan_name, error))