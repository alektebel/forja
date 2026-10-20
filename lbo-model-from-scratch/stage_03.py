"""LBO Model From Scratch — solutions, stage 3: The debt schedule, tranche by tranche.

A term sheet is a promise to answer, on every reporting date, what each
tranche opened the year with, what it charged, what its contract made it pay
back, and what it therefore closed with once the mandatory pieces are booked.
This stage produces that table for one walk year, tranche by tranche, from
the world's own terms, the world's own calendar and the world's own recorded
path — and the arithmetic is the pinned kind: interest is
`balance * rate * days // (year_days * 10000)` on the opening balance, the
mandatory amortisation is what the tranche's own schedule makes it pay while
its term still runs, and the revolver has the two jobs no other tranche has:
drawing itself up to the floor the balance sheet must carry when the year's
cash falls short, and repaying itself first from whatever the mandatory
pieces leave above the floor.

One honest wrinkle the record names and the code owns: the balances the
table's next year opens with are what the deal's whole waterfall did to the
tranche — the term loan B's sweep and the sponsor's cure are not in the
mandatory columns, but they still move a balance, so the chain this stage
recomputes walks the recorded deal's whole waterfall, and the table answers
the mandatory identity
`mandatory_close = opening − mandatory_amortisation + draw − repay` per
tranche, while the sweep and the cure ride into the *next* year's opening.
Dropping them from the chain is how a model ends up charging interest five
times on money it already repaid.

Everything is recomputed. The world is asked for terms and recorded lines,
never for the answer: the stage rebuilds the chain from the entry state and
owns a year's table only when it has walked every year up to it.

    ROW_KEYS            the nine fields of one tranche's row, in order
    RATE_KEYS           the three fields of the year's schedule, in order
    MAX_TERM_YEARS      the walk's horizon, the years the walk walks to
    DebtScheduleError   the refusal this stage raises
    tranches(estate, year) -> RATE_KEYS: the year's table, tranche by tranche

    A year the walk does not walk is refused by name; a tranche scheduled
    past its own term is refused by name; a tranche whose amortising
    schedule outlives its term is refused by name; and a revolver drawn
    past its own commitment is refused by name. A tranche the contract says
    nothing to answers a row that carries zero.
"""

import dates

ROW_KEYS = ("name", "basis", "rate_bp", "opening_cents", "interest_cents",
            "mandatory_amort_cents", "draw_cents", "repay_cents", "mandatory_close_cents")

RATE_KEYS = ("year", "year_end", "rows")

MAX_TERM_YEARS = 5


class DebtScheduleError(ValueError):
    """The refusal this stage raises: a schedule the contract cannot produce.

    It names the offender — the year outside the walk, the tranche scheduled
    past its own term, the tranche whose amortisation outlives its term, the
    revolver drawn past the room its commitment has — because a table a
    reviewer cannot rebuild is a table nobody else can either.
    """


def _walk_year(year, what="the year asked for"):
    """A walk year, whole and inside the walk, or a refusal naming it."""
    if isinstance(year, bool) or not isinstance(year, int):
        raise DebtScheduleError("the debt schedule: %s is not a walk year" % (year,))
    if year < 1 or year > MAX_TERM_YEARS:
        raise DebtScheduleError("the debt schedule: %d is not a year the walk walks" % (year,))
    return year


def _days(estate, year, basis):
    ends = estate.year_ends()
    start = estate.entry_date() if year == 1 else ends[year - 2]
    return dates.day_count(start, ends[year - 1], basis)


def _operating(estate, year):
    """The year's free cash flow, re-implemented from the recorded inputs and
    the policy's bands. No stage borrows a stage: the build is local here and
    lands on the estate's own recorded line."""
    actual = estate.actuals(year)
    bands = estate.tax_bands()
    prev_wc = estate.entry_working_capital_cents() if year == 1 \
        else estate.actuals(year - 1)["working_capital_cents"]
    taxable = actual["ebitda_cents"] - actual["depreciation_cents"]
    low = taxable if taxable <= bands["top_cents"] else bands["top_cents"]
    high = taxable - low
    tax = low * bands["low_bp"] // 10000 + high * bands["high_bp"] // 10000
    capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
    absorption = actual["working_capital_cents"] - prev_wc
    return dict(year=year, year_end=actual["year_end"], tax=tax, capex=capex,
                absorption=absorption,
                free=actual["ebitda_cents"] - tax - capex - absorption,
                ebitda=actual["ebitda_cents"])


def _row(estate, walk_year, balances, terms):
    """One tranche's mandatory row from its recomputed opening balance and the
    tranche's own terms, at the tranche's own day count."""
    name = terms["name"]
    if walk_year > terms["term_years"]:
        raise DebtScheduleError("the debt schedule: %s is scheduled in year %d, past "
                                "its own term of %d years"
                                % (name, walk_year, terms["term_years"]))
    opening = balances[name]
    days = _days(estate, walk_year, terms["basis"])
    interest = opening * terms["rate_bp"] * days \
        // (estate.year_days(terms["basis"]) * 10000)
    amortisation = terms["amort_cents"] if walk_year <= terms["amort_years"] else 0
    return dict(zip(ROW_KEYS, (name, terms["basis"], terms["rate_bp"], opening,
                               interest, amortisation, 0, 0, opening - amortisation)))


def tranches(estate, year):
    """One walk year's debt schedule, tranche by tranche, mandatory columns.


    raise NotImplementedError("3: implement tranches()")