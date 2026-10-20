"""Distressed Debt Investing From Scratch — stage 5: The three values that disagree.

The fund underwrites a claim with three readings, and they never agree. The
first reads the bank's actuals (stage 3's walk): what the defaulted book on
the segment collected, haircutted and discounted — the recovery-based view.
The second reads the identity (stage 4's distance): the equity cushion over
the debt, the ladder it maps to, and the recovery the model expects the par
to be worth — the Merton-based view. The third reads the market (the
comparables table): what similar defaulted segments actually paid, in basis
points of par — the trading view.

`three(book, claim, at)` answers all three plus one more number the course
underwrites on: the MIDDLE of the three. A fund that underwrites on its best
case pays too much, and one that underwrites on its worst case never buys —
the consensus of two out of three views is the reading the trade clears or
fails, so the stage answers it in the record rather than making every later
stage re-derive it from the three legs.

`spread(...)` answers what each pair of readings leaves between itself and
the other — signed, in basis points of par. The gaps are the trade: the fund
sits between the readings, buys under the middle one's line at a discount to
the market's, and the check pins the gaps to the hundredth the divisions
leave, because a spread of one basis point at nine million of face is nine
hundred cents and nobody should lose them by rounding.

    THREE_KEYS                    the six fields of the three readings, in order
    SPREAD_KEYS                   the five fields of the pairwise gaps, in order
    ValuationError                the refusal this stage raises
    three(book, claim, at)        -> THREE_KEYS: the readings, and the middle
    spread(reading)               -> SPREAD_KEYS: what each pair leaves

DESIGN DECISION — why does the stage answer the middle rather than the three
alone?
Because the middle IS the underwriting decision, hiding it among three legs
keeps the decision implicit: every downstream stage would re-derive it,
mis-deriving it the first time a tie or a reordering arrives. The record
answers forecast, Merton, comparables and `middle_bp` — four numbers, one
claim, one date — and the check pins the middle to the sorted list's own
centre, so a stage that "decided" on the mean (a kind of average floats love
and integers refuse) or the best case shows as a disagreement with the
sorting.

DESIGN DECISION — why are the gaps signed rather than absolute?
Because direction is the information: the forecast sits under the Merton
reading and the Merton under the comparables — a borrower in the world's
actuals has been paid less than the model expects, and the model less than the
market pays for similar distress. Signed gaps turn that into arithmetic:
`forecast_merton_bp` is how far the actuals trail the model, and a check pins
each to its sign, so a walk that got the direction backwards shows immediately.

DESIGN DECISION — why does the Merton leg come from the entry date's asset
value, and refuse elsewhere on the path?
Because the reading is the fund's as of the day it decides: the asset path's
month end at `at` and the borrower's booked debt and band give the distance,
the ladder gives the probability, and the recovery is what the par is worth
when the borrower is not fully wiped out. A date off the path has no asset
reading — the world refuses it, and so does this stage — and a distance the
ladder cannot walk to (the close's asset value sinks the distance past even
the ladder's worst row) means the model has no answer for that borrower on
that day, which is a refusal and not a zero.

DESIGN DECISION — why is the equity refused and not priced?
Because the equity does ride a price on the sheet and a comparables row below
it, but no par: a recovery rate has no face to apply to, and the fund's
three-reading discipline is a debt discipline. Pricing the sponsor's claim by
the same machinery would answer a number that looks like the others and
cannot be defended like them — so the stage refuses by name, and the equity
rides the course's decisions only through the waterfall (stage 1) it sits
beneath.

DESIGN DECISION — why does the stage re-walk the bank's actuals instead of
importing stage 3's answer?
Because stages stand alone in this course: a stage reads the WORLD, never
another stage's output, and the three-reading record must be reproducible by
anyone holding the book and the claim — which is also what makes it
auditable. The walk is the same haircut-and-step arithmetic, written once
here, and the check pins it against its own re-walk, so the two files agree
or the course says so loudly.

TODO: implement `ValuationError`, `three` and `spread` in this file: the
three readings from the bank's actuals, the identity and the comparables
table; the middle of the three; and the signed gaps each pair leaves.

    The request is refused by name when the claim record carries no `kind`,
    `segment`, `collateral_kind` or `borrower`, when the kind is `equity`,
    when the identity books no borrower under the claim's name, when the
    `at` is not a date the asset path has a reading for, and when the
    comparables hold no row for the claim's segment and collateral. The
    spread is refused by name when the record it is asked to spread is not
    a `THREE_KEYS` record.
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

import rules
import dates

PAR_BP = 10000

THREE_KEYS = ("claim", "at", "forecast_bp", "merton_bp", "comparables_bp",
              "middle_bp")

SPREAD_KEYS = ("claim", "at", "forecast_merton_bp", "forecast_comparables_bp",
               "merton_comparables_bp")


class ValuationError(ValueError):
    """The refusal this stage raises: a claim the three views cannot price.

    It names the offender — the claim, the borrower, the date, the segment
    and collateral the comparables do not carry — because a valuation the
    world cannot underwrite must say what it was asked for rather than answer
    three numbers and a middle nobody bought.
    """




def _months_between(start, end):
    """The whole months from `start` to `end`, the calendar's clamping honoured.

    The stage-3 walk's own month count: a day on the day itself is zero months
    away, and a start on a day the target month does not have still answers
    the floor `dates.add_months` puts under it.
    """
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months


def _world(what, call):
    """The world's own answer for `what`, wrapped into this stage's refusal."""
    try:
        return call()
    except market.DescriptError as refused:
        raise ValuationError("the world refuses %s (%s)" % (what, refused))


def _claim(claim):
    """The claim the three readings answer, refused by name when it cannot be one."""
    if not isinstance(claim, dict):
        raise ValuationError("the claim is a %s, not a claim record"
                             % (type(claim).__name__,))
    for field in ("claim", "kind", "segment", "collateral_kind", "borrower"):
        if field not in claim:
            raise ValuationError("the claim carries no %r" % (field,))
    if claim["kind"] == "equity":
        raise ValuationError("claim %r is the equity, and no recovery reading "
                             "prices a claim with no par"
                             % (claim["claim"],))
    return claim


def _recovery_walk(book, segment, at):
    """The bank's actuals on one segment: haircutted, discounted, over the par.

    The same haircut-and-step walk the recovery stage runs, restated here so
    that no stage reads another stage's output: every defaulted loan on the
    segment with a recovery row counted at its own rate, the collateral rows
    cut by their own loan's collateral kind, and every row discounted to
    `at` the distance of `months_between(at, row_date)` truncating steps.
    """
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
        raise ValuationError("the book's %r segment has no defaulted loan with "
                             "recoveries to read, so the recovery-based view "
                             "has nothing to stand on" % (segment,))
    return discounted * PAR_BP // par


def _merton_recovery(claim, at):
    """The recovery the identity leaves the par, from the distance at `at`.

    The asset path's reading at `at`, the borrower's booked debt and band,
    the distance in whole band units, the world's own ladder — and the
    recovery is what the par is worth when the walk does not end at the
    worst row. Every refusal is the world's own and is re-raised naming the
    borrower the claim named.
    """
    borrower = claim["borrower"]
    row = _world("debt table row of borrower %r" % (borrower,),
                 lambda: market.merton(borrower))
    asset = _world("the asset path at %r" % (at,), lambda: market.asset_at(at))
    debt = row["debt_cents"]
    units = (asset - debt) * market.DD_SCALE * market.DD_SCALE \
        // (asset * row["band_bp"])
    pd_bp = _world("the PD ladder at distance %d for borrower %r"
                   % (units, borrower), lambda: _to_pd(units))
    return PAR_BP - pd_bp


def _to_pd(units):
    """The ladder walked by greatest lower bound, ended where the world ends it."""
    if units < market.ladder()[0]["from_dd"] or units > market.ladder()[-1]["from_dd"]:
        raise market.DescriptError("the distance %d is outside the ladder's own "
                                   "rows, and no probability is invented beyond "
                                   "them" % (units,))
    answer = market.ladder()[0]["pd_bp"]
    for row in market.ladder():
        if row["from_dd"] <= units:
            answer = row["pd_bp"]
    return answer


def three(book, claim, at):
    """The three readings of one claim, and the middle the fund underwrites on.

    The recovery-based leg reads the bank's own defaulted book on the claim's
    segment, haircutted and discounted to `at` at each loan's own rate. The
    Merton-based leg reads the asset path at `at`, the borrower's booked debt
    and band, and the world's own ladder: the distance the identity answers,
    the probability it walks to, and the recovery the par is left with. The
    comparables-based leg reads the trading table's row for the claim's
    segment and collateral. The middle is the sorted three's own centre.

    A claim of kind `equity`, a record the book and the world cannot read, a
    date off the asset path, and a segment and collateral the comparables do
    not carry, are refused by name.
    """

    claim = _claim(claim)
    forecast_bp = _recovery_walk(book, claim["segment"], at)
    merton_bp = _merton_recovery(claim, at)
    pair = (claim["segment"], claim["collateral_kind"])
    comps_bp = _world("the comparables row for %r collateralised by %r" % pair,
                      lambda: market.comparable(claim["segment"],
                                                claim["collateral_kind"]))["recovery_bp"]
    middle_bp = sorted((forecast_bp, merton_bp, comps_bp))[1]
    return {"claim": claim["claim"], "at": at, "forecast_bp": forecast_bp,
            "merton_bp": merton_bp, "comparables_bp": comps_bp,
            "middle_bp": middle_bp}


def spread(reading):
    """What each pair of the three readings leaves, signed, in basis points.

    `forecast_merton_bp` is the forecast less the Merton reading;
    `forecast_comparables_bp` the forecast less the comparables; and
    `merton_comparables_bp` the Merton less the comparables. The three gaps
    are signed: a leg that sits below another answers the negative it is.

    A record that is not a `THREE_KEYS` record is refused by name.
    """

    if not isinstance(reading, dict):
        raise ValuationError("the reading is a %s, not a THREE_KEYS record"
                             % (type(reading).__name__,))
    for field in ("claim", "at", "forecast_bp", "merton_bp", "comparables_bp"):
        if field not in reading:
            raise ValuationError("the reading carries no %r" % (field,))
    forecast = reading["forecast_bp"]
    merton = reading["merton_bp"]
    comps = reading["comparables_bp"]
    return {"claim": reading["claim"], "at": reading["at"],
            "forecast_merton_bp": forecast - merton,
            "forecast_comparables_bp": forecast - comps,
            "merton_comparables_bp": merton - comps}

if __name__ == "__main__":
    import book as book_module

    b = book_module.Book.build(7)
    structure = market.structure()
    print("the three readings, side by side, and what each pair leaves:")
    print("  claim          forecast  merton  comps  middle")
    for record in structure:
        if record["kind"] == "equity":
            continue
        reading = three(b, record, market.ENTRY_DATE)
        gaps = spread(reading)
        print("  %-14s %-8d %-6d %-6d %-6d   f-m %+d, f-c %+d, m-c %+d"
              % (reading["claim"], reading["forecast_bp"], reading["merton_bp"],
                 reading["comparables_bp"], reading["middle_bp"],
                 gaps["forecast_merton_bp"], gaps["forecast_comparables_bp"],
                 gaps["merton_comparables_bp"]))
