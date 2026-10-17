"""Credit Lifecycle From Scratch — stage 5: The drawn balance, the undrawn limit and the exposure at default.

The exposure at default is what the bank is on the hook for when a borrower stops
paying, and for a committed facility that is the balance plus part of what has not been
drawn yet. So the stage reads the drawn amount off the payments, measures the part of
the limit the borrower has used above the schedule's own plan, estimates the segment's
credit conversion factor from the bank's own defaults — one aggregate ratio, not a mean
of per-loan ratios — and answers the exposure as the pinned sum of the two.
"""

import dates
import rules
from book import BookError

EAD_KEYS = ("loan", "date", "drawn_cents", "undrawn_cents", "ccf_bp", "ead_cents")
CCF_FLOOR_BP = rules.CCF_FLOOR_BP
CCF_CAP_BP = rules.CCF_CAP_BP


def _identity(loan):
    """The loan's own id, or the refusal naming what arrived instead of a record."""
    if isinstance(loan, str):
        return loan
    try:
        return loan["loan"]
    except (KeyError, TypeError):
        raise BookError("stage 5: %r is not a loan record" % (loan,))


def _held(book_of, loan):
    """The book's own record for the loan, or the refusal naming it."""
    ident = _identity(loan)
    for record in book_of.loans():
        if _identity(record) == ident:
            return ident, record
    raise BookError("stage 5: the book holds no loan %r" % (ident,))


def _truncate(top, bottom):
    """`top` over `bottom` truncated toward zero: the course's pinned division."""
    negative = (top < 0) != (bottom < 0)
    value = abs(top) // abs(bottom)
    return -value if negative else value


def _clamp(value):
    """`value` held inside the policy's own floor and cap for a conversion factor."""
    if value < CCF_FLOOR_BP:
        return CCF_FLOOR_BP
    if value > CCF_CAP_BP:
        return CCF_CAP_BP
    return value


def _drawn(book_of, loan, date):
    """The principal actually drawn by `date`: instalments paid, less prepayments, at zero.

    Only the loan's own payment rows count, and only those that had arrived by `date`:
    an `instalment` adds to the drawn amount and a `prepayment` takes from it, so a
    borrower who repaid ahead of the schedule has drawn less than the schedule planned.
    A `fee` is not principal and is not counted. The answer never falls below zero.
    """
    drawn = 0
    for payment in book_of.payments(loan):
        if payment["paid_on"] > date:
            continue
        if payment["kind"] == "instalment":
            drawn = drawn + payment["amount_cents"]
        elif payment["kind"] == "prepayment":
            drawn = drawn - payment["amount_cents"]
    return drawn if drawn > 0 else 0


def _planned(book_of, loan, date):
    """The schedule's own plan for the drawn amount at `date`: the instalments due."""
    planned = 0
    for flow in book_of.schedule(loan)["flows"]:
        if flow["date"] <= date:
            planned = planned + flow["amount_cents"]
    return planned


def _undrawn(book_of, loan, date):
    """The limit less the drawn amount above the schedule's plan, and never negative.

    The part of the loan the schedule did not expect to be drawn — because the borrower
    took the schedule's instalments earlier than their due dates — is what eats into a
    committed limit before the remainder of it is converted. Nothing can make this
    number negative: a loan that drew less than its plan leaves the whole limit alone.
    """
    above = _drawn(book_of, loan, date) - _planned(book_of, loan, date)
    if above < 0:
        above = 0
    left = loan["undrawn_limit_cents"] - above
    return left if left > 0 else 0


def _signalled(book_of, ident):
    """The date the book signalled this loan's default, or `None` when it never did."""
    earliest = None
    for record in book_of.defaults():
        if record["loan"] != ident:
            continue
        when = record["signalled_on"]
        if earliest is None or when < earliest:
            earliest = when
    return earliest


def ccf(book, segment):
    """The credit conversion factor the book's own defaults of `segment` exhibit.

    One ratio over the segment's defaulted loans: the drawdowns between origination and
    default are summed, the amounts undrawn at origination are summed, and the division
    happens once and is truncated. The result is clamped to `CCF_FLOOR_BP`..`CCF_CAP_BP`,
    and a segment with no defaults — or with nothing undrawn at origination to convert —
    answers the policy's floor rather than dividing by an empty limit.
    """
    if segment not in rules.SEGMENTS:
        raise BookError("stage 5: %r is not one of the segments %r"
                        % (segment, rules.SEGMENTS))
    drawdown = 0
    undrawn = 0
    for loan in book.loans():
        if loan["segment"] != segment:
            continue
        ident = _identity(loan)
        signalled = _signalled(book, ident)
        if signalled is None:
            continue
        drawdown = drawdown + (_drawn(book, loan, signalled)
                               - _drawn(book, loan, loan["origination"]))
        undrawn = undrawn + _undrawn(book, loan, loan["origination"])
    if undrawn <= 0:
        return CCF_FLOOR_BP
    return _clamp(_truncate(drawdown * 10000, undrawn))


def ead(book, loan, date):
    """The exposure at `date`: what is drawn, plus the undrawn limit converted.

    `drawn_cents` is the schedule's instalments paid up to `date` less any prepayment,
    floored at zero; `undrawn_cents` is the loan's limit less the part of that drawn
    amount above the schedule's own plan, also floored at zero; `ccf_bp` is the loan's
    segment's factor and `ead_cents` is `drawn_cents + undrawn_cents * ccf_bp // 10000`,
    truncated once. Any ISO date is answerable — the origination date has no reporting
    calendar — while a loan the book does not hold raises `BookError` naming it.
    """
    dates.parse(date)
    ident, held = _held(book, loan)
    drawn = _drawn(book, held, date)
    undrawn = _undrawn(book, held, date)
    rate = ccf(book, held["segment"])
    return {"loan": ident, "date": date, "drawn_cents": drawn,
            "undrawn_cents": undrawn, "ccf_bp": rate,
            "ead_cents": drawn + undrawn * rate // 10000}


def ead_at_default(book, loan):
    """The exposure at the loan's default date, as `ead` answers it there.

    A loan the book does not hold raises `BookError` naming it, and so does a loan that
    never defaulted: the exposure at default is a fact about a default, and the stage
    refuses to invent one for a loan whose payments are still arriving.
    """
    ident, held = _held(book, loan)
    signalled = _signalled(book, ident)
    if signalled is None:
        raise BookError("stage 5: the book records no default for loan %r" % (ident,))
    return ead(book, held, signalled)["ead_cents"]
