"""IRB and Regulatory Capital — stage 5: Downturn LGD, the multiplier and the haircut.

M1's stage 4 turned a loan's recovery flows into the loss the default cost:
haircut first on the collateral, each flow discounted to the default date at
the loan's own contract rate, the recovery capped at the balance the loan
still owed, the complement clamped to the policy's floor and cap. That
arithmetic answered the bank's own books. A capital requirement prices a
*worse* day: the downturn.

The policy orders the steps and the order is the policy's. The best estimate
is computed first — the haircut inside the recovery arithmetic, the discount
inside it, the clamp inside it — and the downturn multiplier is applied to the
**finished** estimate, never to a raw flow: multiplying before the haircut or
before the discount produces a different integer, and the reversed order is a
bug the aged press of a spreadsheet produces more often than any typo. The
multiplied estimate is then held between the policy's own walls: a floor that
refuses to believe an over-collateralised loan loses nothing, and a cap at the
whole cycle.

One class is `refrigerate` — the estate's leasing booking — and the multiplier
does not touch it: its downturn treatment is frozen at the best estimate while
its own calibration is under review. The artifact's rows price every loan the
bank has not yet signalled as defaulted; the recoveries price the ones it has.
A loan with no recoveries behind its default — nothing came back — answers the
cap, and a loan whose grade row the artifact has since re-rated answers at the
version in force.
"""

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

#: The asset classes the multiplier is keyed on, in their own order.
CLASSES = irb.CLASSES

#: The two treatments a booking can enter; only `treat` is multiplied.
TREATMENTS = irb.REFRIGERATE_KINDS

#: The asset class a booking prices to, in their own order.
ASSET_CLASS_OF = irb.ASSET_CLASS_OF

#: The wish the discount steps hold: one basis point per step of a year.
ANNUAL_SCALE = 10000


class DownturnError(PolicyError):
    """The refusal this stage raises: something that cannot be a downturn LGD.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the collateral kind the policy holds no haircut for, the
    date the book does not cover, the asset class the multiplier does not key —
    because a loss the policy cannot stand behind must say what it was asked
    for rather than answer one the arithmetic cannot reproduce.
    """


def _loan_id(loan):
    """The identity a loan arrives under, as the book's records name it."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


def _held(book, loan, at):
    """The loan's own record, refused by name when the book does not hold it."""
    loan_id = _loan_id(loan)
    try:
        return book.loan(loan_id)
    except BookError as refused:
        raise DownturnError("the book does not hold loan %r (%s)"
                            % (loan_id, refused))


def _live(keyed, loan, at):
    """The live loan ids at `at`, or a refusal naming the date or the loan."""
    loan_id = _loan_id(loan)
    try:
        live = keyed.on_book(at)
    except BookError as refused:
        raise DownturnError("the estate at %s is not there to read (%s)" % (at, refused))
    if loan_id not in live:
        raise DownturnError("loan %r is not on the book at %s" % (loan_id, at))
    return loan_id


def _months_between(start, end):
    """The whole months from `start` to `end`, counted with `dates.add_months`."""
    months = 0
    while dates.add_months(start, months + 1) <= end:
        months += 1
    return months


def _discount(amount_cents, periods, period_rate_bp):
    """`amount_cents` discounted `periods` periods, stepped and truncated."""
    factor = ANNUAL_SCALE
    for _ in range(periods):
        factor = factor * ANNUAL_SCALE // (ANNUAL_SCALE + period_rate_bp)
    return amount_cents * factor // ANNUAL_SCALE


def _period_rate_bp(loan):
    """The loan's own contract rate as one period's rate, the world's basis."""
    return rules.period_rate(loan["rate_bp"], rules.DEFAULT_BASIS)


def _haircut(loan):
    """The policy's haircut for the loan's collateral kind, or a refusal naming it."""
    kind = loan.get("collateral_kind")
    if kind not in irb.COLLATERAL_HAIRCUT_BP:
        raise DownturnError("%r is not a collateral kind the policy holds a haircut "
                            "for" % (kind,))
    return irb.COLLATERAL_HAIRCUT_BP[kind]


def _balance_at(book, loan, date):
    """The principal `loan` still owed at `date`: the contract's amortised balance.

    The contractual principal less the principal portions of the instalments
    actually paid by then, less prepayments, floored at zero. Each due's payments
    are summed and applied once against the balance before it: the period's
    interest is `balance * period_rate // 10000`, truncated, and only what the
    payment left over reduces the balance — never more than the balance itself.
    """
    period_rate_bp = _period_rate_bp(loan)
    balance = loan["principal_cents"]
    payments = list(book.payments(loan))
    paid_by_due = {}
    for payment in payments:
        if payment["kind"] == "instalment" and payment["paid_on"] <= date:
            due = payment["due"]
            paid_by_due[due] = paid_by_due.get(due, 0) + payment["amount_cents"]
    for due in sorted(paid_by_due):
        interest = balance * period_rate_bp // ANNUAL_SCALE
        balance -= min(balance, max(0, paid_by_due[due] - interest))
    prepaid = 0
    for payment in payments:
        if payment["kind"] == "prepayment" and payment["paid_on"] <= date:
            prepaid += payment["amount_cents"]
    return max(0, balance - prepaid)


def _recovered(book, loan, default_date):
    """The recovery flows of `loan` discounted to its default date.

    The `collateral` source is a pledged asset's own realisation, so the
    policy's haircut comes off it first; `cash` and `costs` pass at face — a
    `costs` row negative, which reduces what came back. Every flow is then
    discounted from its own date to the default date at the loan's own period
    rate, one truncated step per month.
    """
    haircut_bp = _haircut(loan)
    period_rate_bp = _period_rate_bp(loan)
    recovered = 0
    for row in book.recoveries(loan):
        amount = row["amount_cents"]
        if row["source"] == "collateral":
            amount = amount * (ANNUAL_SCALE - haircut_bp) // ANNUAL_SCALE
        recovered += _discount(amount, _months_between(default_date, row["date"]),
                               period_rate_bp)
    return recovered


def _defaulted_through(book, loan):
    """`(the loan's record, its first signalled default)` — or a refusal.

    The bank's own default rows are the raw facts: the earliest `signalled_on`
    among them is the day the loss was fixed, whether or not the default later
    cured. A loan the book records no default for at all has no recovery
    arithmetic to run and is refused by name.
    """
    loan_id = loan["loan"]
    signalled = [row["signalled_on"] for row in book.defaults()
                 if row["loan"] == loan_id]
    if not signalled:
        raise DownturnError("loan %r has never defaulted, so it has no recovery "
                            "arithmetic to run" % (loan_id,))
    return loan, min(signalled)


def best_estimate_lgd(book, loan, at):
    """The loan's own loss given default, M1's recovery arithmetic recomputed.

    The balance the loan still owed on the day it defaulted — instalments and
    prepayments applied once each, floored at zero — is the denominator, and
    the recovery is each flow haircut on `collateral` first, discounted to the
    default date at the loan's own period rate, capped at the balance. The loss
    is `10000 - recovered * 10000 // balance`, truncated, then clamped to the
    world's own `LGD_FLOOR_BP..LGD_CAP_BP`.

    A loan the book does not hold, one not on the book at `at`, one that has
    never defaulted, a collateral kind the policy holds no haircut for, or a
    date the book does not cover is refused by name.
    """
    loan_id = _live(book, loan, at)
    held = _held(book, loan_id, at)
    held_at, default_date = _defaulted_through(book, held)
    balance = _balance_at(book, held_at, default_date)
    recovered = _recovered(book, held_at, default_date)
    if recovered > balance:
        recovered = balance
    answer = ANNUAL_SCALE - recovered * ANNUAL_SCALE // balance
    return min(max(answer, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)


def downturn_lgd(book, loan, at):
    """The downturn loss: the multiplier on the best estimate, held inside the walls.

    The **order is the policy's**. The best estimate is finished first — the
    haircut inside it, the discount inside it, the clamp inside it — and the
    class's multiplier is applied to the *result*, truncated once, so a reversed
    order (the multiplier on a raw flow, the haircut after the discount) answers
    a different integer and is exactly the kind of bug this stage refuses to
    produce. The multiplied estimate is then held between the policy's own
    walls, the floor refusing to hand a well-collateralised loan a loss of
    nothing and the cap ending it at the whole cycle.

    A `refrigerate` booking is not multiplied at all: its downgrade treatment is
    frozen at the best estimate while its own calibration is under review, and
    the answer is `be_bp` unchanged.

    A loan the book does not hold or is not on at `at` fails the stage by name;
    so does a collateral kind the policy holds no haircut for. A defaulted loan
    with nothing behind it — no recovery row came back — answers the cap, not a
    refusal: losing everything is the arithmetic's own honest answer. A
    **not-defaulted** loan answers at the artifact's row for the grade in
    force, the same rows every stage below prices with.
    """
    loan_id = _live(book, loan, at)
    held = _held(book, loan_id, at)
    defaulted = [row["signalled_on"] for row in book.defaults()
                 if row["loan"] == loan_id and row["signalled_on"] <= at
                 and (row.get("cured_on") is None or row["cured_on"] > at)]
    asset_class, treatment = irb.ASSET_CLASS_OF[held["segment"]]
    if defaulted:
        be_bp = best_estimate_lgd(book, held, at)
        basis = "recoveries"
    else:
        model = _in_force(book, at)
        be_bp = model["lgd_bp"][model["grades"][loan_id]]
        basis = "artifact"
    if treatment == "refrigerate":
        return be_bp
    multiplied = be_bp * irb.DOWNTURN_MULTIPLIER_BP[asset_class] // ANNUAL_SCALE
    return min(max(multiplied, irb.DOWNTURN_FLOOR_BP), irb.DOWNTURN_CAP_BP)


def _in_force(book, at):
    """The artifact in force at `at`, or a refusal naming the date."""
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise DownturnError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise DownturnError("no regulatory artifact is in force at %s, so the best "
                            "estimate has no row to answer" % (at,))
    return model


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    print("loan | at          | basis      | be   | downturn")
    for at in (led.reporting_dates[0], led.reporting_dates[13]):
        for held in led.loans():
            loan_id = held["loan"]
            defaulted = (led.grade(loan_id, at) == "default")
            try:
                down = downturn_lgd(led, loan_id, at)
            except DownturnError as refused:
                print("%-5s | %s | refused: %s" % (loan_id, at, refused))
                continue
            if defaulted:
                be = best_estimate_lgd(led, loan_id, at)
                print("%-5s | %s | %-10s | %d | %+d" % (loan_id, at, "recoveries",
                                                        be, down))
            else:
                print("%-5s | %s | %-10s | ---- | %+d" % (loan_id, at, "artifact",
                                                          down))
