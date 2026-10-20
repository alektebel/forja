"""Collections Workout From Scratch — stage 9: The recovery flows, discounted.

The recovery flows are the cash the workout collected, discounted back to the
default date using the loan's own effective rate. The collateral rows carry a
haircut from the policy, cash and costs pass at face value, and the factor is
carried forward one period at a time, truncated — never a power.

This stage answers the raw flows, the discounted value at any date, and the
realised LGD against the exposure at default, compared to the best estimate
the credit stages carried.

    RecoveryError          the refusal this stage raises
    RECOVERY_KEYS          the three fields of a recovery row, in order
    flows(book, loan)      -> the recovery cash flows as dated records
    discounted(flows, at, eir_bp) -> M1's stepped present value
    lgd_against(book, loan) -> the realised LGD and the comparison

DESIGN DECISION — why does the stage discount collateral with the policy's
haircut and cash at face value?
Because the policy's own `COLLATERAL_HAIRCUT_BP` is a decision about collateral
value, and cash is already cash. The haircut is applied before the discount,
so a property recovery at €8M with a 20% haircut is €6.4M before discount.

TODO: implement `RecoveryError`, `flows`, `discounted` and `lgd_against` in
this file: the raw flows, the discounted value, and the realised LGD.

    A loan with no recoveries returns empty flows; a loan not defaulted raises.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

RECOVERY_KEYS = ("loan", "date", "amount_cents", "source")


class RecoveryError(ValueError):
    """The refusal this stage raises: a loan that cannot have recoveries.

    It names the offender — the loan that never defaulted, the date that is not
    ISO text — because a recovery the workout never collected must say what it
    was asked for rather than answer a row nobody can defend.
    """


def flows(book, loan):
    raise NotImplementedError("stage 51: implement flows()")
























def discounted(recoveries, at, eir_bp):
    raise NotImplementedError("stage 77: implement discounted()")

































def lgd_against(book, loan):
    raise NotImplementedError("stage 112: implement lgd_against()")








































































def _months_between(start, end):
    """Whole months from start to end, with clamping."""
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * 12 + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months


def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if record.get("loan") == name:
            return record
    raise RecoveryError("the book holds no loan %r" % (name,))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 9 — recovery flows and LGD")
    for loan_name in ("L-07", "L-10"):
        try:
            rec_flows = flows(book, loan_name)
            print("  %-5s -> %d flow(s)" % (loan_name, len(rec_flows)))
            for f in rec_flows:
                print("        %s %s %s" % (f["date"], f["source"], f["amount_cents"]))
            lgd = lgd_against(book, loan_name)
            print("        lgd=%d bp (est=%d bp) beat=%s"
                  % (lgd["realised_lgd_bp"], lgd["best_estimate_lgd_bp"], lgd["beat_estimate"]))
        except RecoveryError as error:
            print("  %-5s refused: %s" % (loan_name, error))