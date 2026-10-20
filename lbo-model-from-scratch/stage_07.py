"""LBO Model From Scratch — solutions, stage 7: The money multiple and the rate that discounts the deal.

The sponsor's return is two questions a board asks in one breath. The first
is arithmetic: how many of the sponsor's cents came back for every cent that
went out — the money multiple, in integer ten-thousandths with the pinned
truncation, against the invested cents the flows themselves name. The second
is a rate, and a rate is not arithmetic: it is the smallest whole basis point
at which the dated flows — the entry cheque out, the distributions the
waterfall paid in, the cure cheque back out, and the sale's equity walking
in — have a present value that does not pay more than the deal cost. This
stage searches for it by bisection over `0..MAX_IRR_BP` and reports what it
leaves behind: the residue, the discounted worth the answered rate still
carries, is data about the deal in the same way stage 1's effective interest
rate reported its residue, and hiding it is how a return gets quoted at a
precision the whole-bp search never earned.

The flows are the stage's own first duty: the sponsor's dated cheque out at
the entry date, each year's distribution in on the walk's year ends, the
sponsor's cure cheque out in the year the world recorded it, and the sale's
equity in on the exit date. Every flow is recomputed from the waterfall —
the distributions are what the sweep left, the exit is what the multiple
realised — and the deal the flows must echo is the deal the estate recorded:
an entry multiple or an exit multiple the market table does not quote, or
one that disagrees with the deal itself, is refused by name.

    DEAL_KEYS           the two fields of the deal, in order
    FLOW_KEYS           the two fields of one sponsor flow, in order
    SPONSOR_KEYS        the four fields of the sponsor's flows, in order
    MOIC_KEYS           the three fields of the money multiple, in order
    IRR_KEYS            the four fields of the searched rate, in order
    MAX_IRR_BP          the wall the search never crosses
    ReturnError         the refusal this stage raises
    sponsor_flows(estate, deal) -> SPONSOR_KEYS: the dated flows, recomputed
    moic(flows)         -> MOIC_KEYS: what came back per cent that went out
    irr(estate, flows)  -> IRR_KEYS: the whole-bp rate and the residue it leaves

    A deal the estate does not record; the flows that do not shape like
    flows; a stream with nothing invested; a rate whose whole-bp wall the
    search cannot price — all refused by name. The wall refuser names
    `MAX_IRR_BP`, so the caller knows the answer is elsewhere.
"""

import dates

DEAL_KEYS = ("entry_multiple_bp", "exit_multiple_bp")

FLOW_KEYS = ("date", "amount_cents")

SPONSOR_KEYS = ("deal", "entry_date", "flows", "years")

MOIC_KEYS = ("invested_cents", "collected_cents", "moic_bp")

IRR_KEYS = ("flows", "irr_bp", "pv_cents", "years")

MAX_IRR_BP = 30000

SLOPE_RESIDUE_BP = 1


class ReturnError(ValueError):
    """The refusal this stage raises: a return nobody can price.

    It names the offender — the multiple the recorded deal was not struck on,
    the flow that does not shape like one, the stream with nothing invested,
    the rate search whose wall refuses — because a return without its own
    arithmetic is a claim, and this course does not quote claims.
    """


def _deal(estate, deal):
    """The recorded deal, echoed and tied to the market's quotes, or refused."""
    if not isinstance(deal, dict):
        raise ReturnError("the returns: the deal is a %s, not a record" % (type(deal).__name__,))
    for key in DEAL_KEYS:
        if key not in deal:
            raise ReturnError("the returns: the deal does not answer %s" % (key,))
        multiple = deal[key]
        if isinstance(multiple, bool) or not isinstance(multiple, int):
            raise ReturnError("the returns: the deal's %s is not a whole number of "
                              "basis points" % (key,))
    if deal["entry_multiple_bp"] != estate.entry_multiple_bp() \
            or deal["exit_multiple_bp"] != estate.exit_multiple_bp():
        raise ReturnError("the returns: the deal at %d bp in and %d bp out is not the "
                          "%d bp in and %d bp out the estate recorded"
                          % (deal["entry_multiple_bp"], deal["exit_multiple_bp"],
                             estate.entry_multiple_bp(), estate.exit_multiple_bp()))
    return deal


def _flows(estate, flows):
    """The flows as dated records on the walk's own years, or a refusal."""
    if not isinstance(flows, (tuple, list)):
        raise ReturnError("the returns: the flows are a %s, not a record of dated "
                          "flows" % (type(flows).__name__,))
    for flow in flows:
        if not isinstance(flow, dict) or tuple(flow.keys()) != FLOW_KEYS:
            raise ReturnError("the returns: a flow answers %s, not a %s record"
                              % (sorted([k for k in flow] if isinstance(flow, dict) else []),
                                 ",".join(FLOW_KEYS)),)
    return flows


def _walked_sponsor(estate):
    """The recorded deal's sponsor flows, recomputed: the entry cheque out,
    each year's distribution in, the cure cheque out on the day it was wired,
    and the sale's equity in on the exit date — separate records, even when
    a distribution and the cure share a date, because a sponsor's cheque in
    and the waterfall's cheque out are two events on one day, not one net
    one. The waterfall is local; nothing here reads the answer key."""
    ends = estate.year_ends()
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    order = tuple(terms["name"] for terms in estate.tranches())
    balances = dict((terms["name"], terms["drawn_cents"]) for terms in estate.tranches())
    cash = estate.min_cash_cents()
    events = []
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
            events.append((ends[walk_year - 1], remaining))
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
            events.append((ends[walk_year - 1], -cure))
        cash = estate.min_cash_cents() if excess >= 0 else projected
    ebitda = estate.actuals(len(ends))["ebitda_cents"]
    gross = ebitda * estate.exit_multiple_bp() // 10000
    debt = sum(balances.values())
    events.append((estate.exit_date(), gross + cash - debt))
    return events


def sponsor_flows(estate, deal):
    """The sponsor's dated flows, recomputed from the waterfall, dated on the

    raise NotImplementedError("7: implement sponsor_flows()")
def moic(flows):
    """What came back per cent that went out, in integer ten-thousandths with
    the pinned truncation: the positive flows against the negatives, every
    division `//` and the residue the truncation's own.

    A stream with nothing invested is refused — a multiple has to have a
    something to be multiple of, and a stream of all income is a windfall,
    not a return."""
    flows = _flows(None, flows)
    invested = 0
    collected = 0
    for flow in flows:
        if flow["amount_cents"] < 0:
            invested -= flow["amount_cents"]
        else:
            collected += flow["amount_cents"]
    if invested == 0:
        raise ReturnError("the money multiple: the flows invest nothing — a stream of "
                          "%d of income alone is a windfall, not a return" % (collected,))
    return dict(zip(MOIC_KEYS, (invested, collected, collected * 10000 // invested)))


def _placed(estate, flows):
    """The flows aggregated onto the walk's own year indices: the entry date
    is year `0` and each year end its own year. A date the walk does not move
    on is refused by name, so a misplaced flow cannot drift into somebody
    else's year."""
    net = {}
    years = 0
    for flow in flows:
        if not isinstance(flow, dict) or tuple(flow.keys()) != FLOW_KEYS:
            raise ReturnError("the returns: a flow answers %s, not a %s record"
                              % ([k for k in flow] if isinstance(flow, dict) else flow,
                                 ",".join(FLOW_KEYS)))
        date = flow["date"]
        try:
            index = estate.place(date)
        except ValueError:
            raise ReturnError("the returns: %s is not a date the walk moves on — the "
                              "flows place themselves on %s and the years it walks"
                              % (date, estate.entry_date()))
        net[index] = net.get(index, 0) + flow["amount_cents"]
        years = max(years, index)
    if not net:
        raise ReturnError("the returns: no flows to price")
    return net, years


def irr(estate, flows):
    """The smallest whole basis point in `0..MAX_IRR_BP` at which the dated
    flows do not pay more than they cost, bisected, with the residue
    reported.

    The present value is stepped, never powered: one factor per year apart,
    `factor = factor * 10000 // (10000 + rate)`, divided silent truncation at
    every step. The search reads its slope off the first two basis points and
    asks only that the answer's present value does not pay too much; the
    residue — the worth the answered rate still carries, usually a few cents
    of an under-priced whole bp — is in the record, where it can be read
    rather than defended.

    A stream whose year-zero worth is zero is refused (no rate prices
    nothing), and so is a stream the wall `MAX_IRR_BP` still cannot pay for:
    the refusal names the wall, because the answer being elsewhere is
    exactly what the caller needs to know.
    """
    flows = _flows(estate, flows)
    net, years = _placed(estate, flows)

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
        raise ReturnError("the rate: the flows price to zero at zero bp — no rate "
                          "that prices a nothing")
    falling = npv(SLOPE_RESIDUE_BP) < npv(0)
    pays = (lambda rate: npv(rate) <= 0) if falling else (lambda rate: npv(rate) >= 0)
    if not pays(MAX_IRR_BP):
        raise ReturnError("the rate: no rate in 0..%d bp prices these flows — the "
                          "wall holds" % (MAX_IRR_BP,))
    if pays(0):
        answer, worth = 0, npv(0)
    else:
        low = 0
        high = MAX_IRR_BP
        while high - low > SLOPE_RESIDUE_BP:
            middle = (low + high) // 2
            if pays(middle):
                high = middle
            else:
                low = middle
        answer, worth = high, npv(high)
    return dict(zip(IRR_KEYS, (tuple(flows), answer, worth, years)))
