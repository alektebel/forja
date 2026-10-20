"""Distressed Debt Investing From Scratch — stage 1: The capital structure as a waterfall of claims.

Everything the buy side later underwrites — the fund's chance of being paid
before the insurer, the new paper the exchange grants, the IRR the close implies
— is a consequence of where each claim sits. So this stage mechanises the
waterfall itself: the ranking of one borrower's claims by kind, and the split of
a pool of proceeds over that ranking.

The world gives the claims as data: an instrument kind (`senior-secured`,
`senior-unsecured`, `subordinated`, `equity`), a face amount in cents, an owner,
and the segment and collateral the book's own lending rode on. A bond is not a
bond because of the text on it — it is a bond because of where it sits: the
secured claim is paid first, to its face and no further, then the unsecured,
then the subordinated, and whatever the par lines cannot absorb either is the
equity beneath them. `waterfall(claims)` turns the batch into that ranking and
refuses, by name, a claim whose kind is not one of the four and two claims that
tie — two `senior-unsecured` records are a capital structure the world could
not rank, and a waterfall that guesses between them prices somebody's claim
twice and somebody's not at all.

`pay(proceeds, ranked)` then splits the pool: each claim what remains of it
after the classes above it, up to its face and no further, to the cent. Any
remainder the par lines cannot absorb is pinned — to the equity beneath if the
ranking carries one, or returned as `left_cents` when it does not — because
money the waterfall cannot place is money a settlement has not described, and
stage 6 will need to place it either in the waterfall or in a named violation.

    LINE_KEYS                     the four fields of one paid line, in order
    PAY_KEYS                      the three fields of a split, in order
    StructureError                the refusal this stage raises
    waterfall(claims)             -> the claims in waterfall order, ties refused
    pay(proceeds, ranked)         -> PAY_KEYS: each claim's split of the pool

DESIGN DECISION — why does the ranking come from `CLASSES` and nowhere else?
Because the order of the waterfall is the capital structure's own law, and a
stage that re-stated it locally could drift from the class order the quotes,
the ballots and the settlement all ride. `claims.CLASSES` is the one listing;
`waterfall` locates each claim's kind in it, and answers the records in that
order plus nothing. Equality of two records' kinds is not a sorting difficulty
to absorb — it is a refusal, because a ranking the world cannot describe is a
refusal to trade, not a tie to break.

DESIGN DECISION — why does a claim of an unknown kind refuse rather than rank
last?
Because "last" is a position: the equity holds it, and two lines cannot hold it.
A claim the capital structure does not recognise has no place in the order, and
a waterfall that appended it would have paid it out of the equity's remainder
— money the settlement records as the sponsor's. The refusal names the claim
and the kind, so the fix is a fix of the structure and not of the code.

DESIGN DECISION — why is a debt line paid to its face and no further?
Because the claim is a right to par, and a par line recovers par: four hundred
and forty million of faces cannot be paid out of a forty-eight million pool
however keen the senior note is. The `min` at every line is the whole
machinery — no line can pay above its face, and the pool flows to the next
class with whatever the previous one did not need. A line that paid more than
its face would be lending the pool; a line that paid less than the min
described would be returning money to equity.

DESIGN DECISION — why is the remainder pinned rather than refused?
Because the pool the parties actually settled is forty-eight million over a
waterfall of one hundred and three million of debt and the equity beneath it:
there is no remainder left over, and the machinery that would meet one — a
pool above every par line — is exactly the case where the equity is paid
everything the debt could not absorb, with the overflow the sponsor's to
record. When the ranking carries no equity line, the split still must not
lose the cents: `left_cents` answers what no line could place, and the check
pins it to the pool above the faces rather than dropping it.

DESIGN DECISION — why does `waterfall` accept the world itself, or the records
a rebuild carries?
Because the world hands its structure out in `CLASSES` order and the checks
need to hand the stage a capital structure the world does not hold — a tie, an
unknown kind, a ranking cut short of equity — to prove the refusals are the
stage's. `waterfall` takes the claims as they come: the module itself, whose
`structure()` answers the four records, or a sequence of `CLAIM_KEYS` records
a rebuild carries. Either way the ranking is the stage's own work: the records
are never trusted to arrive in order.

TODO: implement `StructureError`, `waterfall` and `pay` in this file: the
ranking by `claims.CLASSES` with ties and unknown kinds refused by name, and
the split of a pool over that ranking — each claim what remains after the
classes above it, to the cent, any remainder the par lines cannot place either
pinned to the equity beneath or answered as `left_cents`.

    The batch is refused by name when a claim record carries no `claim` or
    `kind` field, when a kind is not one of `claims.CLASSES`, when two claims
    tie, when a pool is negative, and when a ranking pays equity out of order.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import claims as market

LINE_KEYS = ("claim", "kind", "face_cents", "paid_cents")

PAY_KEYS = ("proceeds_cents", "lines", "left_cents")


class StructureError(ValueError):
    """The refusal this stage raises: something that cannot be a waterfall.

    It names the offender — the claim whose kind the structure does not hold,
    the two claims that tie, the pool that is not a count of cents, the line
    that sits out of order — because a payment a capital structure cannot
    describe must say what it was asked for rather than answer a split nobody
    can defend.
    """


def _records(batch):
    """The records a batch of claims carries: the world's, or the rebuild's.

    The world module answers its own structure through its accessor; a
    rebuild hands the records over directly. Anything else — a number, a
    text, a single record where a batch belongs — is refused by name,
    because a waterfall cannot be ranked over what it cannot name.
    """
    if hasattr(batch, "structure"):
        return batch.structure()
    if not isinstance(batch, (tuple, list)):
        raise StructureError("the claims arrived as a %s, not as a batch of "
                             "claims" % (type(batch).__name__,))
    return batch


def _fields(record, where):
    """The three fields the ranking needs, refused by name when one is absent."""
    if not isinstance(record, dict):
        raise StructureError("claim %d of the batch is a %s, not a claim record"
                             % (where, type(record).__name__))
    for field in ("claim", "kind", "face_cents"):
        if field not in record:
            raise StructureError(("the claim at rank %d of the batch carries no %r"
                                  % (where, field)))
    return record["claim"], record["kind"], record["face_cents"]


def waterfall(claims):
    """The claims in waterfall order: `claims.CLASSES`, secured first, equity last.

    The batch arrives as the claims module itself, whose `structure` answers the
    world's own four records, or as a sequence of records a rebuild carries.
    Either way the stage sorts, never trusts: each claim's kind is located in
    `CLASSES` and the records are answered in that order as a tuple.

    A batch with two claims of one kind, a kind the structure does not hold, or
    a record that names no claim, is refused by name.
    """
    records = _records(claims)
    ranked = []
    seen = {}
    for where, record in enumerate(records):
        claim, kind, face = _fields(record, where)
        if kind not in market.CLASSES:
            raise StructureError("claim %r is of kind %r, and the waterfall's "
                                 "own order is %r" % (claim, kind, market.CLASSES))
        if kind in seen:
            raise StructureError("claims %r and %r tie in kind %r, and the "
                                 "waterfall cannot rank them" % (seen[kind], claim, kind))
        seen[kind] = claim
        ranked.append((market.CLASSES.index(kind), where, record, claim))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return tuple(row[2] for row in ranked)


def _ranked(ranked):
    """The ranking a split rides: a batch of records, kinds in `CLASSES` order.

    A pool cannot be split over a ranking it cannot trust, so `pay` takes the
    same care the stage's own `waterfall` does: the kinds must run in class
    order, an equity may only hold the last line, and nothing duplicated, out
    of order or unrecognised gets past the door.
    """
    records = _records(ranked)
    lines = []
    previous = None
    for where, record in enumerate(records):
        claim, kind, face = _fields(record, where)
        if kind not in market.CLASSES:
            raise StructureError("claim %r is of kind %r, and the waterfall's "
                                 "own order is %r" % (claim, kind, market.CLASSES))
        if previous is not None and market.CLASSES.index(kind) <= previous:
            raise StructureError("claim %r sits at rank %d, out of the waterfall's "
                                 "own order %r" % (claim, where, market.CLASSES))
        if kind == "equity" and where != len(records) - 1:
            raise StructureError("claim %r rides no par and so can only hold the "
                                 "waterfall's last line, not rank %d" % (claim, where))
        previous = market.CLASSES.index(kind)
        lines.append({"claim": claim, "kind": kind, "face_cents": face})
    return lines


def pay(proceeds_cents, ranked):
    """The split of a pool of proceeds over a ranked waterfall.

    Each line is paid what remains of the pool after the classes above it, up
    to its face and no further; the equity beneath — which rides no par — is
    paid whatever the par lines could not absorb, and is only ever allowed to
    hold the last line. The record answers the pool, one `LINE_KEYS` row per
    line, and the cents no line could place as `left_cents`: zero when the
    ranking carries an equity line, and the pool above the faces otherwise,
    so a settlement either places the money or has to name where it went.

    A negative pool, a line whose kind is not one of `claims.CLASSES`, a
    duplicated kind or an equity that is not the last line, is refused by name.
    """
    if isinstance(proceeds_cents, bool) or not isinstance(proceeds_cents, int):
        raise StructureError("the proceeds %r are a %s, not a count of cents"
                             % (proceeds_cents, type(proceeds_cents).__name__))
    if proceeds_cents < 0:
        raise StructureError("the proceeds are %d cents, and a pool cannot be "
                             "paid to nobody" % (proceeds_cents,))
    lines = _ranked(ranked)
    remaining = proceeds_cents
    paid = []
    for line in lines:
        if line["kind"] == "equity":
            take = remaining
        else:
            face = line["face_cents"]
            take = face if face < remaining else remaining
        remaining = remaining - take
        paid.append({"claim": line["claim"], "kind": line["kind"],
                     "face_cents": line["face_cents"], "paid_cents": take})
    return {"proceeds_cents": proceeds_cents, "lines": tuple(paid),
            "left_cents": remaining}


if __name__ == "__main__":
    ranking = waterfall(market)
    split = pay(market.restructuring()["proceeds_cents"], ranking)
    print("the close's own pool, split over the waterfall of %s"
          % (" ".join(market.CLASSES),))
    print("  proceeds: %d cents" % (split["proceeds_cents"],))
    for line in split["lines"]:
        print("  %-14s %-16s paid %d of %d" % (line["claim"], line["kind"],
                                               line["paid_cents"], line["face_cents"]))
    print("  left unplaced: %d cents" % (split["left_cents"],))
