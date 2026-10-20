"""Credit Origination From Scratch — stage 10: The booked facility: the bank's ledger, reproduced.

The facility is the loan the contract books — the record M1 measures a life
against — computed from the decision's own terms: the approved amount, the
priced rate, the approved tenor, the first due date on the calendar, and the
level payment the bank searched for in stage 1. The stage reproduces every row
of the amortisation walk from those terms: the bank's own rows, and M1's
answer key. A decline is never booked and is refused by name before the
offer-level keys are read; an unknown id is the estate's own CaseError.

FACILITY_KEYS  the eight fields of a facility record, in order
BookingError   the refusal this stage raises for a decline
book(cases, id)  -> FACILITY_KEYS: book the facility at the offer's terms
booked_rows(cases, id)  -> tuple: the rows from the booked facility

DESIGN DECISION — why does the level payment come from stage 1?
Because the amortisation is a search, not a formula: the balance is truncated
to the cent at every step, so the instalment that clears the loan is the
smallest integer one and no closed form can know it. The same walk the bank
booked its own facilities with — cases.py's _booked — must be reproduced,
and stage 1's payment is that search, already proven and already correct.

DESIGN DECISION — why is first due based on the decision date, not today?
Because the calendar is deterministic and the bank's ledger is its own.
dates.month_end(dates.add_months(decided_on, 1)) is the month end after
the decision — the bank's own rule, byte-identical to the estate — and a
stage that reaches for a machine clock cannot reproduce the ledger.

DESIGN DECISION — why does a decline refuse before reading the offer?
Because the bank's facility record does not exist for a declined application.
A refusal that silently produces no record is the mistake catalogue's
"decline's booking refused silently" — the stage must raise BookingError
naming the id so the check can prove the counters are still.

DESIGN DECISION — why does booked_rows just return rows from book?
Because it is a convenience accessor that gives the caller the rows without
building the whole facility record. Delegation to book keeps the data
in sync and avoids two walks of the same terms.

TODO: implement book and booked_rows in this file: the booking at the
offer's terms, the amortisation rows, and the decline refusal.
"""

import cases as _estate
import dates
import stage_01  # payment search

FACILITY_KEYS = ("id", "booked_cents", "rate_bp", "term_months",
                 "first_due", "basis", "level_payment_cents", "rows")

_BP = 10000
_DPP = 30
_DPY = 360
_BASIS = "thirty-360"


class BookingError(ValueError):
    """The refusal this stage raises: a booking attempt on a declined application.

    The stage names the id in the message so the check can prove a declined
    application's counters remain unchanged.
    """


def _build_rows(principal, rate_bp, term_months, first_due, level_payment):
    """Build the amortisation rows from the booked terms.

    Interest is charged on the opening balance, truncated to the cent.
    The last row is the exact clear: balance + interest.
    """
    period_bp = rate_bp * _DPP // _DPY
    balance = principal
    rows = []
    for i in range(term_months):
        interest = balance * period_bp // _BP
        if i < term_months - 1:
            amount = level_payment
        else:
            amount = balance + interest
        rows.append((dates.add_months(first_due, i), amount))
        balance -= amount - interest
    return tuple(rows)


def book(cases, id):
    """Book the facility at the offer's terms.

    Reads the decision, checks for a decline, reads the offer and the limit
    to determine the terms, computes the level payment via stage 1's search,
    builds the amortisation rows, and returns a FACILITY_KEYS record.

    An unknown id is the estate's own CaseError. A declined application raises
    BookingError naming the id before any offer-level key is read.
    """
    # Check for decline BEFORE reading the offer: a declined application
    # has no offer record, so the estate raises CaseError — catch it and
    # raise BookingError naming the id. An unknown id is the estate's own
    # CaseError, which is re-raised as-is. The counters other than lookups
    # must stillness: applications, decisions, offers, facilities untouched.
    try:
        cases.offer(id)
    except _estate.CaseError as e:
        msg = str(e)
        if "not an application this book holds" in msg:
            raise  # unknown id: re-raise the estate's own CaseError
        raise BookingError("%s is declined: nothing books" % (id,))
    # Now read the decision and the limit for the booking terms.
    import stage_06
    limit = stage_06.limit(cases, id)
    decision = cases.decision(id)
    term_months = limit["approved_months"]
    booked_cents = decision["approved_cents"]
    rate_bp = decision["price_bp"]
    decided_on = decision["decided_on"]
    first_due = dates.month_end(dates.add_months(decided_on, 1))
    level_payment_cents = stage_01.payment(cases, booked_cents, rate_bp,
                                          term_months)
    rows = _build_rows(booked_cents, rate_bp, term_months, first_due,
                       level_payment_cents)
    return {"id": id, "booked_cents": booked_cents, "rate_bp": rate_bp,
            "term_months": term_months, "first_due": first_due,
            "basis": _BASIS, "level_payment_cents": level_payment_cents,
            "rows": rows}


def booked_rows(cases, id):
    """The amortisation rows of the booked facility.

    Returns the rows tuple from the booked facility as a sequence of
    ("date", "amount_cents") pairs. Delegates to book.

    A declined id or an unknown id propagates the same error as book.
    """
    return book(cases, id)["rows"]