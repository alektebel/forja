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

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import claims as market

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


def _quote(quote):
    """The print the trade rides, refused by name when it cannot be one."""
    if not isinstance(quote, dict):
        raise EntryError("the quote is a %s, not a quote record"
                         % (type(quote).__name__,))
    for field in ("claim", "dated", "price_bp"):
        if field not in quote:
            raise EntryError("the quote carries no %r" % (field,))
    return quote


def _price_bp(claim, price_bp):
    """A whole number of basis points, below par, or a refusal naming either."""
    if isinstance(price_bp, bool) or not isinstance(price_bp, int):
        raise EntryError("the price of claim %r is a %s, not a count of basis "
                         "points" % (claim, type(price_bp).__name__))
    if price_bp < 0:
        raise EntryError("the price of claim %r is %d basis points, and a claim "
                         "is not paid to take it" % (claim, price_bp))
    if price_bp >= PAR_BP:
        raise EntryError("claim %r is priced at %d basis points, at or above "
                         "par: paying for what the waterfall pays anyway is the "
                         "restructuring's business, not an entry"
                         % (claim, price_bp))
    return price_bp


def _dated(dated):
    """One of the two dates the sheet prints, or a refusal naming the date."""
    printed = (market.ENTRY_DATE, market.CLOSE_DATE)
    if dated not in printed:
        raise EntryError("the sheet prints %r and %r, and no trade is priced at "
                         "%r" % (printed[0], printed[1], dated))
    return dated


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
    _quote(quote)
    claim = quote["claim"]
    dated = _dated(quote["dated"])
    price_bp = _price_bp(claim, quote["price_bp"])
    face = None
    for record in claims.structure():
        if record["claim"] == claim:
            face = record["face_cents"]
            break
    if face is None:
        raise EntryError("the capital structure holds no claim %r, and the sheet "
                         "prices it" % (claim,))
    cost = face * price_bp // PAR_BP
    return {"claim": claim, "dated": dated, "price_bp": price_bp,
            "face_cents": face, "cost_cents": cost,
            "discount_bp": PAR_BP - price_bp}


if __name__ == "__main__":
    structure = market.structure()
    print("the sheet, priced as trades:")
    print("  claim          dated        price  face        cost        discount")
    for print_date in (market.ENTRY_DATE, market.CLOSE_DATE):
        for record in structure:
            if record["kind"] == "equity":
                continue
            trade = entry(market, market.quote(record["claim"], print_date))
            print("  %-14s %-12s %-6d %-11d %-11d %d"
                  % (trade["claim"], trade["dated"], trade["price_bp"],
                     trade["face_cents"], trade["cost_cents"],
                     trade["discount_bp"]))
