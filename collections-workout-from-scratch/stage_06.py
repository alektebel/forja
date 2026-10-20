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
    raise NotImplementedError("stage 58: implement apply()")


























































def ledger(book, loan):
    raise NotImplementedError("stage 118: implement ledger()")



























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