"""LBO Model From Scratch — solutions, stage 9: The sensitivity grid, with the breach kept visible.

Every deal is priced twice before it closes and endless times after it
breaks: once at the multiples that were struck, and once on the grid the
sponsor banks on — what does two hundred fifty basis points more of entry
leverage do to the return, and what does a thinner exit do, and where exactly
does the covenant bite. This stage produces the grid, one cell per
`(entry, exit)` pair the market quotes: the cell's whole-bp IRR, searched by
the same bisection as the recorded deal's, and the cell's covenant verdict,
measured the way stage 5 measures it — pre-cure, on the scaled balances —
with the first breach as data in the row.

The cell's walk is the recorded deal's walk at a different price: the tranches
fund at the cell's entry multiple scaled off the recorded one, the mandatory
amortisation scales with the money, the fees ride the same fractions, the
floor and the cure cheque do not scale (a sponsor's cheque is a sponsor's
cheque whatever the deal cost), the recorded path's actuals do not move, and
the exit is struck on the cell's exit multiple. A cell is then a whole deal,
and the grid is a table of deals, not of guesses.

The refusal the world may not round away is the breach. A model that cannot
show the year its covenant breaks — the year the sponsor wired a cure — is a
model that amortises its own bad news, and the estate recorded this deal's
year three cure for exactly that reason. The verdict is `breach_year` and
`by_bp`, `0` and `0` when the cell never breaches, because a row without the
column is worse than a row with a hole in it.

    GRID_KEYS           the five fields of one cell, in order
    MAX_IRR_BP          the wall the cells' search never crosses
    SensitivityError    the refusal this stage raises
    grid(estate, entry_range, exit_range) -> tuple(GRID_KEYS): the grid, row by row

    A range that names a multiple the market does not quote, an empty range,
    or a range that is not a range is refused by name — the grid prices the
    market's own columns, and nothing was quoted at the edges it invents.
"""

import dates

GRID_KEYS = ("entry_multiple_bp", "exit_multiple_bp", "irr_bp", "breach_year", "by_bp")

MAX_IRR_BP = 30000


class SensitivityError(ValueError):
    """The refusal this stage raises: a grid the market cannot price.

    It names the offender — the multiple the quotes do not carry, the range
    that is not a range, the empty column — because a grid over multiples
    nobody quotes is a grid over a market nobody runs.
    """


def _quote(estate, multiple, side):
    if isinstance(multiple, bool) or not isinstance(multiple, int):
        raise SensitivityError("the grid: %s is not a %s multiple in basis points"
                               % (multiple, side))
    quotes = estate.entry_quotes() if side == "entry" else estate.exit_quotes()
    if multiple not in quotes:
        raise SensitivityError("the grid: %d is not a %s multiple the market quotes"
                               % (multiple, side))
    return multiple


def _range(estate, multiples, side):
    if isinstance(multiples, (str, bytes)) or not hasattr(multiples, "__iter__"):
        raise SensitivityError("the grid: the %s range is a %s, not a range"
                               % (side, type(multiples).__name__))
    out = []
    for multiple in multiples:
        out.append(_quote(estate, multiple, side))
    if not out:
        raise SensitivityError("the grid: the %s range is empty — nothing to price"
                               % (side,))
    return tuple(out)


def _cell_state(estate, entry_multiple_bp):
    """One cell's opening state: the tranches and the fees at the cell's
    price, scaled off the recorded deal, and the balance sheet's same floor.

    The scale is whole-bp integer arithmetic off the recorded entry multiple:
    drawn `x scale // 10000`, amortisation the same way, advisor fee on the
    purchase this cell strikes, the arrangement fees on the money this cell
    funds. The sponsor's cheque backs whatever the financing does not, and
    the cure cheque has no scale — a sponsor wires what a cure needs."""
    scale = entry_multiple_bp * 10000 // estate.entry_multiple_bp()
    purchase = estate.entry_ebitda_cents() * entry_multiple_bp // 10000
    balances = {}
    fees = 0
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    for fee in estate.fee_rows():
        if fee["basis"] == "purchase":
            fees += purchase * fee["bp"] // 10000
        else:
            name = fee["name"].replace("arrangement-", "")
            fees += terms_by_name[name]["drawn_cents"] * scale // 10000 * fee["bp"] // 10000
    debt = 0
    for terms in estate.tranches():
        drawn = terms["drawn_cents"] * scale // 10000
        balances[terms["name"]] = drawn
        debt += drawn
    equity = purchase + fees + estate.min_cash_cents() - debt
    return balances, equity, scale, terms_by_name


def _cell_flows(estate, entry_multiple_bp, exit_multiple_bp):
    """One cell's whole walk, recomputed from the world's own path and the
    world's own terms, at the cell's own price: the sponsor flows out at the
    entry, the scaled year's waterfall, the cure cheque unscaled in its
    recorded year, and the sale at the cell's exit. The row also carries the
    covenant test the way the world's estate measures it — pre-cure."""
    ends = estate.year_ends()
    balances, equity, scale, terms_by_name = _cell_state(estate, entry_multiple_bp)
    order = tuple(terms["name"] for terms in estate.tranches())
    flows = [(estate.entry_date(), 0 - equity)]
    cash = estate.min_cash_cents()
    breaches = []
    for walk_year in range(1, len(ends) + 1):
        actual = estate.actuals(walk_year)
        bands = estate.tax_bands()
        prev_wc = estate.entry_working_capital_cents() if walk_year == 1 \
            else estate.actuals(walk_year - 1)["working_capital_cents"]
        taxable = actual["ebitda_cents"] - actual["depreciation_cents"]
        low = taxable if taxable <= bands["top_cents"] else bands["top_cents"]
        high = taxable - low
        tax = low * bands["low_bp"] // 10000 + high * bands["high_bp"] // 10000
        capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
        absorption = actual["working_capital_cents"] - prev_wc
        free = actual["ebitda_cents"] - tax - capex - absorption
        interest = {}
        amortisation = {}
        for name in order:
            terms = terms_by_name[name]
            start = estate.entry_date() if walk_year == 1 else ends[walk_year - 2]
            days = dates.day_count(start, ends[walk_year - 1], terms["basis"])
            interest[name] = balances[name] * terms["rate_bp"] * days \
                // (estate.year_days(terms["basis"]) * 10000)
            amortisation[name] = terms["amort_cents"] * scale // 10000 \
                if walk_year <= terms["amort_years"] else 0
        for name in order:
            balances[name] -= amortisation[name]
        projected = cash + free - sum(interest.values()) - sum(amortisation.values())
        revolver = terms_by_name["revolver"]
        if projected < cash:
            undrawn = revolver["commitment_cents"] * scale // 10000 - balances["revolver"]
            if undrawn < 0:
                raise SensitivityError("the grid: at %d bp the revolver's draw runs "
                                       "past its own commitment — the cell cannot fund"
                                       % (entry_multiple_bp,))
            draw = min(cash - projected, undrawn)
            balances["revolver"] += draw
            projected += draw
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
        pre_cure_net = sum(balances.values()) - estate.min_cash_cents()
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
        limit = estate.net_leverage_limit(ends[walk_year - 1])
        pre_ratio = pre_cure_net * 10000 // actual["ebitda_cents"]
        if pre_ratio > limit and not breaches:
            breaches.append((walk_year, pre_ratio - limit))
        if remaining > 0:
            flows.append((ends[walk_year - 1], remaining))
        if cure:
            flows.append((ends[walk_year - 1], -cure))
    ebitda = actual["ebitda_cents"]
    gross = ebitda * exit_multiple_bp // 10000
    debt = sum(balances.values())
    flows.append((estate.exit_date(), gross + cash - debt))
    return tuple(flows), breaches, len(ends)


def _cell_irr(estate, flows, years):
    def place(date):
        if date == estate.entry_date():
            return 0
        return estate.year_ends().index(date) + 1

    net = {}
    for flows_pair in flows:
        net[place(flows_pair[0])] = net.get(place(flows_pair[0]), 0) + flows_pair[1]

    def npv(rate):
        factor = 10000
        total = 0
        last = 0
        for index in sorted(net):
            while last < index:
                factor = factor * 10000 // (10000 + rate)
                last += 1
            total = total + net[index] * factor // 10000
        return total

    if npv(0) == 0:
        raise SensitivityError("the grid: the cell prices to zero — nothing to search")
    falling = npv(1) < npv(0)
    pays = (lambda rate: npv(rate) <= 0) if falling else (lambda rate: npv(rate) >= 0)
    if not pays(MAX_IRR_BP):
        raise SensitivityError("the grid: no rate in 0..%d prices this cell — the "
                               "wall holds" % (MAX_IRR_BP,))
    if pays(0):
        return 0
    low = 0
    high = MAX_IRR_BP
    while high - low > 1:
        middle = (low + high) // 2
        if pays(middle):
            high = middle
        else:
            low = middle
    return high


def grid(estate, entry_range, exit_range):
    """The grid the sponsor banks on, one row per cell the market quotes.

    Each cell carries its own walk: the tranches funded at the cell's entry
    multiple scaled off the recorded one, the actuals the world recorded, the
    cure cheque unscaled in its recorded year, and the exit struck on the
    cell's own multiple. The row answers the cell's whole-bp IRR and the
    covenant verdict the pre-cure test delivers — the first year the
    maintenance test breaks, by how many basis points, or `0` and `0` for a
    cell that never breaches, because a breach that hides is a breach that
    gets amortised.

    A range that names a multiple the market does not quote, an empty range,
    or a range that is not a range is refused by name."""
    entries = _range(estate, entry_range, "entry")
    exits = _range(estate, exit_range, "exit")
    rows = []
    for entry_multiple_bp in entries:
        for exit_multiple_bp in exits:
            flows, breaches, years = _cell_flows(estate, entry_multiple_bp,
                                                 exit_multiple_bp)
            rate = _cell_irr(estate, flows, years)
            breach_year = breaches[0][0] if breaches else 0
            by = breaches[0][1] if breaches else 0
            rows.append(dict(zip(GRID_KEYS, (entry_multiple_bp, exit_multiple_bp, rate,
                                             breach_year, by))))
    return tuple(rows)
