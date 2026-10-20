"""Distressed Debt Investing From Scratch — stage 9: The hold decision against the carry.

The return searched what the close pays for the entry. This stage asks the
question the fund asks every month the trade is still open: is the upside the
trading view still implies worth the carry the fund pays to keep waiting?

Both sides of that comparison are integers the world already carries. The
upside is the comparables' view minus the price paid: the defaulted segments
the world tabulates paid a recovery in basis points of par, the position
bought in at its own basis points, and the gap is worth
`(comparables_bp - price_bp) * face_cents // 10000` cents. The carry is the
fund's own annual basis points over the cost the sheet charged:
`cost * carry_bp // 10000` a year, `// 12` a month, `annual * months // 12`
over the months actually held — one division, once, so the rounding the
world's integers allow is the rounding the decision reads.

The decision itself is one comparison: hold when the upside is still strictly
above the carry the horizon charges, pass when it is not. Equality is a
pass — a trade whose whole remaining upside is its own funding has nothing
left to pay for holding it. The carry reads the position's own clock: the
months between the date the position was taken and the date the decision is
made, plus the horizon the decision projects. The live reading — `carry`
alone — is what waiting to `at` has already cost; the decision arm is what
waiting `horizon` more months would cost.

The refusals are the discipline of the book. A position entered at a price
at or above the comparables' view is UNBUYABLE by name — no horizon ever
clears an upside that is not there, and the fund must say which claim and
which two prints made it so rather than book a silent pass. A decision dated
before the position existed is refused by name — carry never runs backwards.
A horizon of less than one month is refused, and a position whose claim the
structure does not hold, or whose shape is not a position record, is refused
by name.

    DECISIONS      the two answers this stage may give, in order
    CARRY_KEYS     the fields of one carry reading, in order
    HOLD_KEYS      the fields of one hold decision, in order
    HoldError      the refusal this stage raises
    carry(position, at)
                   -> CARRY_KEYS: what waiting to `at` has cost so far
    hold(position, at, horizon)
                   -> HOLD_KEYS: hold, or pass, with the arithmetic attached

DESIGN DECISION — why is a hold strictly above the carry, and a tie a pass?
Because the carry is the fund's cost of waiting, and a decision is for the
money left after it: when upside == carry the capstone books nothing. An
`>=` arm would hold a trade whose entire projected recovery goes to
funding — a book that pays its manager to do nothing. The strictness is
pinned at the fixture's flip horizon, where one month of carry moves the
answer.

DESIGN DECISION — why is the upside measured against the comparables, never
against this claim's own close print? Because the close print is what the
world later RECORDED — data the modelling stages must not read — while the
comparables table is the trading view the fund underwrites on before
knowing. That boundary is the same one the previous stages honoured, and it
is why the entry price at or above the view is refused as unbuyable: at or
above the view there is no return the fund can name before the fact.

DESIGN DECISION — why does the carry divide once, `annual * months // 12`,
rather than running a monthly figure? Because two divisions with two
roundings would let the monthly view and the booked view drift apart by a
cent; the stage computes the annual figure once, exposes the monthly figure
it implies (`annual // 12`) as data, and books the total with the single
rounding — so the assertion "the monthly view times the months equals the
booked carry" is a fact about the world's own numbers here, not a lucky
one, and the check pins it.

DESIGN DECISION — why is the position's own date the anchor of the clock?
Because the carry is paid from the day the position was taken, whenever
that was — the fund's position record carries `dated`, and the decision at
`at` charges the months between. An `at` before `dated` would charge
negative waiting, which is why it is refused by name with both dates in the
message; a date equal to `dated` costs nothing, which is exactly what the
live carry reading answers.

DESIGN DECISION — why refuse an unbuyable position instead of answering a
`pass`? Because `pass` is a decision the arithmetic made about a trade with
upside; unbuyable is a price the view never supported — the trade was
mispriced at the door, not merely not worth waiting for. A silent pass
would bury a bad entry under the same word the good ones use; the refusal
names claim, entry price and the view it never cleared.

TODO: implement `HoldError`, `carry` and `hold` in this file: the cost from
the sheet's own fields, the comparables view looked up by the claim's own
segment and collateral, the upside and the carry in integers with one
division per quantity, the strict comparison that decides — and the
refusals: unbuyable by name, backwards dates by name, a horizon under one
month, and any record or claim that is not a position on this structure.

    `carry` refuses by name a position that is not a position record, a
    claim the structure does not hold, and a date before the position's
    own. `hold` refuses the same three, a horizon below one month, and a
    print at or above the comparables' view.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import dates
import rules
import claims as market

PAR_BP = 10000

#: The two answers the stage may give, and no others. The check walks the
#: tuple, pins its order and refuses any decision outside it.
DECISIONS = ("hold", "pass")

CARRY_KEYS = ("claim", "at", "months", "cost_cents", "carry_bp",
              "annual_cents", "monthly_cents", "carry_cents")

HOLD_KEYS = ("claim", "at", "horizon_months", "total_months", "cost_cents",
             "price_bp", "comparables_bp", "upside_cents", "monthly_cents",
             "carry_cents", "decision")


class HoldError(ValueError):
    """The refusal this stage raises: a decision the position does not carry."""

    # TODO stage 9: raise this with the offender in the message.


def carry(position, at):
    """What holding the position to `at` has cost, in integer cents.

    The cost is the sheet's own fields — `face_cents * price_bp // 10000` —
    the fund's annual carry over it, the monthly figure that annual implies,
    and the booked total `annual * months // 12` over the whole months
    between the position's own date and `at`.

    A position that is not a position record, a claim the structure does
    not hold, and a date before the position's own date are refused by name.
    """
    raise NotImplementedError("stage 9: implement carry()")


def hold(position, at, horizon):
    """The decision: hold, or pass, with the whole arithmetic attached.

    The upside is the comparables' recovery minus the price paid, over the
    position's face: `(comparables_bp - price_bp) * face_cents // 10000`.
    The carry is the live carry extended `horizon` months past `at`. Hold
    when upside > carry; pass when it is not.

    An entry price at or above the comparables' view is refused as unbuyable
    by name; a horizon below one month, a backwards date, an unknown claim
    and a malformed position are refused by name too.
    """
    raise NotImplementedError("stage 9: implement hold()")


if __name__ == "__main__":
    fund = market.fund()
    position = fund["positions"][0]
    print("the fund's live carry, and the decision the view answers:")
    for at in fund["acts_at"]:
        reading = carry(position, at)
        print("  carry to %-11s months %d -> %d after a cost of %d"
              % (at, reading["months"], reading["carry_cents"],
                 reading["cost_cents"]))
        near = hold(position, at, 12)
        print("    horizon 12 from there: %s on an upside of %d"
              % (near["decision"], near["upside_cents"]))
