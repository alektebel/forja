"""Credit Origination From Scratch — stage 6: The limit and its structure.

The price is set and the rating is taken; what is still missing is structure.
How much of what the applicant asked for exists once the policy's own caps have
spoken? How much of that does the bank actually commit to, and how much does it
hold back? How long may the money stay out? The limit record answers those
three questions from the facts the world carries and the decisions the policy
has already made — the application's purpose, request and term, the purpose's
own amount cap and tenor cap, and the share of an approval the policy commits —
and it answers them in the exact words a later stage will quote: the payment of
stage 7 is written on the approved tenor, the letter of stage 9 carries the
styled clauses as its own lines.

Nothing here re-prices or re-rates. A cap that cuts is recorded as the clause
text the letter will carry — `"the-amount-cap"` before `"the-tenor-cap"` when
both cut, and never a clause when the cap did not cut, for a request at the cap
exactly is inside it. A verdict that offers nothing is recorded as a structure
of nothing — approved zero, committed zero, tenor zero, styled
`("not-offered",)` — because "no offer" is an answer the record carries, not a
refusal it raises.

    LIMIT_KEYS                    the eight fields of a limit record, in order
    LimitError                    the refusal this stage raises
    limit(cases, identity)        -> LIMIT_KEYS: the approved structure of one
                                     application

DESIGN DECISION — why does the stage read the verdict instead of deciding the decline?
Because the ladder runs one way. The decision stage owns turning the legs into a
verdict, and it does so by reading this stage's structure — so the limit stage
cannot measure affordability, collateral or gates back to produce the decline
without importing a later stage, which the ladder forbids. Whether anything was
offered is a fact of the case the structure is written on, like the purpose and
the term: the estate's own decision record states it, the stage reads it, and it
uses nothing else from that record — the approved amount is computed from the
policy's cap, not echoed from the bank's book.

DESIGN DECISION — why is the styling clause text and not a boolean?
Because the record's styling is what the offer's conditions say, verbatim. A
boolean `capped` would have to be re-decoded by whoever later writes the letter,
and a second decoder is a second chance to disagree with the record. The clauses
are the offer's own vocabulary — `"the-amount-cap"`, `"the-tenor-cap"` — in the
order the caps fired, amount first, tenor second, and `"not-offered"` when there
is no structure at all to style.

DESIGN DECISION — why is the committed share truncated once and the remainder the subtraction?
Because the two amounts must re-add to the approval, to the cent. The committed
share is `approved * COMMITTED_BP // 10000`, truncating, and the uncommitted
share is whatever that leaves — not a second division on its own scale, which
would swallow the rounding cent and leave a bank recording a commitment plus an
uncommitted remainder that sum to one cent less than the limit they claim to
describe. One division, one subtraction, and the sum is the approved again.

DESIGN DECISION — what does the structure of nothing answer, and why zeros?
Because the record's shape does not shrink when the offer does: every
`LIMIT_KEYS` field is filled, and for a decline the honest fill is zero —
nothing approved, so nothing of it committed, nothing uncommitted, and no term
of it approved. The contract pins the zero for the amount and the
`("not-offered",)` clause; the tenor's zero is this stage's own pin, read the
same way: months approved where no money is approved is months approved of
nothing.

TODO: implement `limit` in this file: the approved amount the purpose's cap
allows, the committed share of it and the remainder to the cent, the tenor the
purpose allows, and the clauses the caps left behind.

    A purpose the policy does not name, a verdict outside the policy's own
    three, is refused by name before any number is answered — and the
    application and decision records are read with nothing written back.
"""

import policy

LIMIT_KEYS = ("id", "purpose", "requested_cents", "approved_cents",
              "committed_cents", "uncommitted_cents", "approved_months",
              "styled")

_AMOUNT_CAP_CLAUSE = "the-amount-cap"

_TENOR_CAP_CLAUSE = "the-tenor-cap"

_NOT_OFFERED_CLAUSE = "not-offered"

_DECLINE = "decline"

_LIMIT_ERROR = "limit: "

_BP = 10000


class LimitError(ValueError):
    """The refusal this stage raises: a purpose or a verdict the policy does not name.

    The policy's own vocabularies — `PURPOSES` and `DECISIONS` — are the table
    the limit structure is read out of. A purpose outside them has no cap and
    no tenor to be floored at, and a verdict outside them is neither offered
    nor not-offered; either one is a shape the record cannot carry, and the
    refusal names the offender rather than answering a number nobody can
    defend.
    """


def limit(cases, identity):
    """The approved structure of one application, as the policy caps it.

    The record answers the eight `LIMIT_KEYS` fields in the order the contract
    prints them: the application's own id, purpose and request; the approved
    amount — the requested one floored at the purpose's amount cap, or zero
    where the verdict offers nothing; the committed share of that approval and
    the remainder to the cent; the approved tenor — the requested term floored
    at the purpose's tenor cap, or zero on the same decline; and the styling
    clauses the caps left behind, as the texts the letter will carry.

    A purpose the policy does not name, or a verdict outside the policy's own
    three, is refused by name before any structure is answered. The estate is
    read and never written: the application and decision doors are the two the
    structure is built from.
    """
    raise NotImplementedError("stage 6: implement limit()")
