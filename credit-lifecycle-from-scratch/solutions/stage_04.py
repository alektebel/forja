"""Credit Lifecycle From Scratch — stage 4: The recovery cash flows and the loss given default.

A default is not the end of a loan's arithmetic; it is where the arithmetic gets
harder. The collateral is realised, the collectors are paid, and what comes back
arrives over months or years after the day the loan stopped performing. This stage
turns those observed flows into the two integers a provision is then built from: what
was recovered, and what was lost.

Each recovery flow is discounted to the loan's default date at the loan's own effective
rate — stage 1's rate, stepped one period at a time with stage 1's own truncation — so a
euro recovered two years after the default is worth fewer cents than the same euro
recovered next month. The loss given default is the complement of that recovery against
the balance the loan still owed on the day it defaulted, clamped to the policy's floor
and cap, with a recovery above the balance capped at the balance and reported as capped.
"""

import dates
import rules
import stage_01
from book import BookError

RECOVERY_KEYS = ("loan", "flows", "recovered_cents", "undiscounted_cents")

LGD_KEYS = ("loan", "balance_cents", "recovered_cents", "lgd_bp", "workout_months",
            "haircut_bp")

LGD_FLOOR_BP = rules.LGD_FLOOR_BP

LGD_CAP_BP = rules.LGD_CAP_BP

COLLATERAL_HAIRCUT_BP = rules.COLLATERAL_HAIRCUT_BP


def _held(book, loan):
    """The book's own record for `loan`, or a refusal that names what arrived."""
    if not isinstance(loan, dict) or "loan" not in loan:
        raise BookError("stage 4: %r is not a loan the book holds" % (loan,))
    return book.loan(loan["loan"])


def _defaulted_on(book, loan):
    """`(the book's record, the date of the loan's first signalled default)`.

    A default that has since cured is still a default: the loss was fixed at the date
    it was signalled and the cure changes the loan's future, not that loss. A loan the
    book recorded more than one default for answers at its first, the same date the
    bank's own record uses; only a loan the book records no default at all for has no
    loss given default, and that one is refused by name.
    """
    held = _held(book, loan)
    signalled = [record["signalled_on"] for record in book.defaults()
                 if record["loan"] == held["loan"]]
    if not signalled:
        raise BookError("stage 4: %r never defaulted, so it has no loss given default"
                        % (held["loan"],))
    return held, min(signalled)


def _months_between(start, end):
    """The whole months from `start` to `end`, counted with `dates.add_months`.

    The number of monthly steps `k >= 1` whose calendar date `add_months(start, k)`
    still falls on or before `end`, so a flow on the default date is zero months out
    and a flow a month later is one — never a local count of 30-day steps, which would
    drift from the calendar the world clamps.
    """
    months = 0
    while dates.add_months(start, months + 1) <= end:
        months += 1
    return months


def _discount(amount_cents, periods, period_rate_bp):
    """`amount_cents` discounted `periods` periods, stage 1's stepwise truncation."""
    factor = 10000
    for _ in range(periods):
        factor = factor * 10000 // (10000 + period_rate_bp)
    return amount_cents * factor // 10000


def _period_rate(book, loan):
    """The loan's own effective rate as one period's rate, in basis points."""
    effective = stage_01.effective_rate(book, loan)
    return rules.period_rate(effective["eir_bp"], effective["basis"])


def _haircut(loan):
    """The policy's haircut for the loan's collateral kind, or a refusal naming it."""
    kind = loan.get("collateral_kind")
    if kind not in COLLATERAL_HAIRCUT_BP:
        raise BookError("stage 4: %r is not a collateral kind the policy holds"
                        % (kind,))
    return COLLATERAL_HAIRCUT_BP[kind]


def _flow_cents(row, haircut_bp, default_date, period_rate_bp):
    """One recovery row's cents at the default date.

    The `collateral` source is a pledged asset's own realisation, so the policy's
    haircut comes off it first; `cash` and `costs` pass at face. Every flow is then
    discounted from its own date to the default date, so collateral collected later is
    worth less than collateral collected sooner.
    """
    amount = row["amount_cents"]
    if row["source"] == "collateral":
        amount = amount * (10000 - haircut_bp) // 10000
    return _discount(amount, _months_between(default_date, row["date"]),
                     period_rate_bp)


def _balance_at(book, loan, date):
    """The principal `loan` still owed at `date`: the schedule's amortised balance.

    The contractual principal less the principal portions of the instalments actually
    paid by then, less prepayments, floored at zero. Each due's payments are summed and
    applied once against the balance before it: the period's interest is
    `balance * period_rate // 10000`, truncated, and only what the payment left over
    reduces the balance — never more than the balance itself — so an underpayment does
    not repay principal it never covered and an overpayment does not overpay it.
    """
    period_rate_bp = rules.period_rate(loan["rate_bp"], rules.DEFAULT_BASIS)
    balance = loan["principal_cents"]
    payments = list(book.payments(loan))
    paid_by_due = {}
    for payment in payments:
        if payment["kind"] == "instalment" and payment["paid_on"] <= date:
            due = payment["due"]
            paid_by_due[due] = paid_by_due.get(due, 0) + payment["amount_cents"]
    for due in sorted(paid_by_due):
        interest = balance * period_rate_bp // 10000
        balance -= min(balance, max(0, paid_by_due[due] - interest))
    prepaid = 0
    for payment in payments:
        if payment["kind"] == "prepayment" and payment["paid_on"] <= date:
            prepaid += payment["amount_cents"]
    return max(0, balance - prepaid)


def recoveries(book, loan):
    """The loan's recovery flows, discounted to the day the loan defaulted.

    `flows` is the book's own recovery rows in their own order, `undiscounted_cents`
    their plain sum, and `recovered_cents` each flow discounted to the loan's default
    date at the loan's own effective rate: the `collateral` source net of the policy's
    haircut, a `costs` source negative, and every flow discounted from its own date so
    collateral collected later is worth less than collateral collected sooner. A loan
    the book does not hold, and a loan that never defaulted, raise `BookError` naming
    it.
    """
    held, default_date = _defaulted_on(book, loan)
    rows = tuple(book.recoveries(held))
    undiscounted = 0
    for row in rows:
        undiscounted += row["amount_cents"]
    if not rows:
        return {"loan": held["loan"], "flows": rows, "recovered_cents": 0,
                "undiscounted_cents": 0}
    haircut_bp = _haircut(held)
    period_rate_bp = _period_rate(book, held)
    recovered = 0
    for row in rows:
        recovered += _flow_cents(row, haircut_bp, default_date, period_rate_bp)
    return {"loan": held["loan"], "flows": rows, "recovered_cents": recovered,
            "undiscounted_cents": undiscounted}


def lgd(book, loan):
    """The loss one default cost: `10000` less the recovery over the balance it owed.

    `balance_cents` is the loan's outstanding principal at its default date — the
    principal less the instalments and prepayments it had repaid by then, floored at
    zero — and `recovered_cents` is `recoveries`'s discounted total capped at that
    balance, so a recovery above the balance is capped and reported as capped.
    `lgd_bp` is `10000 - recovered_cents * 10000 // balance_cents`, truncated, then
    clamped to `LGD_FLOOR_BP`..`LGD_CAP_BP`; `workout_months` is the months from the
    default date to the last recovery flow, by `dates.add_months` arithmetic, and
    `haircut_bp` is the policy's haircut for the loan's collateral kind. A loan the
    book does not hold, a loan that never defaulted, a collateral kind the policy does
    not hold or a balance that is not positive raise `BookError` naming it.
    """
    held, default_date = _defaulted_on(book, loan)
    haircut_bp = _haircut(held)
    balance = _balance_at(book, held, default_date)
    if balance <= 0:
        raise BookError("stage 4: %r owed nothing at its default, so it has no loss"
                        % (held["loan"],))
    recovered = recoveries(book, held)["recovered_cents"]
    if recovered > balance:
        recovered = balance
    lgd_bp = 10000 - recovered * 10000 // balance
    if lgd_bp < LGD_FLOOR_BP:
        lgd_bp = LGD_FLOOR_BP
    elif lgd_bp > LGD_CAP_BP:
        lgd_bp = LGD_CAP_BP
    rows = tuple(book.recoveries(held))
    if rows:
        workout_months = _months_between(default_date,
                                         max(row["date"] for row in rows))
    else:
        workout_months = 0
    return {"loan": held["loan"], "balance_cents": balance,
            "recovered_cents": recovered, "lgd_bp": lgd_bp,
            "workout_months": workout_months, "haircut_bp": haircut_bp}


def lgd_by_segment(book, segment):
    """The exposure-weighted loss the book's own defaults of `segment` have realised.

    The weight is the balance at default and not the loan count: `Σ(lgd_bp *
    balance_cents) // Σ(balance_cents)`, truncated, over the segment's defaulted loans.
    A segment with no defaults answers `None`, and a segment the policy does not hold
    raises `BookError` naming it.
    """
    if segment not in rules.SEGMENTS:
        raise BookError("stage 4: %r is not one of the segments %r"
                        % (segment, rules.SEGMENTS))
    in_default = set(record["loan"] for record in book.defaults()
                     if record.get("cured_on") is None)
    top = 0
    bottom = 0
    for loan in book.loans():
        if loan["segment"] != segment or loan["loan"] not in in_default:
            continue
        record = lgd(book, loan)
        top += record["lgd_bp"] * record["balance_cents"]
        bottom += record["balance_cents"]
    if bottom == 0:
        return None
    return top // bottom
