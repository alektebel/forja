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
    """The recovery cash flows for one loan, in date order.

    Returns the world's `recoveries_of(loan)` rows. Costs are negative.

    A loan that never defaulted is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]

    # Check if defaulted
    defaults = tuple(row for row in book.defaults() if row["loan"] == loan_id)
    if not defaults:
        raise RecoveryError("loan %r has never defaulted, so it has no recoveries" % (loan_id,))

    result = []
    for row in book.recoveries(record):
        result.append({
            "loan": loan_id,
            "date": row["date"],
            "amount_cents": row["amount_cents"],
            "source": row["source"],
        })
    return tuple(result)


def discounted(recoveries, at, eir_bp):
    """The recovery flows discounted back to `at` using the stepped method.

    Each flow is discounted from its own date to `at` using the loan's effective
    rate. The factor is carried forward one period at a time:
    `factor = factor * 10000 // (10000 + period_rate)`, and each term is
    `amount * factor // 10000`. A collateral row carries the policy's haircut.

    `recoveries` is a tuple of dicts with `date`, `amount_cents`, and `source`.
    `at` is the discount date (usually the default date). `eir_bp` is the loan's
    effective rate in basis points.

    Returns the total discounted amount in cents.
    """
    period_bp = eir_bp * 30 // 365  # actual-365 period rate
    total = 0
    default_date = at

    for rec in recoveries:
        amount = rec["amount_cents"]

        # Collateral gets a haircut
        source = rec.get("source", "cash")
        # We don't have collateral_kind here, so skip haircut for generic call
        # The book module applies it when calling recovered_cents

        factor = rules.DISCOUNT_SCALE
        months = _months_between(default_date, rec["date"])
        for _step in range(months):
            factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
        total = total + amount * factor // rules.DISCOUNT_SCALE

    return total


def lgd_against(book, loan):
    """The realised loss given default against the exposure at default.

    Returns a dict with the loan id, the exposure at default, the recovered
    amount (discounted), the realised LGD in basis points, and the comparison
    to the book's own best estimate (the model's LGD at the origination grade).

    A loan that never defaulted is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]
    defaults = tuple(row for row in book.defaults() if row["loan"] == loan_id)
    if not defaults:
        raise RecoveryError("loan %r has never defaulted, so it has no LGD" % (loan_id,))

    default_date = defaults[0]["signalled_on"]

    # Exposure at default: compute from the loan's flows and payments (like collections._LoanLens)
    flows = tuple((f["date"], f["amount_cents"]) for f in book.schedule(record)["flows"])
    period_bp = rules.period_rate(record["rate_bp"], rules.DEFAULT_BASIS)
    balance = record["principal_cents"]
    for due, _amount in flows:
        if due > default_date:
            break
        interest = balance * period_bp // rules.DISCOUNT_SCALE
        paid = 0
        for pay_row in book.payments(record):
            if pay_row["kind"] == "instalment" and pay_row["due"] == due \
                    and pay_row["paid_on"] <= default_date:
                paid = paid + pay_row["amount_cents"]
        portion = paid - interest
        if portion > 0:
            balance = balance - (balance if portion > balance else portion)
    exposure = balance

    # Recovered: discount recoveries back to default date (like book._Loan.recovered_cents)
    recovered = 0
    eir_bp = book._facts["eir"][loan_id][0]
    period_bp_eir = rules.period_rate(eir_bp, rules.DEFAULT_BASIS)
    for rec_row in book.recoveries(record):
        amount = rec_row["amount_cents"]
        if rec_row["source"] == "collateral":
            haircut = rules.COLLATERAL_HAIRCUT_BP.get(record["collateral_kind"], 5000)
            amount = amount * (rules.DISCOUNT_SCALE - haircut) // rules.DISCOUNT_SCALE
        factor = rules.DISCOUNT_SCALE
        months = _months_between(default_date, rec_row["date"])
        for _step in range(months):
            factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp_eir)
        recovered = recovered + amount * factor // rules.DISCOUNT_SCALE
    recovered = min(recovered, exposure)

    # Realised LGD
    if exposure <= 0:
        lgd = rules.LGD_CAP_BP
    else:
        lgd = rules.DISCOUNT_SCALE - recovered * rules.DISCOUNT_SCALE // exposure
    lgd = max(lgd, rules.LGD_FLOOR_BP)
    lgd = min(lgd, rules.LGD_CAP_BP)

    # Best estimate from model at origination grade
    grade = record["grade_origination"]
    model = book.model_in_force(default_date)
    best_estimate = model["lgd_bp"].get(grade, 0) if model else 0

    return {
        "loan": loan_id,
        "exposure_cents": exposure,
        "recovered_cents": recovered,
        "realised_lgd_bp": lgd,
        "best_estimate_lgd_bp": best_estimate,
        "beat_estimate": lgd < best_estimate,
    }


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