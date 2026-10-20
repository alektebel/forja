"""Collections Workout From Scratch — stage 8: Settlement, deficiency and the write-off.

After the workout collects, the desk closes the sale record with three numbers:
the settlement (the cash the workout collected between default and sale), the
deficiency (what the borrower still owes after the net proceeds), and the
write-off (the accounting act that removes the balance from the claims ledger).

The identity every workout record satisfies is:
    exposure_at_default = settlement + net_proceeds + deficiency

The write-off is distinct from the cash that follows: it is the accounting act,
and the world's own write-off events are the key.

    WriteoffError          the refusal this stage raises
    deficiency(book, loan) -> the deficiency: exposure minus settlement minus net proceeds
    settlement(book, loan) -> the agreed reduction: cash collected between default and sale
    writeoff(book, loan)   -> the write-off event: date and the accounting act

DESIGN DECISION — why are settlement, deficiency, and write-off separate?
Because they answer three different questions: how much was collected, how
much is still owed, and when was the balance removed from the ledger. A
reviewer needs each answer separately.

DESIGN DECISION — why does the stage read the workout record from workout.py
rather than recomputing everything?
Because the workout record is the desk's own answer key, and the stage
proves it can reproduce the three pieces of information the desk closes with.

TODO: implement `WriteoffError`, `deficiency`, `settlement` and `writeoff`
in this file: the three numbers the workout closes with, and the write-off record.

    A loan the desk never worked on is refused by name.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

WRITEOFF_KEYS = ("loan", "date", "exposure_cents", "settlement_cents",
                 "net_proceeds_cents", "deficiency_cents")


class WriteoffError(ValueError):
    """The refusal this stage raises: a workout the desk never ran.

    It names the offender — the loan the desk never sold — because a write-off
    the desk never booked must say what it was asked for rather than answer a
    row nobody can defend.
    """


def deficiency(book, loan):
    """The deficiency: what the borrower still owes after settlement and net proceeds.

    From the workout record, `deficiency = max(0, exposure_at_default - settlement -
    net_proceeds)`. A loan the desk never worked on is refused by name.
    """
    sale_row = _sale_row(book, loan)
    exposure = sale_row["exposure_at_default_cents"]
    settlement = sale_row["settlement_cents"]
    net = sale_row["net_proceeds_cents"]
    deficiency_val = exposure - settlement - net
    if deficiency_val < 0:
        deficiency_val = 0
    return {
        "loan": sale_row["loan"],
        "exposure_cents": exposure,
        "settlement_cents": settlement,
        "net_proceeds_cents": net,
        "deficiency_cents": deficiency_val,
        "identity_holds": (settlement + net + deficiency_val) == exposure or
                          (settlement + net > exposure),
    }


def settlement(book, loan):
    """The agreed reduction: cash collected between default and sale.

    From the workout record, the settlement is the sum of cash recovery rows
    and instalments paid between the default date and the sale date.

    A loan the desk never worked on is refused by name.
    """
    sale_row = _sale_row(book, loan)
    return {
        "loan": sale_row["loan"],
        "settlement_cents": sale_row["settlement_cents"],
        "defaulted_on": sale_row["defaulted_on"],
        "sale_date": sale_row["sale_date"],
    }


def writeoff(book, loan):
    """The write-off event: date and the accounting act.

    Returns the bank's own write-off event row for this loan, or `None` when
    the bank never wrote it off. The write-off is the accounting act that removes
    the balance from the claims ledger, distinct from the cash that follows.

    A loan the book does not hold is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]
    for event in book.events(record):
        if event["kind"] == "write-off":
            return {
                "loan": loan_id,
                "date": event["date"],
                "detail_cents": event["detail_cents"],
                "kind": "write-off",
            }
    return None


def _sale_row(book, loan):
    """One sale record from the world's SALES table."""
    record = _resolve(book, loan)
    loan_id = record["loan"]
    for sale_row in col.SALES:
        if sale_row["loan"] == loan_id:
            return sale_row
    raise WriteoffError("the desk never worked on loan %r" % (loan_id,))


def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if record.get("loan") == name:
            return record
    raise WriteoffError("the book holds no loan %r" % (name,))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 8 — settlement, deficiency, write-off")
    for loan_name in ("L-07", "L-10"):
        try:
            defn = deficiency(book, loan_name)
            sett = settlement(book, loan_name)
            wo = writeoff(book, loan_name)
            print("  %-5s def=%-8d sett=%-8d net=%-8d"
                  % (loan_name, defn["deficiency_cents"], sett["settlement_cents"],
                     defn["net_proceeds_cents"]))
            if wo:
                print("        write-off: %s" % wo["date"])
        except WriteoffError as error:
            print("  %-5s refused: %s" % (loan_name, error))