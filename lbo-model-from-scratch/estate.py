"""estate.py — Coyote Industrial Group, its five years, its market, and the memo.

Provided, frozen, and never written by a stage. This module is the whole deal:
the target the sponsor bought whole, the five-year path the company actually
took, the financing market that terms the debt, the covenant treaty that
disciplines it, and the sponsor's own memo about how it all ended. Every stage
reads this world and answers one slice of the deal; the estate is what the
slice is held against.

Money is an integer count of cents, rates and multiples are integer counts of
basis points (`10000` basis points are one whole turn of EBITDA or one whole
rate of interest), every key that carries money says `_cents` and every key
that carries a rate says `_bp`. No number here is a float. Dates are ISO
strings through `dates.py`; the estate owns exactly the dates its walk walks,
and `place()` refuses a date it does not hold.

The five things the deal is made of:

* **The facts at the entry date** (`2026-06-30`) — twelve million shares at
  six hundred thousand cents each, entry EBITDA of twelve million dollars'
  worth of cents on sixty million of revenue, entry working capital, and the
  minimum cash the balance sheet must always~carry.
* **The five-year path the company actually took** — revenue, EBITDA,
  depreciation, capex split maintenance and growth, working capital, the cash
  taxes the policy's own bands charged, and the free cash flow that fell out.
  The model cannot argue with this line: a build that does not land on it is
  a different company.
* **The financing market** — four tranches (a revolver left undrawn at the
  close, a term loan A with four years of mandatory amortisation, a term loan
  B that sweeps half the year's free cash above the floor, and a mezzanine
  the contract never lets prepay), their rates and day counts, the four fee
  rows, and the multiples each side of the table quotes five of.
* **The covenant treaty** — a net-leverage maintenance ladder that steps
  (tight through the squeeze year the sponsor cures through, amended back up
  for year four, tightest at the exit), an incurrence test for any new draw,
  and the sponsor's cure cheque of one hundred fifty million, wired in year
  three the moment the pre-cure test breaks.
* **The actual debt path and the memo** — the ledger of what each tranche
  actually opened with, charged, amortised, swept, cured and closed with,
  year by year. The ledger is the answer key: a stage that recomputes the
  waterfall from the terms and the path above lands on it exactly, and a
  stage that answers anything else has built a different deal.

The answer-key accessors — `debt_row`, `state_end`, `state_for_test`,
`distribution` — recount that ledger, and every ask of them joins `stats()`:
a check proves this way what a stage looked at, so a stage that recomputes a
mechanism can prove it never had to read the answer instead.
"""

import dates

ESTATE_VERSION = "LBO-1.0"

COMPANY = "coyote industrial group"

ENTRY_DATE = "2026-06-30"

YEAR_ENDS = ("2027-06-30", "2028-06-30", "2029-06-30", "2030-06-30", "2031-06-30")

EXIT_DATE = YEAR_ENDS[-1]

DEAL_KEYS = ("entry_multiple_bp", "exit_multiple_bp")

TRANCHE_KEYS = ("name", "kind", "commitment_cents", "drawn_cents", "rate_bp",
                "basis", "amort_cents", "amort_years", "sweep_bp", "term_years",
                "prepayable")

TRANCHE_ORDER = ("revolver", "term-loan-a", "term-loan-b", "mezzanine")

FEE_KEYS = ("name", "basis", "bp")

FEE_BASES = ("purchase", "drawn")

ACTUALS_KEYS = ("year", "year_end", "revenue_cents", "ebitda_cents", "depreciation_cents",
                "capex_maintenance_cents", "capex_growth_cents", "working_capital_cents",
                "tax_cents", "free_cash_flow_cents")

DEBT_ROW_KEYS = ("tranche", "year", "year_end", "opening_cents", "interest_cents",
                 "mandatory_amort_cents", "draw_cents", "repay_cents", "sweep_cents",
                 "cure_cents", "mandatory_close_cents", "closing_cents")

STATE_KEYS = ("balances", "cash_cents")

SHARES_OUTSTANDING = 12_000_000

OFFER_CENTS_PER_SHARE = 600_000

ENTRY_EBITDA_CENTS = 1_200_000_000

ENTRY_REVENUE_CENTS = 6_000_000_000

ENTRY_WORKING_CAPITAL_CENTS = 480_000_000

MIN_CASH_CENTS = 200_000_000

ENTRY_MULTIPLE_BP = 60000

EXIT_MULTIPLE_BP = 62500

EQUITY_CHEQUE_CENTS = 2_232_500_000

#: The multiples each side of the table quotes. A purchase at a multiple the
#: seller never offered, or an exit at one the market never showed, has no
#: record here and no value to strike.
ENTRY_QUOTES = (57500, 60000, 62500, 65000, 67500)

EXIT_QUOTES = (50000, 55000, 60000, 62500, 65000)

TAX_TOP_CENTS = 600_000_000

TAX_LOW_BP = 2000

TAX_HIGH_BP = 2800

#: The maintenance ladder, by year end: net debt below the year's EBITDA, in
#: basis points. The squeeze year bites hardest (the sponsor cures through
#: `2029`), the amendment grants `2030` back to where it started, and the
#: exit year is the tightest test of all.
NET_LEVERAGE_LIMITS = {
    "2027-06-30": 41500,
    "2028-06-30": 40000,
    "2029-06-30": 29000,
    "2030-06-30": 40000,
    "2031-06-30": 27000,
}

#: Any draw the sponsor asks to incur has to keep net leverage under this,
#: too — a looser test than the maintenance ladder's, for money the sponsor
#: has not drawn yet.
INCURRENCE_BP = 42500

CURE_MONEY_CENTS = 150_000_000

CURE_YEAR = 3

#: The cure cheque lands top-down: revolver first, then the amortising term
#: loan, then the sweeping one. It never lands on the mezzanine.
CURE_ORDER = ("revolver", "term-loan-a", "term-loan-b")

_YEARBOOK = {
    1: dict(revenue_cents=6_300_000_000, ebitda_cents=1_292_000_000,
            depreciation_cents=360_000_000, capex_maintenance_cents=330_000_000,
            capex_growth_cents=170_000_000, working_capital_cents=504_000_000),
    2: dict(revenue_cents=6_615_000_000, ebitda_cents=1_425_000_000,
            depreciation_cents=360_000_000, capex_maintenance_cents=340_000_000,
            capex_growth_cents=160_000_000, working_capital_cents=528_000_000),
    3: dict(revenue_cents=6_945_000_000, ebitda_cents=1_562_000_000,
            depreciation_cents=360_000_000, capex_maintenance_cents=350_000_000,
            capex_growth_cents=150_000_000, working_capital_cents=552_000_000),
    4: dict(revenue_cents=6_250_000_000, ebitda_cents=1_180_000_000,
            depreciation_cents=360_000_000, capex_maintenance_cents=310_000_000,
            capex_growth_cents=40_000_000, working_capital_cents=584_000_000),
    5: dict(revenue_cents=6_884_000_000, ebitda_cents=1_543_000_000,
            depreciation_cents=360_000_000, capex_maintenance_cents=330_000_000,
            capex_growth_cents=170_000_000, working_capital_cents=564_000_000),
}

_TERMS = {
    "revolver": dict(kind="revolver", commitment_cents=1_800_000_000, drawn_cents=0,
                     rate_bp=375, basis="thirty-360", amort_cents=0, amort_years=0,
                     sweep_bp=0, term_years=5, prepayable="repay"),
    "term-loan-a": dict(kind="term", commitment_cents=2_100_000_000, drawn_cents=2_100_000_000,
                        rate_bp=475, basis="actual-365", amort_cents=105_000_000,
                        amort_years=4, sweep_bp=0, term_years=5, prepayable="sweep"),
    "term-loan-b": dict(kind="term", commitment_cents=2_700_000_000, drawn_cents=2_700_000_000,
                        rate_bp=625, basis="actual-365", amort_cents=0, amort_years=0,
                        sweep_bp=5000, term_years=5, prepayable="sweep"),
    "mezzanine": dict(kind="term", commitment_cents=600_000_000, drawn_cents=600_000_000,
                      rate_bp=1100, basis="thirty-360", amort_cents=0, amort_years=0,
                      sweep_bp=0, term_years=5, prepayable="never"),
}

_FEES = (
    {"name": "advisor", "basis": "purchase", "bp": 100},
    {"name": "arrangement-term-loan-a", "basis": "drawn", "bp": 250},
    {"name": "arrangement-term-loan-b", "basis": "drawn", "bp": 300},
    {"name": "arrangement-mezzanine", "basis": "drawn", "bp": 450},
)

ERROR = "estate: "

_ASKS = []


class EstateError(ValueError):
    """The estate's refusal: a fact the deal does not hold, named by its own key."""


def _whole(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        raise EstateError(ERROR + ("%s is not a whole number" % (what,)))
    return value


def _year(year, what="the year"):
    """A walk year, `1` through `5`, or a refusal naming the offender."""
    _whole(year, what)
    if year < 1 or year > len(YEAR_ENDS):
        raise EstateError(ERROR + ("%d is not a year the walk walks" % (year,)))
    return year


def _note(kind, key):
    """One ask of the answer key, on the ledger the checks recount."""
    _ASKS.append((kind, key))


def year_days(basis):
    """The year a basis divides its day count into: `365` or `360`."""
    if basis not in dates.BASES:
        raise EstateError(ERROR + ("%r is not one of the bases %r"
                                   % (basis, dates.BASES)))
    return 365 if basis == "actual-365" else 360


YEARS_IN = {"actual-365": 365, "thirty-360": 360}


def _year_start(year):
    return ENTRY_DATE if year == 1 else YEAR_ENDS[year - 2]


def taxes(taxable_cents):
    """The bands the taxable base splits across: the first `top_cents` at the
    low rate, the remainder at the high rate, both truncated to the cent."""
    _whole(taxable_cents, "the taxable base")
    if taxable_cents < 0:
        raise EstateError(ERROR + ("the bands tax a positive base, not %d" % (taxable_cents,)))
    low = taxable_cents if taxable_cents <= TAX_TOP_CENTS else TAX_TOP_CENTS
    high = taxable_cents - low
    return low * TAX_LOW_BP // 10000 + high * TAX_HIGH_BP // 10000


# --- the walk the estate holds as data --------------------------------------

_ROWS = None
_EXIT = None


def _the_walk():
    """The five-year ledger, computed once, the way the contract pins every
    division: interest on the opening balance at the tranche's own day count,
    the mandatory amortisation charged to cash and to the tranche's balance,
    the revolver drawn to the floor and repaid first from any excess, the
    term loan B sweeping its fee of what survives those two, the cure cheque
    top-down through the prepayables, and the rest distributed with the
    balance sheet carrying its floor.
    """
    global _ROWS, _EXIT
    if _ROWS is not None:
        return _ROWS, _EXIT
    balances = dict((name, _TERMS[name]["drawn_cents"]) for name in TRANCHE_ORDER)
    cash = MIN_CASH_CENTS
    rows = {}
    for year in range(1, len(YEAR_ENDS) + 1):
        actual = _YEARBOOK[year]
        prev_wc = ENTRY_WORKING_CAPITAL_CENTS if year == 1 \
            else _YEARBOOK[year - 1]["working_capital_cents"]
        taxable = actual["ebitda_cents"] - actual["depreciation_cents"]
        tax = taxes(taxable)
        absorption = actual["working_capital_cents"] - prev_wc
        capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
        free = actual["ebitda_cents"] - tax - capex - absorption
        interest = {}
        amortisation = {}
        for name in TRANCHE_ORDER:
            terms = _TERMS[name]
            days = dates.day_count(_year_start(year), YEAR_ENDS[year - 1], terms["basis"])
            interest[name] = balances[name] * terms["rate_bp"] * days \
                // (year_days(terms["basis"]) * 10000)
            amortisation[name] = terms["amort_cents"] if year <= terms["amort_years"] else 0
        for name in TRANCHE_ORDER:
            balances[name] -= amortisation[name]
        projected = cash + free - sum(interest.values()) - sum(amortisation.values())
        draw = 0
        if projected < cash:
            undrawn = _TERMS["revolver"]["commitment_cents"] - balances["revolver"]
            draw = min(cash - projected, undrawn)
            balances["revolver"] += draw
            projected += draw
        excess = projected - cash
        repay = min(excess, balances["revolver"]) if excess > 0 else 0
        balances["revolver"] -= repay
        remaining = excess - repay
        sweep = 0
        if remaining > 0:
            sweep = min(remaining * _TERMS["term-loan-b"]["sweep_bp"] // 10000,
                        balances["term-loan-b"])
            balances["term-loan-b"] -= sweep
        remaining = remaining - sweep
        distribution = max(0, remaining)
        cure_on = dict((name, 0) for name in TRANCHE_ORDER)
        if year == CURE_YEAR and CURE_MONEY_CENTS:
            left = CURE_MONEY_CENTS
            for name in CURE_ORDER:
                take = min(left, balances[name])
                if take:
                    balances[name] -= take
                    cure_on[name] = take
                    left -= take
                if left == 0:
                    break
        cash = MIN_CASH_CENTS
        pre_cure = dict((name, balances[name] + cure_on[name]) for name in TRANCHE_ORDER)
        rows[year] = dict(year=year, year_end=YEAR_ENDS[year - 1], interest=interest,
                          amortisation=amortisation, draw=draw, repay=repay, sweep=sweep,
                          cure=sum(cure_on.values()), cure_on=cure_on,
                          distribution=distribution, cash=cash, balances=dict(balances),
                          pre_cure=pre_cure, free=free, tax=tax, absorption=absorption,
                          capex=capex)
    gross = _YEARBOOK[5]["ebitda_cents"] * EXIT_MULTIPLE_BP // 10000
    debt = sum(balances.values())
    _ROWS, _EXIT = rows, dict(balances=dict(balances), cash=MIN_CASH_CENTS, gross=gross,
                              debt_total=debt,
                              sponsor_equity=gross + MIN_CASH_CENTS - debt)
    return _ROWS, _EXIT


# --- facts the stages may read ----------------------------------------------

def version():
    return ESTATE_VERSION


def company():
    return COMPANY


def entry_date():
    return ENTRY_DATE


def year_ends():
    return tuple(YEAR_ENDS)


def exit_date():
    return EXIT_DATE


def place(date):
    """The walk-year index of a date the deal moves on: the entry date is `0`
    and each year end is its own year. A date the walk never lands on is
    refused by name."""
    if not isinstance(date, str):
        raise EstateError(ERROR + ("%s is not a date the walk moves on" % (date,)))
    if date == ENTRY_DATE:
        return 0
    if date in YEAR_ENDS:
        return YEAR_ENDS.index(date) + 1
    raise EstateError(ERROR + ("%s is not a date the walk moves on" % (date,)))


def shares_outstanding():
    return SHARES_OUTSTANDING


def offer_cents_per_share():
    return OFFER_CENTS_PER_SHARE


def entry_ebitda_cents():
    return ENTRY_EBITDA_CENTS


def entry_revenue_cents():
    return ENTRY_REVENUE_CENTS


def entry_working_capital_cents():
    return ENTRY_WORKING_CAPITAL_CENTS


def min_cash_cents():
    return MIN_CASH_CENTS


def entry_multiple_bp():
    return ENTRY_MULTIPLE_BP


def exit_multiple_bp():
    return EXIT_MULTIPLE_BP


def entry_quotes():
    return tuple(ENTRY_QUOTES)


def exit_quotes():
    return tuple(EXIT_QUOTES)


def equity_cheque_cents():
    return EQUITY_CHEQUE_CENTS


def tranches():
    """Every tranche on its own terms, in the waterfall's order."""
    out = []
    for name in TRANCHE_ORDER:
        keys = [key for key in TRANCHE_KEYS]
        record = {"name": name}
        record.update(dict((key, _TERMS[name][key]) for key in keys if key != "name"))
        out.append(record)
    return tuple(out)


def tranche(name):
    if name not in _TERMS:
        raise EstateError(ERROR + ("the deal holds no tranche %r" % (name,)))
    record = {"name": name}
    record.update(dict((key, _TERMS[name][key]) for key in TRANCHE_KEYS if key != "name"))
    return record


def fee_rows():
    """The fees, as the term sheet rows them: what they sit on and their size."""
    return tuple(dict(row) for row in _FEES)


def tax_bands():
    return dict(top_cents=TAX_TOP_CENTS, low_bp=TAX_LOW_BP, high_bp=TAX_HIGH_BP)


def net_leverage_limits():
    """The maintenance ladder, as the treaty writes it: year end → limit in bp."""
    return dict(NET_LEVERAGE_LIMITS)


def net_leverage_limit(year_end):
    if year_end not in NET_LEVERAGE_LIMITS:
        raise EstateError(ERROR + ("the treaty writes no maintenance limit for %r" % (year_end,)))
    return NET_LEVERAGE_LIMITS[year_end]


def incurrence_bp():
    return INCURRENCE_BP


def cure_year():
    return CURE_YEAR


def cure(year):
    """The cure cheque the sponsor wired in a walk year: `150000000_00` in the
    cure year, nothing in every other."""
    _year(year)
    return CURE_MONEY_CENTS if year == CURE_YEAR else 0


def cure_order():
    return tuple(CURE_ORDER)


def actuals(year):
    """The path the company actually took in a walk year, line by line, through
    the policy's own tax bands. The model's build must land on the tax and the
    free cash flow exactly; a build that does not is a different company."""
    year = _year(year)
    actual = _YEARBOOK[year]
    prev_wc = ENTRY_WORKING_CAPITAL_CENTS if year == 1 \
        else _YEARBOOK[year - 1]["working_capital_cents"]
    taxable = actual["ebitda_cents"] - actual["depreciation_cents"]
    capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
    absorption = actual["working_capital_cents"] - prev_wc
    return dict(zip(ACTUALS_KEYS, (
        year, YEAR_ENDS[year - 1], actual["revenue_cents"], actual["ebitda_cents"],
        actual["depreciation_cents"], actual["capex_maintenance_cents"],
        actual["capex_growth_cents"], actual["working_capital_cents"],
        taxes(taxable),
        actual["ebitda_cents"] - taxes(taxable) - capex - absorption)))


# --- the answer key ---------------------------------------------------------

def debt_row(name, year):
    """One tranche's record of one walk year, as the estate's ledger holds it."""
    year = _year(year)
    if name not in _TERMS:
        raise EstateError(ERROR + ("the deal holds no tranche %r" % (name,)))
    _note("debt-row", (name, year))
    rows, _exit = _the_walk()
    row = rows[year]
    opening = _TERMS[name]["drawn_cents"] if year == 1 else rows[year - 1]["balances"][name]
    closing = _OPENING_CLOSE(name, row, opening)
    return dict(zip(DEBT_ROW_KEYS, (
        name, year, row["year_end"], opening, row["interest"][name],
        row["amortisation"][name],
        row["draw"] if name == "revolver" else 0,
        row["repay"] if name == "revolver" else 0,
        row["sweep"] if name == "term-loan-b" else 0,
        row["cure_on"][name],
        closing["mandatory"], row["balances"][name])))


def _OPENING_CLOSE(name, row, opening):
    mandatory = opening - row["amortisation"][name]
    if name == "revolver":
        mandatory = mandatory + row["draw"] - row["repay"]
    return dict(mandatory=mandatory)


def state_end(year):
    """The closing state of a walk year: every tranche's balance and the cash
    the balance sheet carries, once the year's waterfall is booked."""
    year = _year(year)
    _note("state", (year, "end"))
    rows, _exit = _the_walk()
    row = rows[year]
    return dict(zip(STATE_KEYS, (dict(row["balances"]), row["cash"])))


def state_for_test(year):
    """The state the year's maintenance test is measured on: the balances as
    they stand after the sweep, before the cure cheque settles the test."""
    year = _year(year)
    _note("state", (year, "for-test"))
    rows, _exit = _the_walk()
    row = rows[year]
    return dict(zip(STATE_KEYS, (dict(row["pre_cure"]), row["cash"])))


def distribution(year):
    """What the year's waterfall left for the sponsor, in cents."""
    year = _year(year)
    _note("distribution", year)
    rows, _exit = _the_walk()
    return rows[year]["distribution"]


def stats():
    """The ledger of answer-key asks, in order, for the checks to recount."""
    return tuple(_ASKS)


def actual_exit():
    """The exit the deal actually closed on, as the ledger ends: the balances
    the exit pays off, the cash it walks out, and the equity the sponsor
    carries away."""
    _rows, exit = _the_walk()
    return dict(balances=dict(exit["balances"]), cash=exit["cash"],
                gross_cents=exit["gross"], debt_total_cents=exit["debt_total"],
                sponsor_equity_cents=exit["sponsor_equity"])


# --- the sponsor's memo -----------------------------------------------------

MEMO_KEYS = ("deal", "irr_bp", "moic_bp", "carry_bp", "growth_bp", "multiple_bp",
             "leverage_bp", "debt_path", "limits_path", "exit_gross_cents",
             "exit_cash_cents", "exit_equity_cents", "worst_irr_bp")

MEMO_PATH_KEYS = ("year", "closing_cents", "distribution_cents", "cure_cents")

MEMO_LIMIT_KEYS = ("year_end", "limit_bp")

_MEMO = {
    "deal": dict(zip(DEAL_KEYS, (ENTRY_MULTIPLE_BP, EXIT_MULTIPLE_BP))),
    "irr_bp": 2433,
    "moic_bp": 26856,
    "carry_bp": 638,
    "growth_bp": 449,
    "multiple_bp": 77,
    "leverage_bp": 1202,
    "debt_path": (
        dict(zip(MEMO_PATH_KEYS, (1, 5_237_230_000, 57_770_000, 0))),
        dict(zip(MEMO_PATH_KEYS, (2, 5_022_636_967, 109_593_033, 0))),
        dict(zip(MEMO_PATH_KEYS, (3, 4_602_449_372, 165_187_595, 150_000_000))),
        dict(zip(MEMO_PATH_KEYS, (4, 4_387_563_415, 109_885_958, 0))),
        dict(zip(MEMO_PATH_KEYS, (5, 4_137_569_772, 249_993_644, 0))),
    ),
    "limits_path": (
        dict(zip(MEMO_LIMIT_KEYS, ("2027-06-30", 41500))),
        dict(zip(MEMO_LIMIT_KEYS, ("2028-06-30", 40000))),
        dict(zip(MEMO_LIMIT_KEYS, ("2029-06-30", 29000))),
        dict(zip(MEMO_LIMIT_KEYS, ("2030-06-30", 40000))),
        dict(zip(MEMO_LIMIT_KEYS, ("2031-06-30", 20000))),
    ),
    "exit_gross_cents": 9_643_750_000,
    "exit_cash_cents": 320_000_000,
    "exit_equity_cents": 5_826_180_228,
    "worst_irr_bp": 680,
}


def memo():
    """The sponsor's memo, already written. Three of its lines are wrong, by
    the sponsor's own arithmetic — the audit finds them out, not the reader."""
    return dict(_MEMO)
