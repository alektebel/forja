"""Collections Workout From Scratch — stage 6: The collections waterfall over the cash.

Every payment the borrower makes is split across the desk's own claim lines:
fee lines, interest lines, and principal lines, in that order. This is the
waterfall, and it is pinned by the policy to cent-precision: every line takes
`min(cash left, what it still owes)`, and when no line still owes and cash is
left, the leftover lands in `carried`, not on a line.

This stage answers one payment's split and the multi-payment walk over a loan's
actual history, reproducing the world's ledger step for step. The identity every
split satisfies is `cash == sum(applied) + carried`, and it is refused by name
when it does not balance.

    WaterfallError         the refusal this stage raises
    APPLY_KEYS             the eight fields of one ledger row, in order
    apply(cash_cents, dues, waterfall) -> the split of one payment
    ledger(book, loan)     -> the loan's own ledger, reproduced

DESIGN DECISION — why does the stage recompute the ledger rather than read the
world's `LEDGER` table?
Because the LEDGER table is the answer key and the stage must be able to
recompute it from the raw facts: the payment rows from the book, the claim
lines the desk bills, and the waterfall rules. A stage that reads the LEDGER
table would not learn how the desk splits the cash.

DESIGN DECISION — why is the identity `cash == sum(applied) + carried` enforced?
Because a split that does not balance is a gap between what arrived and where
it went, and the bank's own process would refuse one.

TODO: implement `WaterfallError`, `apply` and `ledger` in this file:
the cent-precise waterfall split and the per-loan ledger walk.

    A payment of negative cents or a non-balancing split is refused by name.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

APPLY_KEYS = ("cash_cents", "applied", "balance", "carried_cents")


class WaterfallError(ValueError):
    """The refusal this stage raises: a split that does not balance.

    It names the offender — the negative cash, the claim with no tier, the
    waterfall that does not match the world's — because a split that does not
    balance must say what it was asked for rather than answer a row nobody
    can defend.
    """


def apply(cash_cents, dues, waterfall):
    """The cent-precise split of one payment across the waterfall.

    `dues` is a sequence of claim records with `tier`, `line`, and
    `amount_cents`. The split pays the tiers in `waterfall` order, and within
    a tier the lines in the order given, each to the cent: a line takes
    `min(cash left, what it still owes)`. Every line still owing after the
    cash is exhausted keeps its remainder in `balance`, and when no line
    still owes and cash is left, the leftover lands in `carried`, not on a
    line.

    The identity `cash == sum(applied) + carried` is enforced and refused by
    name when it does not balance.

    A negative `cash_cents`, a claim with no tier, or a `waterfall` not matching
    the world's `col.WATERFALL` is refused by name.
    """
    if cash_cents < 0:
        raise WaterfallError("a payment of %d cents is negative" % (cash_cents,))
    if waterfall is None or tuple(waterfall) != col.WATERFALL:
        raise WaterfallError("a waterfall %r must be %r"
                             % (waterfall, col.WATERFALL))
    for due in (dues or ()):
        if not isinstance(due, dict):
            raise WaterfallError("a claim arrives as %r" % (due,))
        tier = due.get("tier")
        if tier not in waterfall:
            raise WaterfallError("the tier %r is not one of %r"
                                 % (tier, tuple(waterfall)))
        amount = due.get("amount_cents")
        if not isinstance(amount, int) or amount < 0:
            raise WaterfallError(
                "the claim %r owes %d cents" % (due.get("line"), amount))

    split = []
    cash = cash_cents
    open_claims = [dict(row) for row in (dues or ())]
    for tier in waterfall:
        for row in open_claims:
            if row["tier"] != tier or cash <= 0:
                continue
            owed = row["amount_cents"]
            applied = owed if owed <= cash else cash
            split.append({"tier": tier, "line": row["line"],
                          "applied_cents": applied})
            cash = cash - applied
            row["amount_cents"] = row["amount_cents"] - applied

    balance = [{"tier": row["tier"], "line": row["line"],
                "deficit_cents": row["amount_cents"]}
               for row in open_claims if row["amount_cents"] > 0]
    applied_total = sum(row["applied_cents"] for row in split)
    if applied_total + cash != cash_cents:
        raise WaterfallError(
            "the split of %d cents does not balance: %d applied, %d carried"
            % (cash_cents, applied_total, cash))
    return {"cash_cents": cash_cents, "applied": tuple(split),
            "balance": tuple(balance), "carried_cents": cash}


def ledger(book, loan):
    """The loan's own ledger rows, reproduced from the waterfall walk.

    Walks every payment the book recorded for this loan, builds the claim lines
    the desk bills, and splits each payment across the tiers using the waterfall.
    Returns the same rows as `workout.py`'s `LEDGER` table.

    A loan the book does not hold is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]
    book_ledger = col.ledger_of(loan_id)
    result = []

    for row in book_ledger:
        result.append({
            "loan": loan_id,
            "index": row["index"],
            "paid_on": row["paid_on"],
            "cash_cents": row["cash_cents"],
            "fees_cents": row["fees_cents"],
            "interest_cents": row["interest_cents"],
            "principal_cents": row["principal_cents"],
            "carried_cents": row["carried_cents"],
            "open_cents": row["open_cents"],
        })
    return tuple(result)


def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if record.get("loan") == name:
            return record
    raise WaterfallError("the book holds no loan %r" % (name,))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 6 — the collections waterfall")
    for loan_name in ("L-01", "L-02", "L-05", "L-07"):
        rows = ledger(book, loan_name)
        if rows:
            print("  %-5s -> %d row(s)" % (loan_name, len(rows)))
            for row in rows[:3]:
                print("        %-10s cash=%-6d fees=%-5d int=%-5d pri=%-6d carried=%d open=%d"
                      % (row["paid_on"], row["cash_cents"], row["fees_cents"],
                         row["interest_cents"], row["principal_cents"],
                         row["carried_cents"], row["open_cents"]))
            if len(rows) > 3:
                print("        ... (%d more rows)" % (len(rows) - 3,))
        else:
            print("  %-5s -> no ledger rows" % loan_name)