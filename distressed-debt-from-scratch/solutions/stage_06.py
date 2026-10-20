"""Distressed Debt Investing From Scratch — stage 6: The restructuring waterfall against absolute priority.

The close the world settled is recorded: a pool of proceeds, the ballots, and
— the part this stage is about — the ABSOLUTE-PRIORITY BREAKS the parties
agreed. Each break names the class it paid, the cents it paid it, the line
ahead of which it was paid, and the rule it bent. This stage recomputes what
each class ACTUALLY received from those facts, and then names the
contradictions: the cents the waterfall would have paid, and the cents the
decree instead gave to or took from each class.

The recomputation is the stage-1 waterfall with one addition. The decree comes
first — the breaks' cents are lifted straight out of the pool, before any par
line is served — and then the remaining pool runs down `faces`: each debt
claim what remains after the classes above it, up to its face. The actual
received is decree plus waterfall. The identity the check pins holds to the
cent: every cent the settlement paid is either in the waterfall or in a named
break, and both walks answer from the same pool, so their sums agree — or
somebody's settlement pays more than it had, which is a refusal.

`violations(restructuring)` walks the same pool again with no decree at all —
the payment absolute priority WOULD have ordered — and answers one row per
break: the break's own four fields echoed, plus the signed difference the
decree made to the class it paid (`given_cents`) and to the class it bent
(`taken_cents`). For the world's settlement these are the same three million
six hundred thousand — given to the insurer's bonds, taken from the unsecured
pareach — because a decree that pays a class out of turn comes out of the
turn the next class had.

    S6_PAYMENT_KEYS               the six fields of one class's settlement, in order
    S6_VIOLATIONS_KEYS            the six fields of one named violation, in order
    PriorityError                 the refusal this stage raises
    settlement_payment(restructuring, claim_rank)
                                  -> S6_PAYMENT_KEYS, recomputed from the facts
    violations(restructuring)     -> S6_VIOLATIONS_KEYS rows, one per break

DESIGN DECISION — why does the decree come out of the pool before the walk?
Because that is what "break absolute priority" means: the insurer's keep-whole
premium was agreed because without it the insurer would not tender, and it was
paid out of the close's proceeds ahead of the unsecured's par — not out of the
senior's nose or of thin air. A walk that paid the waterfall first and the
decree out of the remainder would make the decree senior to itself, and the
stage's arithmetic is the settlement's own sequence: decree, then waterfall.

DESIGN DECISION — why is `claim_rank` an integer and not the claim's name?
Because rank IS the mechanism: the waterfall pays by position, and the stage
answers by position too — rank one is the senior secured, rank two the unsecured,
rank three the subordinated. A name would let the caller believe the answer is
about the instrument; the rank makes it about the line. A rank the close's
waterfall does not hold (zero, four, minus one) is refused by name with the
number of the par lines the close actually settled.

DESIGN DECISION — why are the violations computed against a no-decree walk
rather than against the waterfall alone?
Because a break's damage is exactly the gap between two amounts: what the line
ahead of it received, and what absolute priority would have handed that same
line from the same pool. The no-decree walk is the counterfactual the parties
agreed to pay for; recomputing it makes the damage a subtraction a reader can
check, `given_cents` and `taken_cents` summing to zero over the classes the
decree and the bent line touch — money moved, not money made.

DESIGN DECISION — why is the overdrawn decree refused rather than partly paid?
Because a settlement that decrees more than the pool holds is not a waterfall
with a big first break; it is a broken record. The decree acts BEFORE the walk,
so a decree larger than the proceeds leaves the walk a negative pool, and a
negative pool pays negative nothing. The refusal names the break's cents and
the pool they were to come from — the one number the record got wrong.

DESIGN DECISION — why does the stage validate the `faces` rows against the
capital structure?
Because the recomputation answers for classes by claim, and a claim the
structure does not hold (or one that is the equity, which rides no par) cannot
be a line of the close. The faces rows must be the world's own debt claims in
class order — the ones stage 1 ranked — and a faces row that names an unknown
claim, duplicates one, or sits out of order names the offender and refuses.
The settlement may bend the order of PAYMENTS, never the order of the records
that describe them.

TODO: implement `PriorityError`, `settlement_payment` and `violations` in this
file: the recomputed settlement per class — decree first, waterfall over the
faces — and the named violations, given and taken, against the no-decree walk.

    The recomputation is refused by name when the record carries no
    `RESTRUCTURING_KEYS` field, when a break names a claim the structure does
    not hold or pays a negative or overdrawn amount, when a `faces` row is
    not one of the world's debt claims in class order, and when `claim_rank`
    is not one of the close's par lines.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import claims as market
import rules
import dates

PAR_BP = 10000

S6_PAYMENT_KEYS = ("claim", "rank", "face_cents", "decree_cents",
                   "waterfall_cents", "received_cents")

S6_VIOLATIONS_KEYS = ("paid_to", "paid_cents", "ahead_of", "rule",
                      "given_cents", "taken_cents")


def _record(restructuring):
    """The settlement's own record, refused by name when a field is absent."""
    if not isinstance(restructuring, dict):
        raise PriorityError("the settlement is a %s, not a RESTRUCTURING_KEYS "
                            "record" % (type(restructuring).__name__,))
    for field in market.RESTRUCTURING_KEYS:
        if field not in restructuring:
            raise PriorityError("the settlement carries no %r" % (field,))
    return restructuring


def _kinds_of(claims_module):
    """The world's debt claims, by claim id, with the class order they sit in."""
    kinds = {}
    for record in claims_module.structure():
        kinds[record["claim"]] = record["kind"]
    return kinds


def _faces(claims_module, restructuring):
    """The par lines the close settles, refused unless they are the world's own.

    Every `faces` row must name a debt claim the structure holds, in the
    waterfall's own class order, once each: the close pays classes, not
    instruments, and the equity beneath rides no par at all.
    """
    kinds = _kinds_of(claims_module)
    lines = []
    previous = None
    for row in restructuring["faces"]:
        if not isinstance(row, dict) or "claim" not in row or "face_cents" not in row:
            raise PriorityError("a faces row is not a claim and a face: %r" % (row,))
        claim = row["claim"]
        if claim not in kinds:
            raise PriorityError("the close's faces name claim %r, and the capital "
                                "structure holds no such claim" % (claim,))
        kind = kinds[claim]
        if kind == "equity":
            raise PriorityError("claim %r is the equity, and the equity is not a "
                                "par line of the close" % (claim,))
        index = claims_module.CLASSES.index(kind)
        if previous is not None and index <= previous:
            raise PriorityError("claim %r sits out of the waterfall's own order in "
                                "the close's faces" % (claim,))
        previous = index
        lines.append(row)
    return lines


def _walk(claims_module, restructuring, with_decree):
    """The pool run down the close: decree first iff `with_decree`, then faces.

    Returns the decree by claim, the waterfall by claim, and the total
    received by claim — the two walks this stage computes and the check lays
    side by side. A break the pool cannot fund is refused by name before any
    line is served: a negative pool pays negative nothing.
    """
    _record(restructuring)
    lines = _faces(claims_module, restructuring)
    kinds = _kinds_of(claims_module)
    pool = restructuring["proceeds_cents"]
    decree = {}
    if with_decree:
        for break_row in restructuring["breaks"]:
            for field in ("paid_to", "paid_cents", "ahead_of", "rule"):
                if field not in break_row:
                    raise PriorityError("a break carries no %r" % (field,))
            paid_to = break_row["paid_to"]
            cents = break_row["paid_cents"]
            ahead_of = break_row["ahead_of"]
            if paid_to not in kinds:
                raise PriorityError("a break pays claim %r, and the capital "
                                    "structure holds no such claim" % (paid_to,))
            if ahead_of not in kinds:
                raise PriorityError("a break names claim %r ahead of its payment, "
                                    "and the capital structure holds no such "
                                    "claim" % (ahead_of,))
            if isinstance(cents, bool) or not isinstance(cents, int) or cents < 0:
                raise PriorityError("the break to claim %r pays %r, which is not a "
                                    "count of cents" % (paid_to, cents))
            if cents > pool:
                raise PriorityError("the break to claim %r pays %d cents out of a "
                                    "pool of %d, and the decree is not a borrower"
                                    % (paid_to, cents, pool))
            decree[paid_to] = decree.get(paid_to, 0) + cents
            pool = pool - cents
    waterfall = {}
    remaining = pool
    for line in lines:
        take = line["face_cents"]
        if remaining < take:
            take = remaining
        waterfall[line["claim"]] = take
        remaining = remaining - take
    received = {}
    for line in lines:
        claim = line["claim"]
        received[claim] = waterfall[claim] + decree.get(claim, 0)
    return decree, waterfall, received


def _rank_line(lines, claim_rank):
    """The par line at `claim_rank`, refused by name when the close has none."""
    if isinstance(claim_rank, bool) or not isinstance(claim_rank, int):
        raise PriorityError("the rank %r is a %s, and a rank is a whole number"
                            % (claim_rank, type(claim_rank).__name__))
    if claim_rank < 1 or claim_rank > len(lines):
        raise PriorityError("the close settles %d par lines, and rank %d is not "
                            "one of them" % (len(lines), claim_rank))
    return lines[claim_rank - 1]


class PriorityError(ValueError):
    """The refusal this stage raises: a settlement the facts cannot pay.

    It names the offender — the break the pool cannot fund, the claim the
    structure does not hold, the rank beyond the waterfall's own lines —
    because a settlement nobody can trace to its own proceeds must say what
    it was asked for rather than pay a ghost.
    """


def settlement_payment(restructuring, claim_rank):
    """What one class actually received at the close, recomputed from the facts.

    The breaks' cents are lifted out of the pool first — the decree the parties
    agreed — and the remaining pool runs down `faces` in the world's own class
    order, each debt claim what remains up to its face. The record answers the
    claim at `claim_rank`, its face, the decree it was paid, the waterfall it
    was paid, and the two added up.

    A rank that is not one of the close's par lines, a break the pool cannot
    fund, a break or a faces row naming a claim the structure does not hold,
    and a record that carries none of the settlement's own fields, are refused
    by name.
    """

    restructuring = _record(restructuring)
    lines = _faces(market, restructuring)
    line = _rank_line(lines, claim_rank)
    decree, waterfall, received = _walk(market, restructuring, True)
    claim = line["claim"]
    return {"claim": claim, "rank": claim_rank,
            "face_cents": line["face_cents"],
            "decree_cents": decree.get(claim, 0),
            "waterfall_cents": waterfall[claim],
            "received_cents": received[claim]}


def violations(restructuring):
    """The breaks, each named with the class it bent and the cents it moved.

    The same settlement recomputed with no decree: the `expected` walk is
    absolute priority's own answer over the same pool. Each break answers a
    row — its own fields echoed — plus `given_cents`, what the decree gave
    the class it paid over the expected, and `taken_cents`, what it took the
    class it bent by paying ahead of it.

    A break naming a claim the structure does not hold, a pool the breaks
    overdraw, and a record that carries none of the settlement's own fields,
    are refused by name.
    """

    restructuring = _record(restructuring)
    lines = _faces(market, restructuring)
    _decree, _waterfall, actual = _walk(market, restructuring, True)
    _none, expected, _received = _walk(market, restructuring, False)
    rows = ()
    for break_row in restructuring["breaks"]:
        paid_to = break_row["paid_to"]
        ahead_of = break_row["ahead_of"]
        rows = rows + ({"paid_to": paid_to,
                        "paid_cents": break_row["paid_cents"],
                        "ahead_of": ahead_of,
                        "rule": break_row["rule"],
                        "given_cents": actual[paid_to] - expected[paid_to],
                        "taken_cents": actual[ahead_of] - expected[ahead_of]},)
    return rows

if __name__ == "__main__":
    r = market.restructuring()
    print("the close, recomputed from the facts:")
    for rank in (1, 2, 3):
        got = settlement_payment(r, rank)
        print("  rank %d %-10s face %-10d decree %-9d waterfall %-10d -> %d"
              % (rank, got["claim"], got["face_cents"], got["decree_cents"],
                 got["waterfall_cents"], got["received_cents"]))
    total = sum(settlement_payment(r, rank)["received_cents"] for rank in (1, 2, 3))
    print("  received in total: %d of a pool of %d"
          % (total, r["proceeds_cents"]))
    print("the absolute-priority violations, given and taken:")
    for row in violations(r):
        print("  paid %s %d ahead of %s: given %+d to %s, taken %+d from %s"
              % (row["paid_to"], row["paid_cents"], row["ahead_of"],
                 row["given_cents"], row["paid_to"],
                 row["taken_cents"], row["ahead_of"]))
