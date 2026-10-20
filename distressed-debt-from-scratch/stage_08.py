"""Distressed Debt Investing From Scratch — stage 8: Entry price, implied return, and the IRR.

The entry priced the trade; the settlement priced the exit. What sits between
them is the number the fund actually underwrites: the internal rate of return
the close implies over the cost the sheet charged — in basis points, whole
basis points, searched the way M1's own world searched an effective rate.

The inputs are data. The cost is the entry print: `claim["face_cents"] *
quote(at)["price_bp"] // 10000`, over one of the two dates the fund acts at.
The receipts are what the close recomputed: the class's waterfall cash, plus
the paper the exchange granted the tendering face, at its issue price —
`tendered * issue_bp // 10000`. Both arrive at the close, which is
`months_between(at, r["closed"])` months after `at`. One receipt, one date:
the search discounts it by whole months at a whole-period rate, stepped,
never powered, and the answer is the smallest rate in `0..MAX_RATE_BP` whose
present value does not exceed the cost — the residue (`cost - pv`) is part of
the record, not hidden, because a whole number of basis points cannot
usually price a trade to the cent.

The refusals are the trade's own honesty. A claim the close paid less than
its cost is a LOSS and is refused by name — the search cannot rescue a trade
that ends under water. A trade whose present value at the world's own wall
(`MAX_RATE_BP`, the fund's facts carry it) still exceeds the cost is beyond
the search and is refused by name with the present value the wall managed. A
claim the close holds no par line for — the equity — is refused by name, a
trade bought at the close with months still to run has no horizon, and a date
the fund does not act at is refused by name.

    RETURN_KEYS                   the eight fields of the searched return, in order
    ReturnError                   the refusal this stage raises
    pv(receipts_cents, rate_bp, months)
                                  -> the present value of one receipt, stepped
    irr(claim, at)                -> RETURN_KEYS: the smallest rate that pays

DESIGN DECISION — why is the search "smallest rate whose present value does
not exceed the cost" rather than the rate that lands exactly on the cost?
Because a whole number of basis points usually cannot price a stream to the
cent, so "exactly" is a float's promise while "not above" is an integer's.
The smallest rate whose `pv` is at or under the cost is the honest bracket
M1's own effective rate used: at the answer the present value is within one
basis point's worth of the cost or already inside it, and one basis point
lower the cost is exceeded — both sides pinned by the check against its own
search, so a bug in either direction shows as a disagreement with M1-style
staircase arithmetic.

DESIGN DECISION — why is the period rate `rate * 30 // 365` through the
world's rulebook?
Because the month is the world's policy (`rules.PERIOD_DAYS`), and the actual
365 day count is the world's basis: the stage never re-implements a day
count, it reads `rules.period_rate(rate_bp, rules.DEFAULT_BASIS)`. The
discount is stepped — `factor = factor * 10000 // (10000 + period_bp)` —
once a month, so a receipt eight months out is discounted eight times and a
float never enters: the same arithmetic the bank applied to its own
recoveries in stage 3, applied to the fund's one payment.

DESIGN DECISION — why does the residue stay in the record instead of
smoothing the answer?
Because the residue IS data: it says what the searched return could not
reach, and it is what distinguishes a trade whose IRR is 1278 bp with four
digits left over from one with a round answer nobody slit open. A smoothed
IRR would also be a float in a course that has none. The check pins the
residue to the cent against the search's own two-sided boundary — the pv at
the answer, the pv one basis point below it — so a stage that fudged the
search's last cent cannot keep the boundary aligned.

DESIGN DECISION — why refuse a loss instead of answering a negative IRR?
Because a negative IRR is not a fact the fund underwrites on — it is a trade
the gate should never have let through, and this stage is that gate. The
receipts are what the close actually paid; the cost is what the sheet
charged; when the first is under the second the honest answer is the refusal
with both numbers in it, so the loss is visible at the call rather than
buried in a negative rate nobody books.

DESIGN DECISION — why is the receipts number the CLASS's, and the fund's own
stake recomputed by the check?
Because the world's answer key is booked per class (`BL-UNSEC` received
38,150,000), and the class's receipts are what the settlement's facts
reproduce: waterfall cash plus the exchange's paper. The fund's own stake is
a small class of one — nine million of the forty-five tendered — and the
check recomputes its return from the stage's own `pv` surface, exactly the
pro-rata share the exchange's terms give it, so the stage never needs to
know the fund is a holder to answer for the machinery.

TODO: implement `ReturnError`, `pv` and `irr` in this file: the stepped one-
receipt discount, and the bisection over whole basis points — smallest rate
whose present value does not exceed the entry cost, residue reported, walls
and losses refused by name.

    `pv` refuses by name a receipts count, rate or month count that is not a
    whole number of the right shape. `irr` refuses by name a date the fund
    does not act at, a claim the close holds no par line for, a claim the
    sheet carries no print for, a trade under water, a trade bought at the
    close, and the wall.
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

RETURN_KEYS = ("claim", "at", "cost_cents", "receipts_cents", "months",
               "irr_bp", "pv_cents", "residue_cents")

#: The wall the return search never crosses — the fund's own `max_rate_bp`,
#: carried here as the stage's constant and pinned by the check against the
#: world's fund facts.
MAX_RATE_BP = 60000


class ReturnError(ValueError):
    """The refusal this stage raises: a return the trade does not carry.

    It names the offender — the claim ended under water, the wall no rate in
    the search pays through, the date the fund does not act at — because a
    return nobody can trace to its own receipts must say what it was asked
    for rather than answer a number nobody can underwrite on.
    """


def pv(receipts_cents, rate_bp, months):
    """The present value of one receipt, `months` whole months out.

    The factor steps once a month — `factor = factor * 10000 //
    (10000 + period_rate)` with the period rate the world's rulebook gives at
    the course's own day count — and truncates at every step, so eight months
    out is eight steps and no power is ever computed. Zero months out the
    receipt is worth its amount; a zero rate discounts nothing.

    A receipts count, a rate or a month count that is not a whole number of
    the right shape is refused by name.
    """
    raise NotImplementedError("stage 8: implement pv()")


def irr(claim, at):
    """The fund's implied annual return on one claim, in whole basis points.

    The cost is the sheet's print at `at` over the claim's face; the receipts
    are what the close recomputed from the settlement's facts — the class's
    waterfall cash plus the exchange's paper at its issue price — arriving
    `months_between(at, close)` months later. The search takes the smallest
    rate in `0..MAX_RATE_BP` whose present value does not exceed the cost,
    and reports the pv it managed and the residue it left.

    A loss (receipts under cost), the wall (even `MAX_RATE_BP` pays more than
    the cost), a claim the close holds no par line for, a trade bought at the
    close, and a date the fund does not act at, are refused by name.
    """
    raise NotImplementedError("stage 8: implement irr()")
