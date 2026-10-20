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
    raise NotImplementedError("stage 5: implement three()")


def spread(reading):
    """What each pair of the three readings leaves, signed, in basis points.

    `forecast_merton_bp` is the forecast less the Merton reading;
    `forecast_comparables_bp` the forecast less the comparables; and
    `merton_comparables_bp` the Merton less the comparables. The three gaps
    are signed: a leg that sits below another answers the negative it is.

    A record that is not a `THREE_KEYS` record is refused by name.
    """
    raise NotImplementedError("stage 5: implement spread()")

