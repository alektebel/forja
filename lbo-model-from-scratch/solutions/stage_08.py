"""LBO Model From Scratch — solutions, stage 8: Where the return came from.

A sponsor's IRR is one number with three engines under it. The debt itself
multiplies whatever the company did. The company's own EBITDA growth carries
the earnings from entry to exit. And the market re-rating — the multiple it
paid at exit against the one it charged at entry — moves the price while the
company moves the earnings. This stage answers all three by building the
counterfactuals the question requires, each one the same deal with one engine
removed, each one priced by the same whole-bp search stage 7 pins:

* the **carry** is the deal without the debt: the sponsor's cheque now buys
  the purchase, the fees and the balance sheet's opening cash all by itself,
  the company's free cash flows are collected whole in every year before the
  exit, and the exit is struck on the entry multiple — the return the
  financing never touched, priced at `(entry EBITDA, entry multiple)`.
* the **growth** part is the carry raised at the exit year's recorded
  EBITDA's own multiple — the same deal, one engine moved.
* the **multiple** part is growth raised at the market's exit multiple — the
  re-rating, priced last, before the debt is let back in.
* the **leverage** part is the whole recorded IRR less the parts priced
  through: the engines' worth with the cheaper engines accounted, which is
  how an identity lands at zero instead of how a decomposition gets to
  fudge a remainder.

The reconcile is the stage's own report: the parts' sum is the whole IRR,
and the residual it leaves is reported in the record — pinned arithmetic
here, a zero by the telescoping, and the zero is the point: a decomposition
that leaves a remainder it cannot name is a story that is missing a chapter.

    DECOMPOSE_KEYS      the seven fields of the decomposition, in order
    MAX_IRR_BP          the wall the counterfactuals' search never crosses
    DecomposeError      the refusal this stage raises
    decompose(estate, deal) -> DECOMPOSE_KEYS: the whole return, engine by engine

    A deal the estate does not record is refused by name, and so is a
    counterfactual the deal's own years make impossible: an unlevered year
    whose recorded free cash flow is an absorption, because an all-equity
    sponsor isn't renegotiating its own term sheet's cures — it simply never
    wired them.
"""

import dates

DECOMPOSE_KEYS = ("irr_bp", "carry_bp", "growth_bp", "multiple_bp", "leverage_bp",
                  "sum_bp", "residual_bp")

DEAL_KEYS = ("entry_multiple_bp", "exit_multiple_bp")

MAX_IRR_BP = 30000


class DecomposeError(ValueError):
    """The refusal this stage raises: a counterfactual the deal cannot hold.

    It names the offender — the deal whose multiples the recorded one never
    priced, the unlevered year whose recorded line is an absorption the
    all-equity sponsor has nothing to route — because a decomposition built
    on a dealstage never booked is a story about a different deal.
    """


def _deal(estate, deal):
    if not isinstance(deal, dict):
        raise DecomposeError("the decomposition: the deal is a %s, not a record"
                             % (type(deal).__name__,))
    for key in DEAL_KEYS:
        if key not in deal:
            raise DecomposeError("the decomposition: the deal does not answer %s" % (key,))
        multiple = deal[key]
        if isinstance(multiple, bool) or not isinstance(multiple, int):
            raise DecomposeError("the decomposition: the deal's %s is not a whole "
                                 "number" % (key,))
    if deal["entry_multiple_bp"] != estate.entry_multiple_bp() \
            or deal["exit_multiple_bp"] != estate.exit_multiple_bp():
        raise DecomposeError("the decomposition: the deal at %d in and %d out is not "
                             "the %d in and %d out the estate recorded"
                             % (deal["entry_multiple_bp"], deal["exit_multiple_bp"],
                                estate.entry_multiple_bp(), estate.exit_multiple_bp()))
    return deal


def _npv(net, rate, years):
    factor = 10000
    total = 0
    last = 0
    for index in sorted(net):
        while last < index:
            factor = factor * 10000 // (10000 + rate)
            last += 1
        total = total + net[index] * factor // 10000
    return total


def _irr(estate, net, years):
    """The whole-bp search, shared shapes with stage 7 but local, because no
    stage borrows a stage: the slope is read, the wall is named, the residue
    is the answer's own present value."""
    def npv(rate):
        return _npv(net, rate, years)

    if npv(0) == 0:
        raise DecomposeError("the decomposition: the counterfactual prices to zero at "
                             "zero bp — nothing to decompose")
    falling = npv(1) < npv(0)
    pays = (lambda rate: npv(rate) <= 0) if falling else (lambda rate: npv(rate) >= 0)
    if not pays(MAX_IRR_BP):
        raise DecomposeError("the decomposition: no rate in 0..%d bp prices these "
                             "counterfactual flows" % (MAX_IRR_BP,))
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


def _sponsor_flows(estate):
    ends = estate.year_ends()
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    order = tuple(terms["name"] for terms in estate.tranches())
    balances = dict((terms["name"], terms["drawn_cents"]) for terms in estate.tranches())
    cash = estate.min_cash_cents()
    events = {}
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
            amortisation[name] = terms["amort_cents"] \
                if walk_year <= terms["amort_years"] else 0
        for name in order:
            balances[name] -= amortisation[name]
        projected = cash + free - sum(interest.values()) - sum(amortisation.values())
        revolver = terms_by_name["revolver"]
        if projected < cash:
            undrawn = revolver["commitment_cents"] - balances["revolver"]
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
        if remaining > 0:
            events[ends[walk_year - 1]] = events.get(ends[walk_year - 1], 0) + remaining
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
            events[ends[walk_year - 1]] = events.get(ends[walk_year - 1], 0) - cure
        cash = estate.min_cash_cents() if excess >= 0 else projected
    ebitda = estate.actuals(len(ends))["ebitda_cents"]
    gross = ebitda * estate.exit_multiple_bp() // 10000
    events[estate.exit_date()] = events.get(estate.exit_date(), 0) + gross + cash \
        - sum(balances.values())
    net = {0: 0 - estate.equity_cheque_cents()}
    for index, date in enumerate(ends, start=1):
        cents = events.get(date)
        if cents:
            net[index] = cents
    return net, len(ends)


def _unlevered_flows(estate, ebitda, multiple):
    """The same deal, the debt taken out and never let back in: the sponsor's
    cheque buys the purchase, the fees and the balance sheet's opening cash,
    the native free cash flows are collected whole in every year but the
    last, and the exit is struck on the parked years' own terms. The cure the
    sponsor never has to wire cannot appear — an all-equity sponsor IS the
    waterfall."""
    ends = estate.year_ends()
    purchase = estate.entry_ebitda_cents() * estate.entry_multiple_bp() // 10000
    fees = 0
    for fee in estate.fee_rows():
        if fee["basis"] == "purchase":
            fees += purchase * fee["bp"] // 10000
        else:
            terms = estate.tranche(fee["name"].replace("arrangement-", ""))
            fees += terms["drawn_cents"] * fee["bp"] // 10000
    net = {0: 0 - (purchase + fees + estate.min_cash_cents())}
    for index, date in enumerate(ends, start=1):
        actual = estate.actuals(index)
        bands = estate.tax_bands()
        prev_wc = estate.entry_working_capital_cents() if index == 1 \
            else estate.actuals(index - 1)["working_capital_cents"]
        taxable = actual["ebitda_cents"] - actual["depreciation_cents"]
        low = taxable if taxable <= bands["top_cents"] else bands["top_cents"]
        high = taxable - low
        tax = low * bands["low_bp"] // 10000 + high * bands["high_bp"] // 10000
        capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
        absorption = actual["working_capital_cents"] - prev_wc
        free = actual["ebitda_cents"] - tax - capex - absorption
        if free < 0:
            raise DecomposeError("the decomposition: year %d's unlevered line is %d — "
                                 "an absorption an all-equity sponsor has no cure, no "
                                 "term sheet, nothing to route it through"
                                 % (index, free))
        if index < len(ends):
            net[index] = free
        else:
            net[index] = ebitda * multiple // 10000 + estate.min_cash_cents()
    return net, len(ends)


def decompose(estate, deal):
    """The whole return, engine by engine, on the recorded deal.

    The engines are priced in order and their parts carry the difference:
    the carry at `(entry EBITDA, entry multiple)`, growth at the exit year's
    recorded EBITDA on the entry multiple, the multiple part at the market's
    exit multiple, and the leverage part priced last as the whole recorded
    IRR's own worth through the waterfall. The parts' sum is the whole and
    the residual is pinned: zero from the telescoping, and a decomposition
    that cannot zero is a story that has lost a chapter.

    A deal the record does not price and an unlevered year whose line is an
    absorption the sponsor cannot route are refused by name."""
    deal = _deal(estate, deal)
    net, years = _sponsor_flows(estate)
    whole = _irr(estate, net, years)
    e0 = estate.entry_ebitda_cents()
    e1 = estate.actuals(years)["ebitda_cents"]
    carry_net, years = _unlevered_flows(estate, e0, estate.entry_multiple_bp())
    carry = _irr(estate, carry_net, years)
    growth_net, years = _unlevered_flows(estate, e1, estate.entry_multiple_bp())
    growth = _irr(estate, growth_net, years)
    multiple_net, years = _unlevered_flows(estate, e1, estate.exit_multiple_bp())
    re_rated = _irr(estate, multiple_net, years)
    return dict(zip(DECOMPOSE_KEYS, (whole, carry, growth - carry, re_rated - growth,
                                     whole - re_rated, whole, 0)))
