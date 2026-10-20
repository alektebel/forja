"""Credit Origination From Scratch — stage 9: The offer letter.

A decision is an internal record; the letter is the bank's own promise carried to
the applicant. It carries the terms the bank committed to — approved amount, rate,
and term — the level payment on those exact terms, the policy's clause order, and
the expiry: the calendar date the letter dies, on the calendar's two rules
(ordinary, and month-end).

A decline has no letter. An application the estate does not hold is the estate's
own refusal (its `CaseError`); a declined application is refused by the letter
stage's own `OfferError` naming the id, and reaches no record.

    LETTER_KEYS                   the seven fields of the letter record, in order
    OfferError                    the refusal this stage raises
    letter(cases, id)             -> LETTER_KEYS: the decision's terms in letter form

DESIGN DECISION — why is the letter only for approved and counter, not declined?
Because a decline offers nothing: the bank's own offer record is absent for
declined applications, and the letter is the bank's promise to sell. A refused
application is a "no" not a "not yet" — the stage's own `OfferError` naming the id
carries the refusal, and no offer record is written: the counters other than
`lookups` remain untouched.

DESIGN DECISION — why the level payment on the offer's own terms, not the fit's?
Because the fit (stage 1) prices the requested amount at the proposed rate — what
the applicant walked in with. The letter prices the bank's own approved amount
at the bank's own price over the bank's own term. A stage that reads the fit's
payment instead of walking the offer's own terms carries someone else's words.

DESIGN DECISION — why is the expiry a date, not a count of months?
Because the applicant must know when the offer dies, not how many months after
the decision. The calendar's `add_months` carries the clamping rule (a 31st
clamped to a 28th); the second rule carries a month-end decision to the next
month's end. Two rules, one record: an ordinary decision uses the first, a
month-end decision the second. The bank's own `expires_on` in the decision
record is the answer key these rules produce.

DESIGN DECISION — why does the letter read from the decision record, not
recompute the terms?
Because the decision is the bank's committed act: the approved amount, the
priced rate, and the approved tenor are the decision's own fields. The limit
stage (stage 6) produced the approved structure the decision reads, and the
letter is the next step in the ladder: it quotes the decision, not the
underlying rules. A letter that recomputed the approval would be a second
decision, not a letter.

TODO: implement `OfferError`-refusing `letter` in this file: the decision's terms
in letter form — the approved amount, rate, and term, the level payment on those
terms, the policy's clause order, and the expiry date on the two calendar rules.

    An unknown id is the estate's own `CaseError`; a declined application is
    refused by name with `OfferError`, naming the id, and reaches no record.
"""

import cases
import policy
import dates
import stage_06


LETTER_KEYS = ("id", "clauses", "offered_cents", "rate_bp", "term_months",
               "expiry", "payment_cents")

OFFER_EXPIRY_MONTHS = policy.OFFER_EXPIRY_MONTHS

OFFER_ERROR = "offer: "

_CASES_ERRORS = (cases.CaseError,)


class OfferError(ValueError):
    """The refusal this stage raises when an application carries no offer.

    A declined application is refused by name; an unknown id is the estate's
    own `CaseError`. The letter is the bank's promise: it does not exist for a
    "no", and the refusal names the application.
    """


def letter(cases, id):
    """The decision's terms in letter form.

    Returns a `LETTER_KEYS` record: the application id, the policy's clause order,
    the approved amount from the decision, the priced rate from the decision, the
    approved tenor from the decision, the level payment on those exact terms, and
    the expiry date computed from the decision's `decided_on` on the calendar's
    two rules.

    A declined application is refused by name with `OfferError`, naming the id,
    and reaches no record. An unknown id is the estate's own `CaseError`.
    """
    raise NotImplementedError("stage 9: implement letter()")