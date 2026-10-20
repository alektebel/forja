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


def _claim(claim):
    """The claim the return answers for, refused by name when it cannot be one."""
    if not isinstance(claim, dict):
        raise ReturnError("the claim is a %s, not a claim record"
                          % (type(claim).__name__,))
    if "claim" not in claim:
        raise ReturnError("the claim record carries no %r" % ("claim",))
    return claim

def _months_between(start, end):
    """The whole months from `start` to `end`, the calendar's clamping honoured."""
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months


def _whole(value, what):
    """A whole number, and a `bool` is not one here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReturnError("the %s %r is a %s, not a whole number"
                          % (what, value, type(value).__name__))
    return value


def _world(what, call):
    """The world's own answer for `what`, wrapped into this stage's refusal."""
    try:
        return call()
    except market.DescriptError as refused:
        raise ReturnError("the world refuses the %s (%s)" % (what, refused))


def _receipts(restructuring, claim_id):
    """What the close paid the class: the decree's breaks, the waterfall's
    cash, and the tendered paper.

    The recomputation stages 6 and 7 both run, restated here: the breaks lift
    their cents out of the pool first — and each break names the class it
    PAID, so the decree money is a receipt of the class it landed on — the
    rest runs down `faces` in the world's own class order, and the tendering
    face of the claim exchanges into new paper worth `tendered * issue_bp //
    10000`. A claim with no par line in the close is refused by name — the
    equity rides no par and so no receipts.
    """
    for row in restructuring["faces"]:
        if row.get("claim") == claim_id:
            break
    else:
        raise ReturnError("claim %r rides no par line in the close, and a return "
                          "has no receipts to search for" % (claim_id,))
    receipts = sum(break_row["paid_cents"]
                   for break_row in restructuring["breaks"]
                   if break_row.get("paid_to") == claim_id)
    pool = restructuring["proceeds_cents"]
    for break_row in restructuring["breaks"]:
        pool = pool - break_row["paid_cents"]
        if pool < 0:
            raise ReturnError("the breaks of the close overdraw its pool: the "
                              "decree leaves %d of %d"
                              % (pool, restructuring["proceeds_cents"]))
    remaining = pool
    cash = 0
    for row in restructuring["faces"]:
        take = row["face_cents"]
        if remaining < take:
            take = remaining
        remaining = remaining - take
        if row["claim"] == claim_id:
            cash = take
    tendered = sum(ballot["face_cents"] for ballot in restructuring["ballots"]
                   if ballot.get("claim") == claim_id
                   and ballot.get("vote") == "tender")
    paper = tendered * restructuring["issue_bp"] // PAR_BP
    return receipts + cash + paper


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

    receipts = _whole(receipts_cents, "receipts")
    rate = _whole(rate_bp, "rate")
    steps = _whole(months, "months")
    if receipts < 0:
        raise ReturnError("the receipts are %d cents, and nothing owed cannot be "
                          "paid a negative arrival" % (receipts,))
    if rate < 0:
        raise ReturnError("the rate is %d basis points, and a discount is never "
                          "charged backwards" % (rate,))
    if steps < 0:
        raise ReturnError("the months are %d, and a receipt arrives forwards"
                          % (steps,))
    period_bp = rules.period_rate(rate, rules.DEFAULT_BASIS)
    factor = rules.DISCOUNT_SCALE
    for _step in range(steps):
        factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
    return receipts * factor // rules.DISCOUNT_SCALE


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

    claim = _claim(claim)
    claim_id = claim["claim"]
    face_cents = _whole(claim.get("face_cents"), "the face of claim %r"
                        % (claim_id,))
    if face_cents <= 0:
        raise ReturnError("claim %r carries %d cents of face, and a trade of no "
                          "face is not a trade" % (claim_id, face_cents))
    acts_at = _world("the fund's acts-at dates", lambda: market.fund())["acts_at"]
    if at not in acts_at:
        raise ReturnError("the fund acts at %r and %r, and a return is red from "
                          "no other day" % (acts_at[0], acts_at[1]))
    quote = _world("print of claim %r at %r" % (claim_id, at),
                   lambda: market.quote(claim_id, at))
    restructuring = _world("the settlement facts", lambda: market.restructuring())
    cost_cents = face_cents * quote["price_bp"] // PAR_BP
    receipts_cents = _receipts(restructuring, claim_id)
    months = _months_between(at, restructuring["closed"])
    if months <= 0:
        if receipts_cents <= cost_cents:
            raise ReturnError("claim %r bought at the close pays %d cents of "
                              "receipts against a cost of %d: the trade ends "
                              "under water and the search cannot rescue it"
                              % (claim_id, receipts_cents, cost_cents))
        raise ReturnError("claim %r bought at the close costs %d against receipts "
                          "of %d, and there are %d months left to annualise: no "
                          "horizon is not a return" % (claim_id, cost_cents,
                                                       receipts_cents, months))
    if receipts_cents <= cost_cents:
        raise ReturnError("claim %r ends under water: the close pays %d cents of "
                          "receipts against a cost of %d, and a negative return "
                          "is a refusal, not a rate"
                          % (claim_id, receipts_cents, cost_cents))
    wall_pv = pv(receipts_cents, MAX_RATE_BP, months)
    if wall_pv > cost_cents:
        raise ReturnError("no rate in 0..%d brings claim %r's receipts of %d down "
                          "to its cost of %d: the wall itself pays %d"
                          % (MAX_RATE_BP, claim_id, receipts_cents, cost_cents,
                             wall_pv))
    low = 0
    high = MAX_RATE_BP
    while low < high:
        middle = (low + high) // 2
        if pv(receipts_cents, middle, months) <= cost_cents:
            high = middle
        else:
            low = middle + 1
    pv_cents = pv(receipts_cents, low, months)
    return {"claim": claim_id, "at": at, "cost_cents": cost_cents,
            "receipts_cents": receipts_cents, "months": months, "irr_bp": low,
            "pv_cents": pv_cents, "residue_cents": cost_cents - pv_cents}

if __name__ == "__main__":
    structure = market.structure()
    print("the fund's gate, over every debt claim it priced:")
    for record in structure:
        try:
            got = irr(record, market.ENTRY_DATE)
            print("  %-10s cost %-10d receipts %-10d months %d -> %d bp, "
                  "residue %d" % (got["claim"], got["cost_cents"],
                                  got["receipts_cents"], got["months"],
                                  got["irr_bp"], got["residue_cents"]))
        except ReturnError as refused:
            print("  %-10s refused: %s" % (record["claim"], refused))
