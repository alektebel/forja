"""IRB and Regulatory Capital — stage 6: BE-EAD and its CCFs.

A capital requirement prices an *exposure*, and the exposure of a loan that has
not been drawn down entirely is bigger than its balance: the bank is committed
to lending further, and the policy converts that commitment at a product's own
credit conversion factor. The best-estimate exposure at `at` is
`drawn + undrawn * ccf // 10000` — the drawn cash the loan has received so far
(instalments paid less prepayments, floored at zero, exactly the drawn-cash
arithmetic the book records), the undrawn limit the loan still carries after
the plan the contract schedules is subtracted, and the product row of
`irb.CCF_BY_PRODUCT_BP` converting the undrawn part, truncated once.

The other half of the stage is the estimator — what the bank's *own defaults*
have already taught it about those factors. For each product the bank has
defaults recorded in, the CCF the bank earns is the drawdowns the book records
at the default dates over the open commitments that were there at origination:
`Σ drawn(default) // Σ open(origination)`, truncated, and clamped to the
policy's own floor and cap. A product the bank has never defaulted on, and a
product whose defaults all sat on limits of zero, are outside the estimator's
support — refused by name, because a factor with no exposure behind it is not
an estimated factor but a guess.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import dates
import irb
from book import BookError
from irb import PolicyError

#: The products the CCF table is keyed on, in the policy's own order.
PRODUCTS = tuple(sorted(irb.CCF_BY_PRODUCT_BP, key=irb.CCF_BY_PRODUCT_BP.get))

#: The drawn/undrawn conversion factors, as the policy carries them.
CCF_BY_PRODUCT_BP = irb.CCF_BY_PRODUCT_BP

#: The clamps the bank's own estimate of a factor is held between.
CCF_FLOOR_BP = irb.CCF_FLOOR_BP

CCF_CAP_BP = irb.CCF_CAP_BP

#: The scale every factor and basis point measure is held at.
BP_SCALE = 10000


class EadError(PolicyError):
    """The refusal this stage raises: something that cannot be an exposure.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the product outside the policy's table, the segment the
    estimator has no default in, the segment whose defaults sat on zero open
    commitments — because an exposure the arithmetic cannot stand behind must
    say what it was asked for rather than answer one divided by nothing.
    """


def _loan_id(loan):
    """The identity a loan arrives under, as the book's records name it."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


def _live(keyed, loan, at):
    """The loan's record, refused by name when it is not live on the book."""
    loan_id = _loan_id(loan)
    try:
        live = keyed.on_book(at)
    except BookError as refused:
        raise EadError("the estate at %s is not there to read (%s)" % (at, refused))
    if loan_id not in live:
        raise EadError("loan %r is not on the book at %s" % (loan_id, at))
    try:
        return keyed.loan(loan_id), loan_id
    except BookError as refused:
        raise EadError("the book does not hold loan %r (%s)" % (loan_id, refused))


def drawn_cents(book, loan, at):
    """The cash `loan` has drawn by `at`: instalments paid, less prepayments.

    The world's own drawn-cash arithmetic — every instalment the borrower
    actually paid by `at` counted, every prepayment taken back off, then
    floored at zero. The scheduled plan is independent of this: a borrower that
    paid ahead of the plan is drawn for what it paid, not for what the plan
    said it should have paid by now.
    """
    drawn = 0
    for payment in book.payments(loan):
        if payment["paid_on"] > at:
            continue
        if payment["kind"] == "instalment":
            drawn += payment["amount_cents"]
        elif payment["kind"] == "prepayment":
            drawn -= payment["amount_cents"]
    return max(0, drawn)


def plan_cents(book, loan, at):
    """What the contract says should have been paid by `at`: the schedule's own sum."""
    total = 0
    for flow in book.schedule(loan)["flows"]:
        if flow["date"] <= at:
            total += flow["amount_cents"]
    return total


def undrawn_cents(book, loan, at):
    """The limit `loan` still carries at `at`, after what paying ahead consumed.

    The undrawn limit less what the borrower has drawn *above* the plan — the
    part of the limit paying ahead has already eaten is not available to draw
    again — floored at zero, so a limit that has been fully consumable is
    answered as nothing rather than as a negative commitment.
    """
    drawn = drawn_cents(book, loan, at)
    above_plan = max(0, drawn - plan_cents(book, loan, at))
    return max(0, loan["undrawn_limit_cents"] - above_plan)


def be_ead(book, loan, at):
    """The best-estimate exposure of `loan` at `at`, in cents, at its product row.

    `drawn + undrawn * ccf // 10000` — the drawn cash, the undrawn limit after
    paying ahead is accounted for, and the product's own conversion factor
    applied to the undrawn part with one truncated division. The limit's own
    size sets the exposure far more than the factor does: the factor converts a
    commitment, and the answer commits to no more of one than the limit holds.

    A loan the book does not hold or is not on at `at`, or a product whose row
    the policy does not carry, is refused by name.
    """
    held, loan_id = _live(book, loan, at)
    ccf_bp = CCF_BY_PRODUCT_BP.get(held["segment"])
    if ccf_bp is None:
        raise EadError("%r is not a product the policy holds a CCF row for"
                       % (held["segment"],))
    drawn = drawn_cents(book, held, at)
    undrawn = undrawn_cents(book, held, at)
    return drawn + undrawn * ccf_bp // BP_SCALE


def _first_default(book, loan_id):
    """The day the bank first signalled the loan default, or `None`."""
    signalled = [row["signalled_on"] for row in book.defaults()
                 if row["loan"] == loan_id]
    return min(signalled) if signalled else None


def _drawn_at(book, loan, date):
    """The drawn cash of `loan` at `date`, by the stage's own arithmetic."""
    drawn = 0
    for payment in book.payments(loan):
        if payment["paid_on"] > date:
            continue
        if payment["kind"] == "instalment":
            drawn += payment["amount_cents"]
        elif payment["kind"] == "prepayment":
            drawn -= payment["amount_cents"]
    return max(0, drawn)


def ccf(book, segment):
    """The conversion factor the bank's own defaults of `segment` estimate, in bp.

    Over every loan the book signalled as default in `segment` — a default that
    has since cured is still one the bank earned a factor from — at its first
    signalled day, the drawdowns the book records between origination and that
    day are the numerator, each defaulted loan taken at
    `max(0, drawn(default) - drawn(origination))`, floored. The open
    commitments that were there at origination are the denominator, floored the
    same way. The quotient is `drawn * 10000 // open`, truncated once, then
    clamped to the policy's own floor and cap. The weight is the limit, not the
    count: a product whose one defaulted borrower had a big limit out-weighs
    one with a small limit.

    A segment outside the policy's products, a segment the bank has never
    defaulted on, and a segment whose defaults all sat on limits of zero are
    refused by name — the estimator answers only inside its support, and a
    factor with no open exposure behind it is a guess, not an estimate.
    """
    if segment not in CCF_BY_PRODUCT_BP:
        raise EadError("%r is not a product the policy holds a CCF row for"
                       % (segment,))
    by_loan = {}
    for row in book.defaults():
        if row["loan"] not in by_loan or row["signalled_on"] < by_loan[row["loan"]]:
            by_loan[row["loan"]] = row["signalled_on"]
    in_segment = {}
    for loan_id, default_date in by_loan.items():
        held = book.loan(loan_id)
        if held["segment"] == segment:
            in_segment[loan_id] = default_date
    if not in_segment:
        raise EadError("the estimator cannot answer %r: the book holds no default "
                       "recorded on %r, so the bank has earned no factor for it"
                       % (segment, segment))
    drawn_total = 0
    open_total = 0
    for loan_id, default_date in sorted(in_segment.items()):
        held = book.loan(loan_id)
        origination = held["origination"]
        drawn_total += max(0, _drawn_at(book, held, default_date)
                           - _drawn_at(book, held, origination))
        orig_drawn = _drawn_at(book, held, origination)
        orig_plan = 0
        for flow in book.schedule(held)["flows"]:
            if flow["date"] <= origination:
                orig_plan += flow["amount_cents"]
        above = max(0, orig_drawn - orig_plan)
        open_total += max(0, held["undrawn_limit_cents"] - above)
    if open_total == 0:
        raise EadError("the estimator cannot answer %r: every default it sat on "
                       "carried a limit of zero, so there is no open exposure to "
                       "divide by" % (segment,))
    estimated = drawn_total * BP_SCALE // open_total
    return min(max(estimated, CCF_FLOOR_BP), CCF_CAP_BP)


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    print("loan | at          | drawn      | undrawn    | ccf  | be_ead")
    for at in (led.reporting_dates[0], led.reporting_dates[13]):
        for held in led.loans():
            loan_id = held["loan"]
            try:
                print("%-5s | %s | %8d | %8d | %4d | %d"
                      % (loan_id, at, drawn_cents(led, held, at),
                         undrawn_cents(led, held, at),
                         CCF_BY_PRODUCT_BP[held["segment"]],
                         be_ead(led, loan_id, at)))
            except EadError as refused:
                print("%-5s | %s | refused: %s" % (loan_id, at, refused))
    print()
    print("segment      | policy row | estimated")
    for segment in sorted(CCF_BY_PRODUCT_BP):
        try:
            print("%-12s | %d | %d" % (segment, CCF_BY_PRODUCT_BP[segment],
                                       ccf(led, segment)))
        except EadError as refused:
            print("%-12s | %d | refused: %s"
                  % (segment, CCF_BY_PRODUCT_BP[segment], refused))
