"""LBO Model From Scratch — solutions, stage 6: The exit on the multiple the market realised.

The deal ends on a date and a multiple both sides struck in advance: the
terminal year's recorded EBITDA, the year-end the market's exit table shows,
and the equity the sponsor carries away once the debt the waterfall left is
paid off on the way out. This stage produces that record, recompute-first:
the whole five-year waterfall is rebuilt from the estate's own path, so the
balances the sale pays off are what the recorded deal actually carried at the
end of the terminal year — term loan B swept, term loan A amortised and its
cure absorbed, the mezzanine untouched by everything but its own interest —
and not a number copied from a page.

The waterfall order at a sale is short, because a sale does not ask questions:
the debt is paid in the waterfall's own order — revolver first, then the
amortising term loan, then the sweeping one, then the mezzanine it can never
prepay — and the remainder, after the balance sheet's floor walks out, is the
sponsor's equity. The record names each of those pieces, dated on the estate's
own exit date, because a line without its date is not a flow and a flow
without its date cannot be discounted next stage.

The estate records one exit, on one multiple. The market's exit table quotes
five; an exit struck on a multiple the table does not quote is not a bad
price, it is no price — and the stage refuses it by name rather than
extrapolate the market's own arithmetic.

    EXIT_KEYS           the seven fields of the exit record, in order
    MAX_TERM_YEARS      the walk's horizon, the years the sale rides on
    ExitError           the refusal this stage raises
    exit(estate, exit_multiple_bp) -> EXIT_KEYS: the terminal record

    A multiple the market's exit table does not quote is refused by name;
    anything the estate does record is priced to the cent.
"""

import dates

EXIT_KEYS = ("exit_date", "ebitda_cents", "exit_multiple_bp", "gross_value_cents",
             "debt_repaid_cents", "cash_out_cents", "sponsor_equity_cents")

MAX_TERM_YEARS = 5


class ExitError(ValueError):
    """The refusal this stage raises: an exit that is not on the record.

    It names the offender — the multiple the market's exit table does not
    quote, the exit the estate does not date — because an exit nobody
    quoted is an exit no model may price, and a price invented to fill the
    gap is a price that says nothing.
    """


def _operating(estate, year):
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
    return dict(free=actual["ebitda_cents"] - tax - capex - absorption,
                ebitda=actual["ebitda_cents"],
                year_end=actual["year_end"])


def _terminal_state(estate):
    """The walk's own terminal state, recomputed from the estate's path and
    the world's terms: the balances the recorded deal actually carried at the
    end of the terminal year, and the cash the floor held."""
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    order = tuple(terms["name"] for terms in estate.tranches())
    balances = dict((terms["name"], terms["drawn_cents"]) for terms in estate.tranches())
    cash = estate.min_cash_cents()
    ends = estate.year_ends()
    for walk_year in range(1, MAX_TERM_YEARS + 1):
        operating = _operating(estate, walk_year)
        interest = {}
        amortisation = {}
        for name in order:
            terms = terms_by_name[name]
            start = estate.entry_date() if walk_year == 1 else ends[walk_year - 2]
            days = dates.day_count(start, ends[walk_year - 1], terms["basis"])
            interest[name] = balances[name] * terms["rate_bp"] * days \
                // (estate.year_days(terms["basis"]) * 10000)
            amortisation[name] = terms["amort_cents"] \
                if walk_year <= terms["amort_years"] else 0
            balances[name] -= amortisation[name]
        projected = cash + operating["free"] - sum(interest.values()) \
            - sum(amortisation.values())
        revolver = terms_by_name["revolver"]
        revolver_row_draws = 0
        if projected < cash:
            undrawn = revolver["commitment_cents"] - balances["revolver"]
            revolver_row_draws = min(cash - projected, undrawn)
            balances["revolver"] += revolver_row_draws
            projected += revolver_row_draws
        excess = projected - cash
        repay = min(excess, balances["revolver"]) if excess > 0 else 0
        balances["revolver"] -= repay
        remaining = excess - repay
        sweep = 0
        if remaining > 0:
            sweeping = terms_by_name["term-loan-b"]
            sweep = min(remaining * sweeping["sweep_bp"] // 10000,
                        balances["term-loan-b"])
            balances["term-loan-b"] -= sweep
        remaining = remaining - sweep
        cure = estate.cure(walk_year)
        if cure:
            left = cure
            for name in estate.cure_order():
                take = min(left, balances[name])
                if take:
                    balances[name] -= take
                    left -= take
                if left == 0:
                    break
        cash = estate.min_cash_cents() if excess >= 0 else projected
    return balances, cash


def exit(estate, exit_multiple_bp):
    """The exit the deal closed on, priced on a multiple the market quotes.

    The terminal year's recorded EBITDA, the market's exit multiple, the
    gross value struck on the two — and then the walk's own terminal state
    from the estate's recorded path: the debt the sale pays off in the
    waterfall's own order, the balance sheet's floor walking out as cash,
    and the equity that remains, which is what the sponsor carries away on
    the estate's own exit date.

    A multiple the market's exit table does not quote is refused by name.
    """
    if isinstance(exit_multiple_bp, bool) or not isinstance(exit_multiple_bp, int):
        raise ExitError("the exit: %s is not a multiple in basis points"
                        % (exit_multiple_bp,))
    if exit_multiple_bp not in estate.exit_quotes():
        raise ExitError("the exit: %d is not a multiple the market's exit table quotes"
                        % (exit_multiple_bp,))
    balances, cash = _terminal_state(estate)
    ebitda = estate.actuals(MAX_TERM_YEARS)["ebitda_cents"]
    gross = ebitda * exit_multiple_bp // 10000
    debt = sum(balances.values())
    return dict(zip(EXIT_KEYS, (estate.exit_date(), ebitda, exit_multiple_bp, gross,
                                debt, cash, gross + cash - debt)))
