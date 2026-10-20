"""LBO Model From Scratch — solutions, stage 10: The sponsor's memo, audited line by line.

Every deal closes twice: once in money, once in paper — the memo the sponsor
hands the approving board, with the IRR claimed, the engines attributed, the
debt path charted and the sensitivity range named. The paper is small and the
numbers in it come from somewhere, and the craft of the capstone is finding
out whether the hand that wrote the paper used the same arithmetic the walk
runs. This stage is the tool for that question: `memo` is the sponsor's own
document, handed over as the world records it — three of whose lines were
written by optimistic arithmetic — and `audit` recomputes the deal from the
world and answers, line by line, what the memo claims and what the model
holds, and which lines agree.

The audit recomputes *everything* it compares. The IRR is walked again, the
engines are re-priced, the debt path is rebuilt year by year, the covenant
table is read from the treaty, the exit is struck and the sensitivity range
is re-gridded — every one of these recomputations is local, because the whole
of an audit's authority is that it needed no permission to re-add. Each line
then answers as data: the line's name, the memo's number, the model's, and
whether they agree, with no exception for a disagreement — an auditor that
stops at the first miss is a stenographer of errors, and the record here must
carry all of them.

    DEAL_KEYS           the two fields of the deal, in order
    MEMO_KEYS           the world's own memo keys, echoed here for the check
    AUDIT_KEYS          the two fields of the audit, in order
    LINE_KEYS           the four fields of one audit line, in order
    MATCH               the verdict an agreeing line answers
    OFF                 the verdict a line the model disagrees with answers
    MAX_IRR_BP          the wall the recomputations' searches never cross
    MemoError           the refusal this stage raises
    memo(estate, deal)  -> the sponsor's recorded memo
    audit(estate, memo, deal) -> AUDIT_KEYS: every line, named, with both numbers

    A memo that does not shape like the world's own, a deal the record does
    not price, and a memo whose own deal disagrees with the one handed over
    are refused by name. A wrong line is never a refusal — it is the
    founding data of the audit.
"""

import dates
import estate

DEAL_KEYS = ("entry_multiple_bp", "exit_multiple_bp")

MEMO_KEYS = ("deal", "irr_bp", "moic_bp", "carry_bp", "growth_bp", "multiple_bp",
             "leverage_bp", "debt_path", "limits_path", "exit_gross_cents",
             "exit_cash_cents", "exit_equity_cents", "worst_irr_bp")

MEMO_PATH_KEYS = ("year", "closing_cents", "distribution_cents", "cure_cents")

MEMO_LIMIT_KEYS = ("year_end", "limit_bp")

AUDIT_KEYS = ("lines", "wrong")

LINE_KEYS = ("line", "claimed", "model", "verdict")

EXIT_VALUES_KEYS = ("gross_cents", "cash_cents", "sponsor_equity_cents")

MATCH = "match"

OFF = "off"

MAX_IRR_BP = 30000


class MemoError(ValueError):
    """The refusal this stage raises: an audit that cannot be opened.

    It names the offender — the memo that does not shape like the world's
    own, its deal against the one handed over, the deal whose multiples the
    market never quoted — because an audit of a document it cannot open is
    a signature on paper the auditor never read.
    """


def _deal(estate, deal):
    if not isinstance(deal, dict):
        raise MemoError("the memo: the deal is a %s, not a record" % (type(deal).__name__,))
    for key in DEAL_KEYS:
        if key not in deal:
            raise MemoError("the memo: the deal does not answer %s" % (key,))
        multiple = deal[key]
        if isinstance(multiple, bool) or not isinstance(multiple, int):
            raise MemoError("the memo: the deal's %s is not a whole number of bp" % (key,))
    if deal["entry_multiple_bp"] != estate.entry_multiple_bp() \
            or deal["exit_multiple_bp"] != estate.exit_multiple_bp():
        raise MemoError("the memo: the deal at %d in and %d out is not the %d in and "
                        "%d out the estate recorded"
                        % (deal["entry_multiple_bp"], deal["exit_multiple_bp"],
                           estate.entry_multiple_bp(), estate.exit_multiple_bp()))
    return deal


def _memo(estate, values):
    if not isinstance(values, dict):
        raise MemoError("the memo: what arrived is a %s, not the sponsor's record"
                        % (type(values).__name__,))
    for key in MEMO_KEYS:
        if key not in values:
            raise MemoError("the memo: the sponsor's record does not answer %s" % (key,))
    return values


def memo(estate, deal):
    """The sponsor's memo, as the world recorded it — including the lines its
    sponsor's own arithmetic wrote for itself. The deal must be the recorded
    one, and must match the memo's own record of it."""
    deal = _deal(estate, deal)
    values = _memo(estate, estate.memo())
    if values["deal"].get("entry_multiple_bp") != deal["entry_multiple_bp"] \
            or values["deal"].get("exit_multiple_bp") != deal["exit_multiple_bp"]:
        raise MemoError("the memo: the sponsor's record says the deal is %d in and %d "
                        "out, and the audit was handed %d in and %d out"
                        % (values["deal"].get("entry_multiple_bp"),
                           values["deal"].get("exit_multiple_bp"),
                           deal["entry_multiple_bp"], deal["exit_multiple_bp"]))
    return dict(values)


def _operating(estate, year):
    """The year's free cash flow and EBITDA, re-implemented from the recorded
    inputs and the policy's bands. No stage borrows a stage: the build is
    local here and lands on the estate's own recorded line."""
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
                ebitda=actual["ebitda_cents"])


def _walk(estate, entry_multiple_bp=None, exit_multiple_bp=None):
    """The recorded deal's whole waterfall — or a scaled one, for the cells
    the sensitivity range re-grids — rebuilt locally: the balances path, the
    distributions, the cure, and the sale."""
    entry = entry_multiple_bp or estate.entry_multiple_bp()
    end_quote = exit_multiple_bp or estate.exit_multiple_bp()
    scale = 10000 if entry == estate.entry_multiple_bp() \
        else entry * 10000 // estate.entry_multiple_bp()
    purchase = estate.entry_ebitda_cents() * entry // 10000
    fees = 0
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    for fee in estate.fee_rows():
        if fee["basis"] == "purchase":
            fees += purchase * fee["bp"] // 10000
        else:
            terms = terms_by_name[fee["name"].replace("arrangement-", "")]
            fees += terms["drawn_cents"] * scale // 10000 * fee["bp"] // 10000
    balances = dict((terms["name"], terms["drawn_cents"] * scale // 10000)
                    for terms in estate.tranches())
    order = tuple(terms["name"] for terms in estate.tranches())
    debt = sum(balances.values())
    equity = purchase + fees + estate.min_cash_cents() - debt
    ends = estate.year_ends()
    events = []
    rows = []
    cash = estate.min_cash_cents()
    for walk_year in range(1, len(ends) + 1):
        operating = _operating(estate, walk_year)
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
        projected = cash + operating["free"] - sum(interest.values()) \
            - sum(amortisation.values())
        revolver = terms_by_name["revolver"]
        if projected < cash:
            undrawn = revolver["commitment_cents"] * scale // 10000 - balances["revolver"]
            if undrawn < 0:
                raise MemoError("the memo: at %d bp the revolver's draw runs past "
                                "its own commitment — the deal cannot fund"
                                % (entry,))
            draw = min(cash - projected, undrawn)
            balances["revolver"] += draw
            projected += draw
        else:
            draw = 0
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
        cure_total = estate.cure(walk_year)
        cure_on = dict((name, 0) for name in order)
        if cure_total:
            left = cure_total
            for name in estate.cure_order():
                take = min(left, balances[name])
                if take:
                    balances[name] -= take
                    cure_on[name] = take
                    left -= take
                if left == 0:
                    break
        cash = estate.min_cash_cents() if excess >= 0 else projected
        if max(0, remaining):
            events.append((ends[walk_year - 1], max(0, remaining)))
        if cure_total:
            events.append((ends[walk_year - 1], -cure_total))
        rows.append(dict(zip(MEMO_PATH_KEYS, (
            walk_year, sum(balances.values()), max(0, remaining), cure_total))))
    ebitda = _operating(estate, len(ends))["ebitda"]
    gross = ebitda * end_quote // 10000
    sponsor_equity = gross + cash - sum(balances.values())
    events.append((estate.exit_date(), sponsor_equity))
    return dict(equity=equity, events=events, rows=rows, gross=gross, cash=cash,
                exit_equity=sponsor_equity, years=len(ends))


def _irr(net):
    """The whole-bp search over a net of dated flows, shared shapes with
    stages 7-9 but local, because no stage borrows a stage."""
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
        raise MemoError("the memo: the recomputed flows price to zero at zero bp — "
                        "no rate that prices a nothing")
    falling = npv(1) < npv(0)
    pays = (lambda rate: npv(rate) <= 0) if falling else (lambda rate: npv(rate) >= 0)
    if not pays(MAX_IRR_BP):
        raise MemoError("the memo: no rate in 0..%d bp prices the recomputed flows "
                        "— the wall holds" % (MAX_IRR_BP,))
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


def _net(estate, flows):
    """The flows aggregated onto the walk's own year indices: the entry date
    is year `0`, each year end its own year."""
    net = {}
    for date, cents in flows:
        if date == estate.entry_date():
            index = 0
        elif date in estate.year_ends():
            index = estate.year_ends().index(date) + 1
        else:
            raise MemoError("the memo: %s is not a date the walk moves on" % (date,))
        net[index] = net.get(index, 0) + cents
    return net


def _unlevered(estate, ebitda, multiple):
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
    for index, _date in enumerate(ends, start=1):
        free = _operating(estate, index)["free"]
        if free < 0:
            raise MemoError("the memo: year %d's unlevered line is %d — an absorption "
                            "an all-equity sponsor has nothing to route"
                            % (index, free))
        if index < len(ends):
            net[index] = free
        else:
            net[index] = ebitda * multiple // 10000 + estate.min_cash_cents()
    return net


def _model(estate):
    """Everything the audit compares, recomputed once: the whole IRR, the
    money multiple, the engines' parts, the debt path, the exit, and the
    sensitivity's worst cell."""
    walked = _walk(estate)
    flows = [(estate.entry_date(), 0 - walked["equity"])] + list(walked["events"])
    whole = _irr(_net(estate, flows))
    invested = sum(0 - cents for _date, cents in flows if cents < 0)
    collected = sum(cents for _date, cents in flows if cents > 0)
    moic = collected * 10000 // invested
    e0 = estate.entry_ebitda_cents()
    e1 = estate.actuals(walked["years"])["ebitda_cents"]
    carry = _irr(_unlevered(estate, e0, estate.entry_multiple_bp()))
    growth = _irr(_unlevered(estate, e1, estate.entry_multiple_bp()))
    re_rated = _irr(_unlevered(estate, e1, estate.exit_multiple_bp()))
    parts = dict(carry=carry, growth=growth - carry, multiple=re_rated - growth,
                 leverage=whole - re_rated)
    worst = MAX_IRR_BP
    for entry_quote in estate.entry_quotes():
        for exit_quote in estate.exit_quotes():
            cell = _walk(estate, entry_multiple_bp=entry_quote,
                         exit_multiple_bp=exit_quote)
            cell_net = _net(estate, [(estate.entry_date(), 0 - cell["equity"])]
                            + list(cell["events"]))
            rate = _irr(cell_net)
            if rate < worst:
                worst = rate
    return dict(irr_bp=whole, moic_bp=moic, debt_path=tuple(walked["rows"]),
                exit=dict(zip(EXIT_VALUES_KEYS, (walked["gross"], walked["cash"],
                                                 walked["exit_equity"]))),
                parts=parts, worst=worst)


def audit(estate, values, deal):
    """The memo, line by line, against the model.

    Every number the memo claims is recomputed from the estate: the IRR, the
    multiple, the engines' parts, the year-by-year debt path, the covenant
    table, the exit and the sensitivity range's worst cell. A line answers
    its own name, the memo's number, the model's, and a verdict — `match`
    when the two integers agree and `off` when they do not — and the audit's
    own `wrong` count is what a reader's eye would otherwise have to count.

    The audit refuses a memo that does not shape like the world's own, a
    deal whose multiples the market does not quote, and a memo whose own
    deal disagrees with the one the audit was handed. Wrong lines are data,
    never refusals."""
    deal = _deal(estate, deal)
    values = _memo(estate, values)
    if values["deal"].get("entry_multiple_bp") != deal["entry_multiple_bp"] \
            or values["deal"].get("exit_multiple_bp") != deal["exit_multiple_bp"]:
        raise MemoError("the audit: the memo's own deal reads %d in and %d out against "
                        "the audit's %d in and %d out"
                        % (values["deal"].get("entry_multiple_bp"),
                           values["deal"].get("exit_multiple_bp"),
                           deal["entry_multiple_bp"], deal["exit_multiple_bp"]))
    model = _model(estate)
    lines = []
    for name, claimed_value, model_value in (
        ("irr_bp", values["irr_bp"], model["irr_bp"]),
        ("moic_bp", values["moic_bp"], model["moic_bp"]),
        ("carry_bp", values["carry_bp"], model["parts"]["carry"]),
        ("growth_bp", values["growth_bp"], model["parts"]["growth"]),
        ("multiple_bp", values["multiple_bp"], model["parts"]["multiple"]),
        ("leverage_bp", values["leverage_bp"], model["parts"]["leverage"]),
    ):
        lines.append(dict(zip(LINE_KEYS, (name, claimed_value, model_value,
                                          MATCH if claimed_value == model_value
                                          else OFF))))
    for claimed_row, model_row in zip(values["debt_path"], model["debt_path"]):
        name = "debt-path year %d" % (claimed_row["year"],)
        claimed = dict(zip(("closing_cents", "distribution_cents", "cure_cents"),
                           (claimed_row["closing_cents"],
                            claimed_row["distribution_cents"], claimed_row["cure_cents"])))
        reworked = dict(zip(("closing_cents", "distribution_cents", "cure_cents"),
                            (model_row["closing_cents"], model_row["distribution_cents"],
                             model_row["cure_cents"])))
        lines.append(dict(zip(LINE_KEYS, (name, claimed, reworked,
                                          MATCH if claimed == reworked else OFF))))
    limits = estate.net_leverage_limits()
    for row in values["limits_path"]:
        name = "limit %s" % (row["year_end"],)
        counted = limits[row["year_end"]]
        lines.append(dict(zip(LINE_KEYS, (name, row["limit_bp"], counted,
                                          MATCH if row["limit_bp"] == counted
                                          else OFF))))
    claimed_exit = dict(zip(EXIT_VALUES_KEYS, (values["exit_gross_cents"],
                                               values["exit_cash_cents"],
                                               values["exit_equity_cents"])))
    lines.append(dict(zip(LINE_KEYS, ("exit", claimed_exit, model["exit"],
                                      MATCH if claimed_exit == model["exit"]
                                      else OFF))))
    lines.append(dict(zip(LINE_KEYS, ("worst_irr_bp", values["worst_irr_bp"],
                                      model["worst"],
                                      MATCH if values["worst_irr_bp"] == model["worst"]
                                      else OFF))))
    wrong = len([one for one in lines if one["verdict"] == OFF])
    return dict(zip(AUDIT_KEYS, (tuple(lines), wrong)))


if __name__ == "__main__":
    deal = dict(zip(DEAL_KEYS, (estate.entry_multiple_bp(), estate.exit_multiple_bp())))
    record = memo(estate, deal)
    ruled = audit(estate, record, deal)
    print("the sponsor's memo, audited line by line")
    print("%-24s %-14s %s" % ("line", "verdict", "what changed"))
    for line in ruled["lines"]:
        note = ""
        if line["verdict"] == OFF:
            note = "claimed %r, model %r" % (line["claimed"], line["model"])
        print("%-24s %-14s %s" % (line["line"], line["verdict"], note))
    print("wrong lines: %d of %d" % (ruled["wrong"], len(ruled["lines"])))
