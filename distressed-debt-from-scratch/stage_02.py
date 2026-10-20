"""Distressed Debt Investing From Scratch — stage 2: The claim the fund buys, at the price the market gave.

The waterfall says who gets paid; the sheet says what getting paid costs. This
stage mechanises the trade the fund would have made: one claim, on one printed
date, at one price in basis points of par — and the cost of that price in
cents, and the discount to par it leaves.

Every quote the world prints is below par: the senior loan at ninety-two, the
unsecured notes at eighteen, the subordinated bonds at sixty, the equity at
four. That is not decoration. The discount IS the opportunity — the fund buys
because the market prices a claim at a fraction of what the waterfall will pay
it — and a trade at or above par would be buying the same money the waterfall
hands out, which is the restructuring's business, not the entry's. So the
stage refuses such a trade by name rather than price it: the machinery that
answers what a claim is worth when you pay all of it is stage 1's waterfall,
and what a claim is worth when it pays nothing is nobody's trade.

The record answers the four facts the trade rests on: which claim, on which
priced date, at what print, over what face — plus the two numbers the later
stages live off, the cost in cents and the discount in basis points of par.
The cost is `face * price_bp // 10000`, truncated, because a price is a whole
number of basis points and the entry is a whole number of cents: no float
passes through, and the check recomputes the cent.

    ENTRY_KEYS                    the six fields of an entry, in order
    EntryError                    the refusal this stage raises
    entry(claims, quote)          -> ENTRY_KEYS: the trade the sheet priced

DESIGN DECISION — why does the stage refuse a trade at or above par instead
of booking it?
Because the machinery that answers "what does par pay" already exists: the
waterfall. An entry at par is the fund buying exactly what the waterfall pays —
no discount, no upside, no trade to underwrite — and an entry above par is the
fund paying a premium for a recovery, which is a different course. Refusing by
name keeps the boundary honest: the entry stage's answers are only ever
discounted trades, and every number downstream of them can assume it.

DESIGN DECISION — why does the price come as a record rather than a number?
Because a price without its date is half a trade: the sheet prints each claim
twice, at the date the fund looked and at the date the restructuring closed,
and the entry the fund actually made is the first print. The record carries
claim, dated, price — and the stage echoes all three in its answer, so the
entry's cost is always traceable to the print it priced. A bare number could
be the entry and it could be the close, and the IRR machinery downstream
depends on which one it was.

DESIGN DECISION — why does the stage look the claim up on the capital
structure instead of trusting the sheet?
Because the sheet names a claim, and the face the cost is computed over lives
in the structure, not on the quote — the quote sheet is a list of prints, and
a print alone would answer a cost over a face the market could have printed
wrong. The lookup also refuses, by name, a quote for a claim the structure
does not hold: a price for an instrument nobody issued is a print the sheet
cannot explain.

DESIGN DECISION — why is `discount_bp` reported rather than left to the caller?
Because "eighteen" and "eighty-two" are the same fact said two ways — a price
of 18% of par and a discount of 82% of par — and the downstream stages mix the
two constantly in their heads. The entry says both: `price_bp` is what the
market asked, `discount_bp` is `10000 - price_bp`, what the fund is getting
for free relative to the waterfall's par. An off-by-one in either half shows
up as a disagreement between the two fields in the same record.

DESIGN DECISION — why is a priced date outside the sheet's two refused?
Because the two dates are not two prices of the sheet's mood — they are the
look and the close, and the whole course reasons from one to the other. A
trade dated in between has no print to trace: the world never printed it, and
an entry stage that echoed a price the market never gave would hand the
return search a date nobody can underwrite against.

TODO: implement `EntryError` and `entry` in this file: the trade off the
world's structure by the sheet's own price record — the face looked up by
claim, the cost `face * price_bp // 10000`, the discount `10000 - price_bp`.

    The entry is refused by name when the quote record carries no `claim`,
    `dated` or `price_bp`, when the claim is not on the capital structure,
    when the price is negative or at or above par, and when the dated is not
    one of the two dates the sheet prints.
"""

import claims

PAR_BP = 10000

ENTRY_KEYS = ("claim", "dated", "price_bp", "face_cents", "cost_cents",
              "discount_bp")


class EntryError(ValueError):
    """The refusal this stage raises: something that cannot be a trade.

    It names the offender — the quote record that carried no price, the claim
    the structure does not hold, the price at or above par, the date the sheet
    never printed — because a trade the market cannot have made must say what
    it was asked for rather than answer a position nobody underwrote.
    """


def entry(claims, quote):
    """The trade the sheet priced: face, print, cost in cents, discount in bp.

    `quote` is a `QUOTE_KEYS` record off the world's sheet — one claim, one of
    the two printed dates, one price in basis points of par. The stage looks
    the claim's face up on the capital structure and answers the record: the
    print echoed, the cost truncated from `face * price_bp // 10000`, the
    discount the price leaves against par.

    A print at or above par is refused by name: that trade is the waterfall's
    to pay, not the entry's to price. A claim off the structure, a price off
    the sheet or a date off the sheet is refused by name too.
    """
    raise NotImplementedError("stage 2: implement entry()")
