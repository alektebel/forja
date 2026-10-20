"""Credit Origination From Scratch — stage 8: The decision and who owns it.

Everything the course has measured so far converges on one record. Does the
payment fit, what did the scorecard answer, does the collateral carry the ask,
who the applicant is to the bank, what the price, the structure and the
promises say — and the decision is those legs' verdict: every leg the decision
cites is a record a stage already answered, the fit and the collateral and the
rating in the policy's own order, and a leg that fires is why the verdict is
not an approval. On top the conditions: the clauses the cap left, the
promises the projections breached — the things the letter carries, not things
that change the verdict. And under it the role: the amount that clears the
committee's threshold is owned by the committee, and everything else — a thin
approval and every decline — is filed by the underwriter.

The stage derives every word and every number it publishes. The refusal reads
no shortcut: an approval cites the five legs in `REASONS` order because all
five cleared, a decline cites only the legs that fired and nothing more, and a
counter is a structure the caps styled, not the applicant's own words. The one
number the decision record does not rebuild is the bank's own priced rate —
the number the bank set, carried from its own record, explained by stage 5 and
never copied by the letter — and a record whose verdict disagrees with the
legs is refused, not answered, because a decision the legs cannot reach is a
decision nobody can audit.

    DECIDE_KEYS                    the seven fields of a decision record, in order
    STAGE_ERROR                    the prefix every refusal of this stage opens with
    DecideError                    the refusal this stage raises
    decide(cases, identity)        -> DECIDE_KEYS: the legs' verdict, priced and owned
    role(approved_cents)           -> str: who owns the number

DESIGN DECISION — why is the verdict the legs' verdict rather than the record's?
Because a decision a learner cannot re-derive from the legs is a rumour. Each
leg owns one test the earlier stages already answered: the fit's two halves
(stage 1), the collateral's cap and coverage (stage 3), the rating's grade and
its gates (stage 4) — and a leg that fires is why nothing is on offer. The
scorecard, the limit and the covenants never fire: the band table answers
every total, a styled structure is a *condition* the letter carries, and a
breached promise is a promise, not a decline — the bank's own records name
exactly the legs the stage derives, and their refusal to name the rest is the
rule the data holds up.

DESIGN DECISION — why is the bank's own record read at all, and when does it refuse?
Because the record is the estate's own truth about the act, not the stage's
answer: the stage derives the verdict from the legs and answers the record's
word only after proving the two agree, and a record the legs cannot reach — a
verdict the policy does not decide, an offer the legs decline, a decline the
legs cleared, a counter nothing styled — is refused by name. It is the one
number the record owns that the legs do not rebuild: the priced rate. The
price's legs (stage 5) re-add it wherever the policy leaves nothing behind,
and where the bank's own book sits a hair above its build the gap is the
residual — stage 5's data and the record's, not the decision's arithmetic.

DESIGN DECISION — why is the role the approved amount's role, not the request's?
Because the committee owns the number that exists, not the number that was
asked for. `COMMITTEE_CENTS` is the policy's own line: an approval at or
above it is the committee's, and everything under it is the underwriter's —
including every decline, whose approved amount is zero whatever was asked.
A request of five million cents exactly for a two-million cap is still an
underwriter's file, and the estate's own roles say so.

DESIGN DECISION — why is a styled structure a condition and a breach a
condition, while the verdict stays?
Because the conditions say what the letter carries, and the letter is written
for an offer that exists. A cap-cut structure and a breached promise do not
unmake the offer; they ride on top of it — `("styled",)` for the clauses the
caps left, then one `covenant-<name>-year-<worst>` per breached promise in the
policy's covenant order, and never a `no-year` record, which is a promise
nothing binds rather than a promise broken.

DESIGN DECISION — why does `decide` take the estate in?
Because a refusal branch is only checkable against an estate the stage was
actually handed, per the house precedent every estate-hungry stage set: the
stage asks the doors the legs need — the application, the fit, the collateral,
the rating, the structure, the promises and the bank's own record — and
nothing beyond them: no offers and no facilities, which belong to the letter
and the booking. The masks the check builds refuse unknown ids through the
estate's own class, and the counters keep the proof.

TODO: implement `decide` and `role` in this file: the legs the record cites
in `REASONS` order, the offer's conditions on top, the role the amount owns,
and the price the bank's own record carries — with every mismatch refused
naming the offender.

    A verdict outside the policy's three is refused; so is a record whose
    verdict the legs answer differently, either way, before anything is
    answered. A decline prices nothing, owns nothing, and carries no
    conditions: the legs that fired are all the record says.
"""

import policy
import stage_01
import stage_03
import stage_04
import stage_06
import stage_07

DECIDE_KEYS = ("id", "verdict", "role", "reasons", "conditions",
               "approved_cents", "price_bp")

STAGE_ERROR = "stage 8: "

_DECLINE = "decline"

_COUNTER = "counter"

_APPROVE = "approve"

_ZERO = 0

_STYLED_CONDITION = "styled"

_FORCED_GRADE = "F"

_NO_GATE = ""

_BREACH = "breach"

_HELD_REASONS = ("affordability", "scorecard", "collateral", "rating", "limit")


class DecideError(ValueError):
    """The refusal this stage raises: a leg, a verdict or a role it cannot carry.

    The stages of the ladder handed their records over; the bank's own record
    must agree with the legs they answered. A verdict the policy does not
    decide, a record whose verdict the legs answer differently in either
    direction, a priced rate that is not a whole count of basis points, and a
    role asked of a number that is not a whole count of cents are all refused
    with the offender named — a decision that disagrees with its own legs is
    exactly the thing this stage exists to refuse.
    """


def role(approved_cents):
    """Who owns a number: `committee` at the policy's threshold, else `underwriter`.

    `COMMITTEE_CENTS` is the line an amount has to reach *clearly*: an approval
    at the threshold is the committee's own, one cent under is not. The amount,
    never a request and never a record's word, is what owns its role — and a
    negative or a non-count refuses by name.
    """
    raise NotImplementedError("stage 8: implement role()")


def decide(cases, identity):
    """The decision of one application: the legs' verdict, owned and priced.

    The record answers `DECIDE_KEYS` in the order the contract prints them.
    Every leg the decision cites is a record an earlier stage answered — the
    fit, the collateral, the rating and, in the policy's `REASONS` order, the
    gate none of them passed. An approval cites the five legs that held; a
    decline cites the legs that fired and nothing more, prices nothing, owns
    nothing and carries no conditions. An offer stands on the structure the
    caps allowed: styled, it is a counter; unstyled, an approval — and its
    conditions carry the structure's one word and every breached promise the
    projections named, in the policy's covenant order. The role belongs to
    the approved amount at the policy's threshold; the price is the bank's own
    recorded rate, carried from its record and refused when it is not a whole
    count of basis points.

    The bank's own record is read and answered, never obeyed: a verdict the
    policy does not decide, or one the legs answer differently in either
    direction, is refused by name before anything is answered. The estate is
    read and never written: no offer is asked and no facility is opened.
    """
    raise NotImplementedError("stage 8: implement decide()")
