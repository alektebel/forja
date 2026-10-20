"""claims.py — the fund's side of the trade: one borrower's distress, as data.

Provided, frozen, and never written by the course. The sister book of the bank's
`book.py`: where the bank recorded what it PROVISIONED for, this module records
what the MARKET priced and the parties eventually SETTLED. It holds one
borrower's whole capital structure — the claims ranked in the waterfall, the
quotes the market gave at the date the fund looked and the date the
restructuring closed, the distressed exchange the parties settled, the Merton
inputs the identity books, a table of comparables, the fund's own facts, and the
world's own answer key: the realised outcome per claim — what the holder
ACTUALLY received at the close, derived from the restructuring facts.

It holds six kinds of thing.

* **The capital structure** — four claims of one borrower (`Berthline
  Industrial Holdings`), ranked by kind in `CLASSES` order: a senior secured
  term loan whose collateral is the same asset class the bank's corporate book
  lends against, the senior unsecured notes the fund buys, the subordinated
  bonds an insurer holds, and the equity beneath them.
* **The quotes** — every debt claim, priced in basis points of par at
  `ENTRY_DATE` and at `CLOSE_DATE`, including the sub's deep-distress print the
  fund priced and never bought.
* **The restructuring facts** — the exchange's ballots (holders by name, tender
  or hold, and one cash-asking ballot refused by name), the new paper with its
  issue price and the maturity extension that faces it, the close's own
  proceeds, and the absolute-priority breaks the parties agreed: each break
  names the class it paid, the cents it paid it, the line ahead of which it was
  paid, and the priority rule it bent.
* **The Merton inputs** — the borrower's asset value and its monthly path in
  integer cents, the volatility bands tabulated so no float ever enters, a PD
  ladder the distance maps through, the debt level and the drift per borrower.
* **The comparables** — seven defaulted credit segments with their realised
  recovery multiples in basis points of par, the trading view the fund
  underwrites on.
* **The fund's facts** — the carry cost in basis points a year, the cash
  account, the dates the fund acts at, the underwriting hurdle, the wall of the
  return search, and the position the fund holds (`The Fund` is also a ballot
  holder on the instrument it bought).

The realised outcome is the answer key and a stage that simply reads it is a
stage that learned nothing — that is why `outcome` is booked into its own
counter in `stats()`, and why every check counts the asks before and after.

Nothing here reads a clock and nothing here is random: the same tuple of rows,
twice, answers equal records, equal records and equal counters.
"""

MARKET_VERSION = "DD-1.0"

CLAIM_KEYS = ("claim", "borrower", "kind", "face_cents", "owner", "segment",
              "collateral_kind", "maturity")

#: The waterfall's own order. A bond is a bond because of where it sits.
CLASSES = ("senior-secured", "senior-unsecured", "subordinated", "equity")

#: The kinds that ride the waterfall with a par to recover. Equity rides no par.
DEBT_CLASSES = ("senior-secured", "senior-unsecured", "subordinated")

PAR_BP = 10000

#: The date the market priced the sheet, and the date the parties settled.
ENTRY_DATE = "2033-01-31"

CLOSE_DATE = "2033-09-30"

QUOTE_KEYS = ("claim", "dated", "price_bp")

BALLOT_KEYS = ("holder", "claim", "face_cents", "vote")

#: The votes the exchange accepts, and the one it refuses by name.
VOTES = ("tender", "hold", "cash")

BREAK_KEYS = ("paid_to", "paid_cents", "ahead_of", "rule")

RESTRUCTURING_KEYS = ("opened", "closed", "proceeds_cents", "breaks", "ballots",
                      "paper", "issue_bp", "old_maturity", "new_maturity", "faces")

FACES_KEYS = ("claim", "face_cents")

OUTCOME_KEYS = ("claim", "received_cents", "on", "moves")

MERTON_KEYS = ("borrower", "debt_cents", "band_bp", "drift_bp")

BAND_KEYS = ("name", "low_bp", "high_bp")

LADDER_KEYS = ("from_dd", "pd_bp")

FUND_KEYS = ("cash_cents", "carry_bp", "hurdle_bp", "max_rate_bp", "acts_at",
             "positions", "audit_tolerance_bp")

POSITION_KEYS = ("claim", "dated", "price_bp", "face_cents")

CARRY_MONTHS = 12

CARRY_SCALE = 10000

#: The scale a distance is carried in — the same fixed-point scale as the bank's.
DD_SCALE = 10000

#: The identity's own borrower, and what the debt table holds beside it.
_BORROWER = "Berthline Industrial Holdings"

_CLAIMS = (
    ("BL-1L", _BORROWER, "senior-secured", 40000000, "Berthline Facility Agent",
     "corporate", "equipment", "2035-03-31"),
    ("BL-UNSEC", _BORROWER, "senior-unsecured", 45000000, "widely held",
     "corporate", "none", "2034-06-30"),
    ("BL-SUB", _BORROWER, "subordinated", 18000000, "Meridian Assurance Co",
     "corporate", "none", "2036-03-31"),
    ("BL-EQ", _BORROWER, "equity", 25000000, "Berthline Sponsor LP",
     "corporate", "none", "open"),
)

#: The sheet: every debt claim priced at the date the fund looked and at the
#: close. The sub's 60 is the print the fund priced and walked away from —
#: 0.6 cents for a par is one the return search's wall refuses to carry.
_QUOTES = (
    ("BL-1L", ENTRY_DATE, 9200), ("BL-1L", CLOSE_DATE, 9750),
    ("BL-UNSEC", ENTRY_DATE, 1800), ("BL-UNSEC", CLOSE_DATE, 6400),
    ("BL-SUB", ENTRY_DATE, 60), ("BL-SUB", CLOSE_DATE, 2600),
    ("BL-EQ", ENTRY_DATE, 400), ("BL-EQ", CLOSE_DATE, 900),
)

#: The ballots of the only exchange: a majority of the unsecured's face tendered
#: into `paper`, one holder's 7.5 million asks for cash and is told no, and the
#: fund itself is in the ballot on the stake it bought.
_BALLOTS = (
    ("Alderwood Advisors", "BL-UNSEC", 13000000, "tender"),
    ("Cranebay Credit", "BL-UNSEC", 15500000, "tender"),
    ("The Fund", "BL-UNSEC", 9000000, "tender"),
    ("Ostrander Holdings", "BL-UNSEC", 7500000, "cash"),
)

#: The exchange's terms: paper given for paper at a face the holder kept, at an
#: issue price of `issue_bp` of par (the 1000 basis points the tenderer left on
#: the table against a market at 1800), and a maturity pushed out fifty-four
#: months — `add_months(old, 54) == new`.
_ISSUE_BP = 9000

_OLD_MATURITY = "2034-06-30"

_NEW_MATURITY = "2038-12-30"

_PAPER = "BL-2027-notes"

#: The break the parties agreed: the insurer's keep-whole premium, paid by
#: decree to the subordinated bonds ahead of the senior unsecured's par, whose
#: right to it the absolute priority rule bent.
_BREAK = ("BL-SUB", 3600000, "BL-UNSEC",
          "absolute priority: the insurer's keep-whole premium paid ahead of the "
          "senior unsecured's par claim")

#: The close's own proceeds, and the face each debt claim rides that close
#: with — the waterfall's own par, in `CLASSES` order. Equity rides no par and
#: so no row: what the waterfall left it is what the decree did not rescue.
_PROCEEDS_CENTS = 48000000

_FACES = (
    ("BL-1L", 40000000),
    ("BL-UNSEC", 45000000),
    ("BL-SUB", 18000000),
)

_RESTRUCTURING_OPENED = "2033-02-28"

#: The Merton inputs, borrower by borrower: the debt the identity books, the
#: volatility band the band table tabulates, and the drift the model expects.
_MERTON = (
    (_BORROWER, 103000000, 3200, -2200),
    ("Calderman Marine", 34000000, 1500, 400),
    ("Arquette Materials", 12000000, 5400, -3500),
)

#: The tabulated volatility bands. A `band_bp` that is not one of their upper
#: bounds is not a band the world books, and the distance refuses it.
_BANDS = (
    ("calm", 0, 1500),
    ("normal", 1500, 3200),
    ("stressed", 3200, 5400),
)

#: The PD ladder the distance maps through, walked like the book's buckets:
#: the row whose `from_dd` is the greatest lower bound of the distance answers;
#: a distance below the first or above the last is refused by name.
_PD_LADDER = (
    (-2000, 10000),
    (0, 8000),
    (800, 7000),
    (2000, 5400),
    (3600, 3400),
    (6400, 1600),
    (10000, 400),
    (16000, 0),
)

#: The borrower's asset value, month by month, in integer cents: the path the
#: model walks in to and out of the trade. The pool at the close is the
#: collateral's own realisation, and is not the path's last value.
_ASSET_PATH = (
    ("2032-10-31", 118000000),
    ("2032-11-30", 116000000),
    ("2032-12-31", 113000000),
    ("2033-01-31", 104000000),
    ("2033-02-28", 96000000),
    ("2033-03-31", 90000000),
    ("2033-04-30", 87000000),
    ("2033-05-31", 85000000),
    ("2033-06-30", 83000000),
    ("2033-07-31", 81000000),
    ("2033-08-31", 79000000),
    ("2033-09-30", 77000000),
)

#: The trading view: similar defaulted credit segments and the recoveries they
#: actually paid, in basis points of par, with the deals behind each row.
_COMPARABLES = (
    ("corporate", "none", 2600, 4),
    ("corporate", "equipment", 3100, 3),
    ("corporate", "receivables", 2200, 2),
    ("mortgage", "property", 6900, 5),
    ("sme", "receivables", 3300, 2),
    ("consumer", "none", 300, 7),
    ("credit-card", "none", 500, 9),
    ("leasing", "equipment", 2400, 3),
)

_CASH_CENTS = 200000000

_CARRY_BP = 1000

_HURDLE_BP = 1900

_MAX_RATE_BP = 60000

_AUDIT_TOLERANCE_BP = 4500

_ACTS_AT = (ENTRY_DATE, CLOSE_DATE)

#: The fund's own book: the stake it bought on the sheet's print — nine million
#: of the unsecured's forty-five — and nothing else. It tendered (see the
#: ballots) and holds the new paper.
_POSITION = ("BL-UNSEC", ENTRY_DATE, 1800, 9000000)

_LOG_STATS = ("structure", "ballots", "restructuring", "merton", "comparables",
              "quotes", "asset", "outcome")

_CALL_STATS = {
    "structure": "structure",
    "ballots": "ballots",
    "restructuring": "restructuring",
    "merton": "merton",
    "comparable": "comparables",
    "quote": "quotes",
    "quotes": "quotes",
    "asset_at": "asset",
    "fund": "structure",
    "outcome": "outcome",
}

CLAIMS_ERROR = "claims: "


class DescriptError(ValueError):
    """The world's refusal: a claim the structure does not hold, a price off
    the quote sheet, an input outside a tabulated band.

    It names the offender — the claim, the date, the band — because a market
    one cannot describe must say what was asked for rather than answer a
    number nobody can trade on.
    """


def _log_ask(what):
    """One line of the ledger: what was asked, and for whom."""
    _LOG.append((_CALL_STATS.get(what, what), what))


def structure():
    """The capital structure: `CLAIM_KEYS` records, one per claim, in kind order.

    The claim records are the same shape the stages read, the borrower naming
    the Merton row and the segment naming the comparables row. The fund's own
    facts are read here as well — the structure is what the fund trades in.
    """
    _log_ask("structure")
    return tuple(dict(zip(CLAIM_KEYS, row)) for row in _CLAIMS)


def fund():
    """The fund's facts, and the position it holds, as one record.

    The carry cost, the hurdle, the return search's wall, the dates the fund
    acts at, its cash account and its audit tolerance are all data here; the
    positions are `POSITION_KEYS` rows — the stake bought, when, at what price.
    """
    _log_ask("fund")
    return {"cash_cents": _CASH_CENTS, "carry_bp": _CARRY_BP,
            "hurdle_bp": _HURDLE_BP, "max_rate_bp": _MAX_RATE_BP,
            "acts_at": tuple(_ACTS_AT),
            "positions": (dict(zip(POSITION_KEYS, _POSITION)),),
            "audit_tolerance_bp": _AUDIT_TOLERANCE_BP}


def quote(claim, dated):
    """One printed price, by claim and date, or a refusal naming either.

    The sheet holds two dates per claim: the one the fund looked and the one
    the restructuring closed. A pair off the sheet is refused by name because
    a price a market never printed would carry a thesis on nothing.
    """
    _log_ask("quote")
    for row in _QUOTES:
        if row[0] == claim and row[1] == dated:
            return dict(zip(QUOTE_KEYS, row))
    raise DescriptError(CLAIMS_ERROR + ("the sheet carries no quote for claim %r "
                                        "dated %r" % (claim, dated)))


def quotes(claim):
    """Every printed price of one claim, in the sheet's own order, named."""
    _log_ask("quotes")
    rows = [dict(zip(QUOTE_KEYS, row)) for row in _QUOTES if row[0] == claim]
    if not rows:
        raise DescriptError(CLAIMS_ERROR + ("the sheet carries no quotes for "
                                            "claim %r" % (claim,)))
    return tuple(rows)


def ballots():
    """The exchange's ballots: `BALLOT_KEYS` rows, holder by name, in order.

    The whole face of the instrument the exchange touches is covered by these
    rows — tendered, held and cash-asking — which is what lets the terms be
    computed from the record alone.
    """
    _log_ask("ballots")
    return tuple(dict(zip(BALLOT_KEYS, row)) for row in _BALLOTS)


def restructuring():
    """The restructuring facts as one record — `RESTRUCTURING_KEYS`, in order.

    The close's proceeds, the agreed breaks by name, the ballots, and the
    exchange's own terms: the paper's name, the price it was issued at, the
    maturity it left and the maturity it was granted. The stages read the
    record and recompute; the record is what the parties actually settled.
    """
    _log_ask("restructuring")
    return {"opened": _RESTRUCTURING_OPENED, "closed": CLOSE_DATE,
            "proceeds_cents": _PROCEEDS_CENTS,
            "breaks": (dict(zip(BREAK_KEYS, _BREAK)),),
            "ballots": tuple(dict(zip(BALLOT_KEYS, row)) for row in _BALLOTS),
            "paper": _PAPER, "issue_bp": _ISSUE_BP,
            "old_maturity": _OLD_MATURITY,
            "new_maturity": _NEW_MATURITY,
            "faces": tuple(dict(zip(FACES_KEYS, row)) for row in _FACES)}


def merton(borrower):
    """The identity's Merton row for a borrower, or a refusal naming one.

    The row carries the debt the identity books, the volatility band it books
    the borrower at, and the drift the model expects — `MERTON_KEYS`, in order.
    A borrower the debt table does not hold is refused by name: a distance
    cannot be carried by an enterprise nobody measured.
    """
    _log_ask("merton")
    for row in _MERTON:
        if row[0] == borrower:
            return dict(zip(MERTON_KEYS, row))
    raise DescriptError(CLAIMS_ERROR + ("the debt table holds no borrower %r; it "
                                        "holds %r" % (borrower,
                                                      tuple(row[0] for row in _MERTON))))


def asset_at(dated):
    """The path's asset value at one of its month ends, or a refusal naming one.

    The path is the world's own measurement: twelve month ends, oldest first.
    A date between the rows, or before the first, or after the last, has no
    reading — the answer is a refusal naming the date, never a neighbour's
    value or an interpolation.
    """
    _log_ask("asset_at")
    for row in _ASSET_PATH:
        if row[0] == dated:
            return row[1]
    raise DescriptError(CLAIMS_ERROR + ("the asset path has no reading for %r; it "
                                        "runs %r..%r" % (dated, _ASSET_PATH[0][0],
                                                         _ASSET_PATH[-1][0])))


def asset_path():
    """The path itself, month end by month end, oldest first."""
    _log_ask("asset_at")
    return tuple(_ASSET_PATH)


def comparable(segment, collateral_kind):
    """One row of the comparables table, by segment and collateral, or a refusal.

    The row is the trading view — basis points of par, and the deals behind it.
    A pair the table does not hold is refused by name: the fund underwrites on
    rows it can name, never on a guess.
    """
    _log_ask("comparable")
    for row in _COMPARABLES:
        if row[0] == segment and row[1] == collateral_kind:
            return {"segment": row[0], "collateral_kind": row[1],
                    "recovery_bp": row[2], "deals": row[3]}
    raise DescriptError(CLAIMS_ERROR + ("the comparables hold no %r claims collateralised "
                                        "by %r" % (segment, collateral_kind)))


def bands():
    """The tabulated volatility bands, `BAND_KEYS` order, low to high."""
    _log_ask("merton")
    return tuple(dict(zip(BAND_KEYS, row)) for row in _BANDS)


def ladder():
    """The PD ladder the distance maps through, `LADDER_KEYS` order.

    The mapping is data: one row per step of the distance, the same walk the
    bank's own bucket table takes. Refusals at the ends are the world's, not a
    stage's, so every stage that walks it walks the same ends.
    """
    _log_ask("merton")
    return tuple(dict(zip(LADDER_KEYS, row)) for row in _PD_LADDER)


def outcome(claim):
    """The world's answer key for one claim — what the holder received at the close.

    The realised outcome, derived from the restructuring facts: the cents the
    class received, the date they arrived, and the moves that paid them. A
    stage reads it to grade a thesis against what the world recorded, never to
    learn a recovery rate from — the modelling stages reproduce the close from
    the facts below it, and the stats ledger counts every ask of this door.
    """
    _log_ask("outcome")
    for row in _OUTCOMES:
        if row["claim"] == claim:
            return {"claim": row["claim"], "received_cents": row["received_cents"],
                    "on": row["on"], "moves": row["moves"]}
    raise DescriptError(CLAIMS_ERROR + ("the answer key holds no outcome for claim "
                                        "%r" % (claim,)))


_OUTCOMES = (
    {"claim": "BL-1L", "received_cents": 40000000, "on": CLOSE_DATE,
     "moves": ("waterfall",)},
    {"claim": "BL-UNSEC", "received_cents": 38150000, "on": CLOSE_DATE,
     "moves": ("exchange", "waterfall")},
    {"claim": "BL-SUB", "received_cents": 3600000, "on": CLOSE_DATE,
     "moves": ("agreement",)},
    {"claim": "BL-EQ", "received_cents": 0, "on": CLOSE_DATE, "moves": ()},
)

_LOG = []


def stats():
    """The ledger, recounted: what was asked of this world, by family.

    `outcome` is its own family precisely so a check can prove a stage asked
    for nothing but the facts it was entitled to — the answer key is the
    world's, and a stage that silently reads it learned nothing. `stats` does
    not log itself, so two recounts of an untouched world answer equal.
    """
    return {family: len([line for line in _LOG if line[0] == family])
            for family in _LOG_STATS}
