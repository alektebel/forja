"""Distressed Debt Investing From Scratch — stage 10: The thesis, checked against what actually happened.

Everything the course computed so far was a line in one argument the fund
makes about one trade. This stage is that argument written down, and then
graded by the world against what the parties actually settled.

The thesis is the fund's underwriting book for the position it holds: the
claim, the day the fund decided, the close the argument runs to, the months
between them; the cost the sheet charged over the position's held face at
the position's own price; the three readings it bought on — the bank's
actuals on the claim's segment, the identity's distance walked through the
world's own ladder, and the comparables' trading view — with the middle one
the underwriting cleared on; the receipts the close's exchange and waterfall
recomputed, the return the fund's wall-bounded search finds over them, the
residue the whole basis points leave; the carry holding costs over the
months, the upside the view implies over the price paid, and the decision
that comparison answers — hold, or pass.

The audit grades that argument claim by claim through the world's own answer
key: per debt claim, the middle of the three readings the fund underwrote
on, the realised basis points what actually settled paid over the face, the
gap between them, and a grade — pass when the gap is inside the
world's audit tolerance, fail when it is not. The audit takes both worlds by hand — the
bank's `book` and the market's `claims` module — because the capstone is the
one place in the course where the two sides of the trade meet, and it is the
only stage allowed to read the answer key: the stats ledger counts every ask
of the `outcome` door, and the check counts them before and after.

    THESIS_KEYS                   the eighteen fields of the thesis, in order
    AUDIT_KEYS                    the thirteen fields of one graded claim, in order
    GRADES                        the two grades the audit may give, in order
    ThesisError                   the refusal this stage raises
    thesis(claim, at)             -> THESIS_KEYS: the fund's written argument
    audit(book, claims, at, close)
                                  -> one AUDIT_KEYS row per debt claim: the
                                     grades against what actually happened

DESIGN DECISION — why does the thesis answer for the position the fund
holds, and refuse every other claim by name? Because a thesis nobody
committed capital to is an essay, not an underwriting file: the fund's
record carries the price it actually paid and the face it actually holds,
and every cost, carry and upside in the file is computed over them. Answering
for a claim the fund never bought would be a record that looks like the
real one and audits against nothing — so the stage walks the fund's own
positions, and a claim they do not hold is refused.

DESIGN DECISION — why does the audit take the two worlds as arguments
instead of reading a passed-in thesis? Because the audit is the world
grading the FUND, not the fund grading its own homework: it recomputes the
three readings from the bank's actuals, the identity and the comparables —
the same legs the thesis used — and only then opens the answer key to grade
the middle against what settled. A thesis the audit took on faith could be
right only because it said so; recomputing the legs makes the grading trap
both files' arithmetic at once.

DESIGN DECISION — why is the realised basis point received times par over
the face, and the grade one absolute gap against the fund's own tolerance?
Because the answer key is cents and the thesis is basis points, so the two
only meet at one scale: what arrived over what was owed. The tolerance is
the fund's OWN audit_tolerance_bp — a house number, carried in the world's
fund facts and pinned by the check — because who the grader is decides how
far a miss is missed: the fund must survive its own bar, not the model's.

DESIGN DECISION — why is the capstone the only stage that reads the answer
key, and why does not one line of the thesis? Because the recovery stage's
discipline holds all the way down: the modelling stages reproduce the close
from the facts below it, the thesis is computed before the close is known,
and only the audit — after the fact, claim by claim — opens `outcome` to
grade. The ledger makes that boundary mechanical: the check counts the
`outcome` counters before and after the thesis and they must not move, and
after the audit they must stand at one ask per debt claim.

DESIGN DECISION — why is the middle the grade the realised close is compared
to, and not the best of the three readings? Because the middle is what the
fund underwrote on — the stage-5 reading the decision cleared on. Grading
the best case would flatter every trade the comps flattered, grading the
worst would fail every trade the ladders saved; the middle is the number
the trade was bought on, which is the number the audit grades.

TODO: implement `ThesisError`, `thesis` and `audit` in this file: the
fund's own book of the held position — cost, the three readings, the
middle, the receipts the close's terms pay the held face, the searched
return and its residue, the carry, the upside and the decision — and the
audit that recomputes the legs claim by claim, grades the middle against
what actually settled, and answers one row per debt claim.

    `thesis` refuses by name a record that is not a claim, the equity, a
    claim the fund holds no position on, and a date that is not the day the
    position itself was taken. `audit` refuses by name a close that is not
    the world's own close date, a date the asset path has no reading for,
    and any world or book argument it cannot read.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import book
import dates
import rules
import claims as market

PAR_BP = 10000

#: The wall the return search never crosses — carried from the entry stage's
#: discipline and pinned by the check against the world's fund facts.
MAX_RATE_BP = 60000

THESIS_KEYS = ("claim", "at", "close", "months", "face_cents", "price_bp",
               "cost_cents", "forecast_bp", "merton_bp", "comparables_bp",
               "middle_bp", "receipts_cents", "irr_bp", "pv_cents",
               "residue_cents", "carry_cents", "upside_cents", "decision")

AUDIT_KEYS = ("claim", "at", "close", "received_cents", "face_cents",
              "realised_bp", "forecast_bp", "merton_bp", "comparables_bp",
              "middle_bp", "tolerance_bp", "gap_bp", "grade")

#: The two grades the audit may give, and no others.
GRADES = ("pass", "fail")


class ThesisError(ValueError):
    """The refusal this stage raises: an underwriting file the world cannot hope."""


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
        raise ThesisError("the %s %r is a %s, not a whole number"
                          % (what, value, type(value).__name__))
    return value


def _world(what, call):
    """The world's own answer for `what`, wrapped into this stage's refusal."""
    try:
        return call()
    except market.DescriptError as refused:
        raise ThesisError("the world refuses the %s (%s)" % (what, refused))


def _claim(claim):
    """The claim the thesis answers for, refused by name when it cannot be one."""
    if not isinstance(claim, dict):
        raise ThesisError("the claim is a %s, not a claim record"
                          % (type(claim).__name__))
    if "claim" not in claim:
        raise ThesisError("the claim carries no %r" % ("claim",))
    if claim.get("kind") == "equity":
        raise ThesisError("claim %r is the equity, and the equity rides no "
                          "par for a thesis to stand on" % (claim.get("claim")))
    return claim


def _position(position, claim_id):
    """The fund's position on `claim_id`, or a refusal naming one."""
    fund = market.fund()
    for pos in fund["positions"]:
        if pos["claim"] == claim_id:
            return pos
    raise ThesisError("the fund holds no position on claim %r, and a thesis "
                      "nobody bought is an essay, not an underwriting"
                      % (claim_id,))


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
        raise ThesisError("claim %r rides no par line in the close, and a return "
                          "has no receipts to search for" % (claim_id,))
    receipts = sum(break_row["paid_cents"]
                   for break_row in restructuring["breaks"]
                   if break_row.get("paid_to") == claim_id)
    pool = restructuring["proceeds_cents"]
    for break_row in restructuring["breaks"]:
        pool = pool - break_row["paid_cents"]
        if pool < 0:
            raise ThesisError("the breaks of the close overdraw its pool: the "
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


def _pv(receipts_cents, rate_bp, months):
    """The present value of one receipt, `months` whole months out."""
    receipts = _whole(receipts_cents, "receipts")
    rate = _whole(rate_bp, "rate")
    steps = _whole(months, "months")
    if receipts < 0:
        raise ThesisError("the receipts are %d cents, and nothing owed cannot be "
                          "paid a negative arrival" % (receipts,))
    if rate < 0:
        raise ThesisError("the rate is %d basis points, and a discount is never "
                          "charged backwards" % (rate,))
    if steps < 0:
        raise ThesisError("the months are %d, and a receipt arrives forwards"
                          % (steps,))
    period_bp = rules.period_rate(rate, rules.DEFAULT_BASIS)
    factor = rules.DISCOUNT_SCALE
    for _step in range(steps):
        factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
    return receipts * factor // rules.DISCOUNT_SCALE


def _search(receipts_cents, cost_cents, months):
    """The smallest rate in 0..MAX_RATE_BP whose pv does not exceed cost."""
    low = 0
    high = MAX_RATE_BP
    while low < high:
        middle = (low + high) // 2
        if _pv(receipts_cents, middle, months) <= cost_cents:
            high = middle
        else:
            low = middle + 1
    return low


def _three_readings(book, claim, at):
    """The three readings from the bank's actuals, the identity, and the comps."""
    # Forecast: bank's actuals on the claim's segment
    segment = claim["segment"]
    par = 0
    discounted = 0
    for loan in book.loans():
        if loan.get("segment") != segment:
            continue
        rows = book.recoveries(loan["loan"])
        if not rows:
            continue
        par = par + loan["principal_cents"]
        period_bp = rules.period_rate(loan["rate_bp"], rules.DEFAULT_BASIS)
        for row in rows:
            amount = row["amount_cents"]
            if row["source"] == "collateral":
                haircut = rules.COLLATERAL_HAIRCUT_BP[loan["collateral_kind"]]
                amount = amount * (rules.DISCOUNT_SCALE - haircut) \
                    // rules.DISCOUNT_SCALE
            steps = _months_between(at, row["date"])
            if steps < 0:
                steps = 0
            factor = rules.DISCOUNT_SCALE
            for _step in range(steps):
                factor = factor * rules.DISCOUNT_SCALE \
                    // (rules.DISCOUNT_SCALE + period_bp)
            discounted = discounted + amount * factor // rules.DISCOUNT_SCALE
    if par == 0:
        raise ThesisError("the book's %r segment has no defaulted loan with "
                          "recoveries to read, so the recovery-based view "
                          "has nothing to stand on" % (segment,))
    forecast_bp = discounted * PAR_BP // par

    # Merton: distance and ladder
    borrower = claim["borrower"]
    row = _world("debt table row of borrower %r" % (borrower,),
                 lambda: market.merton(borrower))
    asset = _world("the asset path at %r" % (at,), lambda: market.asset_at(at))
    debt = row["debt_cents"]
    units = (asset - debt) * market.DD_SCALE * market.DD_SCALE \
        // (asset * row["band_bp"])
    ladder = market.ladder()
    if units < ladder[0]["from_dd"] or units > ladder[-1]["from_dd"]:
        raise ThesisError("the distance %d is outside the ladder's own "
                          "rows for borrower %r, and no probability is "
                          "invented" % (units, borrower))
    pd_bp = ladder[0]["pd_bp"]
    for lrow in ladder:
        if lrow["from_dd"] <= units:
            pd_bp = lrow["pd_bp"]
    merton_bp = PAR_BP - pd_bp

    # Comparables: the trading view
    comps = _world("the comparables row for segment %r collateralised by %r"
                   % (segment, claim.get("collateral_kind", "none")),
                   lambda: market.comparable(segment,
                                             claim.get("collateral_kind", "none")))
    comps_bp = comps["recovery_bp"]

    middle_bp = sorted((forecast_bp, merton_bp, comps_bp))[1]
    return forecast_bp, merton_bp, comps_bp, middle_bp


def thesis(claim, at):
    """The fund's written argument for the position it holds.

    The cost is the position's own fields over its own face; the three
    readings re-derive themselves from the worlds right here; the receipts
    are the close's exchange terms over the held face; the return is
    searched under the wall with the residue reported; the carry, the
    upside and the decision close the file.

    A record that is not a claim, the equity, a claim the fund holds no
    position on, and a date that is not the day the position was taken, are
    refused by name.
    """
    claim = _claim(claim)
    claim_id = claim["claim"]
    face = _whole(claim.get("face_cents", 0), "the face of claim %r" % (claim_id,))

    # Find the fund's position
    pos = _position(None, claim_id)  # _position handles the claim_id lookup
    if pos is None:
        raise ThesisError("the fund holds no position on claim %r" % (claim_id,))

    # The position date must match at
    dated = pos["dated"]
    if at != dated:
        raise ThesisError("claim %r's position was taken at %r, and the "
                          "thesis is asked at %r, which is not the day it "
                          "was taken" % (claim_id, dated, at))

    position_face = _whole(pos["face_cents"], "the face of position on %r"
                           % (claim_id,))
    price_bp = _whole(pos["price_bp"], "the print of position %r" % (claim_id,))
    cost_cents = position_face * price_bp // PAR_BP

    # Three readings
    fund = market.fund()
    b = book.Book.build(7)
    forecast_bp, merton_bp, comps_bp, middle_bp = _three_readings(b, claim, at)

    # Receipts from the close (scaled by position's share of the claim)
    restructuring = _world("the settlement facts", lambda: market.restructuring())
    class_receipts = _receipts(restructuring, claim_id)
    receipts_cents = class_receipts * position_face // face

    # Return search
    close = restructuring["closed"]
    months = _months_between(at, close)
    if receipts_cents <= cost_cents:
        raise ThesisError("claim %r ends under water: the close pays %d cents "
                          "of receipts against a cost of %d, and a negative "
                          "return is a refusal" % (claim_id, receipts_cents, cost_cents))

    irr_bp = _search(receipts_cents, cost_cents, months)
    pv_cents = _pv(receipts_cents, irr_bp, months)
    residue_cents = cost_cents - pv_cents

    # Carry
    carry_cents = 0  # calculated below
    fund_carry_bp = fund["carry_bp"]
    annual_cents = cost_cents * fund_carry_bp // PAR_BP
    months_held = _months_between(dated, at)
    if months_held < 0:
        raise ThesisError("the carry of claim %r is asked at %r, before the "
                          "position was even taken at %r: carry never runs "
                          "backwards" % (claim_id, at, dated))
    carry_cents = annual_cents * months_held // 12

    # Upside and decision
    view = _world("the comparables' view of segment %r collateralised by %r"
                  % (claim["segment"], claim.get("collateral_kind", "none")),
                  lambda: market.comparable(claim["segment"],
                                            claim.get("collateral_kind", "none")))
    view_bp = view["recovery_bp"]
    if price_bp >= view_bp:
        raise ThesisError("claim %r entered at %d basis points, at or above "
                          "the comparables' view of %d: the trade is unbuyable"
                          % (claim_id, price_bp, view_bp))
    upside_cents = (view_bp - price_bp) * position_face // PAR_BP
    decision = "hold" if upside_cents > carry_cents else "pass"

    return {"claim": claim_id, "at": at, "close": close, "months": months,
            "face_cents": position_face, "price_bp": price_bp, "cost_cents": cost_cents,
            "forecast_bp": forecast_bp, "merton_bp": merton_bp,
            "comparables_bp": comps_bp, "middle_bp": middle_bp,
            "receipts_cents": receipts_cents, "irr_bp": irr_bp,
            "pv_cents": pv_cents, "residue_cents": residue_cents,
            "carry_cents": carry_cents, "upside_cents": upside_cents,
            "decision": decision}


def audit(book, claims, at, close):
    """The thesis's legs, claim by claim, graded against what actually settled.

    Per debt claim of the structure: the three readings recomputed at `at`,
    the middle, the realised basis points the answer key recorded over the
    face, the gap and the grade against the fund's own tolerance. This is
    the only reader of the answer key the course allows.

    A close off the world's own, a date the asset path has no reading for,
    and worlds the machinery cannot read, are refused by name.
    """
    if close != market.CLOSE_DATE:
        raise ThesisError("the close is %r, and the audit only grades at the "
                          "world's own close date %r" % (close, market.CLOSE_DATE))

    try:
        market.asset_at(close)
    except market.DescriptError as e:
        raise ThesisError("the close date %r has no asset path reading (%s)"
                          % (close, e))

    fund = market.fund()
    tolerance_bp = fund["audit_tolerance_bp"]
    structure = claims.structure()
    rows = []
    for claim in structure:
        if claim["kind"] == "equity":
            continue
        claim_id = claim["claim"]

        # Three readings
        forecast_bp, merton_bp, comps_bp, middle_bp = _three_readings(book, claim, at)

        # Realised: the answer key
        outcome = _world("the answer key for claim %r" % (claim_id,),
                         lambda: claims.outcome(claim_id))
        received = outcome["received_cents"]
        face = claim["face_cents"]
        realised_bp = received * PAR_BP // face

        # Grade: gap against tolerance
        gap_bp = middle_bp - realised_bp
        if gap_bp < 0:
            gap_bp = -gap_bp
        grade = GRADES[0] if gap_bp <= tolerance_bp else GRADES[1]

        rows.append({"claim": claim_id, "at": at, "close": close,
                     "received_cents": received, "face_cents": face,
                     "realised_bp": realised_bp, "forecast_bp": forecast_bp,
                     "merton_bp": merton_bp, "comparables_bp": comps_bp,
                     "middle_bp": middle_bp, "tolerance_bp": tolerance_bp,
                     "gap_bp": middle_bp - realised_bp, "grade": grade})
    return tuple(rows)


if __name__ == "__main__":
    import book as book_module
    import claims as market

    fund = market.fund()
    held = fund["positions"][0]
    structure = market.structure()
    print("the fund's thesis, the argument the whole course writes:")
    for record in structure:
        try:
            got = thesis(record, held["dated"])
            print("  %-9s at %s: triplet %d/%d/%d, middle %d, receipts %d,"
                  % (got["claim"], got["at"], got["forecast_bp"],
                     got["merton_bp"], got["comparables_bp"], got["middle_bp"],
                     got["receipts_cents"]))
            print("              return %d bp with residue %d, carry %d,"
                  " upside %d -> %s"
                  % (got["irr_bp"], got["residue_cents"], got["carry_cents"],
                     got["upside_cents"], got["decision"]))
        except ThesisError as refused:
            print("  %-9s refused: %s" % (record["claim"], refused))
    print("the audit, against what actually settled:")
    b = book_module.Book.build()
    for row in audit(b, market, market.ENTRY_DATE, market.CLOSE_DATE):
        print("  %-9s middle %d, realised %d, gap %+d -> %s"
              % (row["claim"], row["middle_bp"], row["realised_bp"],
                 row["gap_bp"], row["grade"]))