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

_COMMITTEE = "committee"

_UNDERWRITER = "underwriter"


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


def _fit(cases, identity):
    """Stage 1's record of the two halves, or the stage's own refusal."""
    try:
        record = stage_01.affordability(cases, identity)
    except ValueError as refused:
        raise DecideError(STAGE_ERROR + ("the fit of %r was not handed over: %s"
                                         % (identity, refused)))
    return record


def _credited(cases, identity, requested_cents):
    """Stage 3's record of the collateral, or the stage's own refusal."""
    try:
        record = stage_03.return_of(identity, requested_cents, cases)
    except ValueError as refused:
        raise DecideError(STAGE_ERROR + ("the collateral of %r was not handed "
                                         "over: %s" % (identity, refused)))
    return record


def _rating(cases, identity):
    """Stage 4's record of the grade and the gates, or the stage's own refusal."""
    try:
        record = stage_04.rating(cases, identity)
    except ValueError as refused:
        raise DecideError(STAGE_ERROR + ("the rating of %r was not handed over: "
                                         "%s" % (identity, refused)))
    return record


def _structure(cases, identity):
    """Stage 6's record of the structure, or the stage's own refusal."""
    try:
        record = stage_06.limit(cases, identity)
    except ValueError as refused:
        raise DecideError(STAGE_ERROR + ("the approved structure of %r was not "
                                         "handed over: %s" % (identity, refused)))
    return record


def _promises(cases, identity):
    """Stage 7's records of the promises, or the stage's own refusal."""
    try:
        records = stage_07.covenants(cases, identity)
    except ValueError as refused:
        raise DecideError(STAGE_ERROR + ("the promises of %r were not handed "
                                         "over: %s" % (identity, refused)))
    return records


def _fired(fit, credited, rating):
    """Every leg that fired, in `REASONS` order.

    One predicate per leg, and the policy's order is the only order the list
    is read in. The scorecard never fires: the band table answers every total,
    a band below every threshold reading the last band, so the band alone can
    never be the word a decline cites — the rating leg speaks for it. The
    limit never fires: a styled structure is the offer's condition, not its
    absence. A covenant never fires: a breach is a condition, a promise the
    letter carries, and never the verdict's own reason — the bank's own
    records cite `covenant` on no application at all.
    """
    fire = {
        "affordability": not fit["fits"],
        "scorecard": False,
        "collateral": not credited["eligible"],
        "rating": rating["grade"] == _FORCED_GRADE,
        "limit": False,
        "covenant": False,
        "gate": rating["gate"] != _NO_GATE,
    }
    return tuple(leg for leg in policy.REASONS if fire[leg])


def _priced(identity, record):
    """The bank's own priced rate, as a whole count of basis points.

    The price is the one number the decision does not rebuild: the bank set
    it, stage 5 explains it, and the record carries it. A price that is not a
    whole count, or one below nothing, is a record whose arithmetic the legs
    cannot underwrite, and the refusal names the application.
    """
    priced = record["price_bp"]
    if isinstance(priced, bool) or not isinstance(priced, int):
        raise DecideError(STAGE_ERROR + ("the bank's own price of %r is %r, a "
                                         "%s, not a whole count of basis points"
                                         % (identity, priced,
                                            type(priced).__name__)))
    if priced < _ZERO:
        raise DecideError(STAGE_ERROR + ("the bank's own price of %r is %d "
                                         "basis points, below nothing"
                                         % (identity, priced)))
    return priced


def role(approved_cents):
    """Who owns a number: `committee` at the policy's threshold, else `underwriter`.

    `COMMITTEE_CENTS` is the line an amount has to reach *clearly*: an approval
    at the threshold is the committee's own, one cent under is not. The amount,
    never a request and never a record's word, is what owns its role — and a
    negative or a non-count refuses by name.
    """
    if isinstance(approved_cents, bool) or not isinstance(approved_cents, int):
        raise DecideError(STAGE_ERROR + ("the approved amount %r is a %s, not a "
                                         "whole count of cents"
                                         % (approved_cents,
                                            type(approved_cents).__name__)))
    if approved_cents < _ZERO:
        raise DecideError(STAGE_ERROR + ("the approved amount is %d cents, and "
                                         "nothing is approved backwards"
                                         % (approved_cents,)))
    if approved_cents >= policy.COMMITTEE_CENTS:
        return _COMMITTEE
    return _UNDERWRITER


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
    application = cases.application(identity)
    fit = _fit(cases, identity)
    credited = _credited(cases, identity, application["requested_cents"])
    rating = _rating(cases, identity)
    fired = _fired(fit, credited, rating)
    declined = True if fired else False
    record = cases.decision(identity)
    declared = record["verdict"]
    if declared not in policy.DECISIONS:
        raise DecideError(STAGE_ERROR + ("the bank's own record of %r decided "
                                         "%r, and the policy decides only %r"
                                         % (identity, declared,
                                            policy.DECISIONS)))
    if declined != (declared == _DECLINE):
        raise DecideError(STAGE_ERROR + ("the legs of %r answer %r, and the "
                                         "bank's own record decided %r; a "
                                         "record the legs cannot reach is "
                                         "refused, not answered"
                                         % (identity,
                                            _DECLINE if declined else _APPROVE,
                                            declared)))
    if declined:
        return {"id": identity,
                "verdict": _DECLINE,
                "role": role(_ZERO),
                "reasons": fired,
                "conditions": (),
                "approved_cents": _ZERO,
                "price_bp": _ZERO}
    structure = _structure(cases, identity)
    styled = structure["styled"]
    verdict = _COUNTER if styled else _APPROVE
    if verdict != declared:
        raise DecideError(STAGE_ERROR + ("the structure of %r styles %r, and "
                                         "the bank's own record decided %r; a "
                                         "record the structure cannot reach is "
                                         "refused, not answered"
                                         % (identity, verdict, declared)))
    conditions = (_STYLED_CONDITION,) if styled else ()
    breached = []
    for promise in _promises(cases, identity):
        if promise["verdict"] == _BREACH:
            breached.append("covenant-%s-year-%d"
                            % (promise["name"], promise["year"]))
    approved = structure["approved_cents"]
    return {"id": identity,
            "verdict": verdict,
            "role": role(approved),
            "reasons": _HELD_REASONS,
            "conditions": conditions + tuple(breached),
            "approved_cents": approved,
            "price_bp": _priced(identity, record)}
