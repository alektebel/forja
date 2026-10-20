"""LBO Model From Scratch — solutions, stage 4: The mandatory prepayment and the cash that sweeps.

Stage 3 produced the table the term sheet mandates; this stage produces the
waterfall that moves cash. It is a state machine: the caller hands over the
balance sheet as it stands — every tranche's balance and the cash the books
carry — and the stage hands back what one walk year does to it. Interest is
first, on the balances the state carries; then the mandatory pieces; then the
revolver, drawn when the year's short needs it and repaid first from every
excess; then the term loan B's sweep, which takes its contract fee of what is
left; then the sponsor's cure cheque, wired in the year the world recorded it
and routed top-down through the prepayables; and the remainder is the year's
distribution, with the balance sheet carrying the floor.

The sweep takes a state, not a year's history. A what-if — a balance sheet
after a harder year, a state the check builds out of its own arithmetic —
flows through the same waterfall as the recorded one, which is the whole
reason the surface is state-shaped: a mechanism that re-derives rather than
re-reads can be asked about balances nobody recorded.

The stage refuses, by name: a year past the exit (the exit year closes in a
sale), a state that does not shape like a balance sheet, a negative cash
balance, and a revolver booked above what its own terms allow — because a
state that cannot exist has no waterfall to answer and no distribution to
name.

    SWEEP_KEYS          the twelve fields of the year's waterfall, in order
    MAX_TERM_YEARS      the walk's horizon
    SweepError          the refusal this stage raises
    sweep(estate, debt_state, year) -> SWEEP_KEYS: one year, on one state

    The record echoes the state it was handed as the year's opening, answers
    the aggregate columns of the waterfall, and carries the state the next
    year's opening must be — the closing balances and the cash the floor held.
"""

import dates

SWEEP_KEYS = ("year", "year_end", "opening", "rows", "interest_cents",
              "mandatory_amort_cents", "draw_cents", "repay_cents", "sweep_cents",
              "cure_cents", "distribution_cents", "state")

ROW_KEYS = ("name", "basis", "rate_bp", "opening_cents", "interest_cents",
            "mandatory_amort_cents", "draw_cents", "repay_cents", "mandatory_close_cents")

MAX_TERM_YEARS = 5


class SweepError(ValueError):
    """The refusal this stage raises: a waterfall that cannot be run.

    It names the offender — the year past the exit, the balance sheet that
    does not shape like one, the cash that is negative, the revolver booked
    above its own terms — because a state the world cannot have held is a
    state no waterfall answers, and pretending otherwise is how a model
    distributes money that was never there.
    """


def _state(estate, state, year):
    """The caller's state, shaped and tied to terms, or a refusal naming it."""
    if not isinstance(state, dict):
        raise SweepError("the sweep: the state is a %s, not a balance sheet"
                         % (type(state).__name__,))
    balances = state.get("balances")
    cash = state.get("cash_cents")
    if not isinstance(balances, dict):
        raise SweepError("the sweep: the state's balances are a %s, not a record"
                         % (type(balances).__name__,))
    if isinstance(cash, bool) or not isinstance(cash, int):
        raise SweepError("the sweep: the state's cash_cents is not an integer count "
                         "of cents" % ())
    if cash < 0:
        raise SweepError("the sweep: the state's cash of %d is negative" % (cash,))
    for terms in estate.tranches():
        if terms["name"] not in balances:
            raise SweepError("the sweep: the state holds no balance for %s" % (terms["name"],))
        if not isinstance(balances[terms["name"]], int) \
                or isinstance(balances[terms["name"]], bool):
            raise SweepError("the sweep: the state's %s balance is not a whole number"
                             % (terms["name"],))
    revolver = [terms for terms in estate.tranches() if terms["name"] == "revolver"][0]
    if balances.get("revolver", 0) > revolver["commitment_cents"]:
        raise SweepError("the sweep: the revolver is booked at %d, %d above what its "
                         "own terms draw"
                         % (balances["revolver"],
                            balances["revolver"] - revolver["commitment_cents"]))
    return balances, cash


def sweep(estate, debt_state, year):
    """One walk year's waterfall, on the state the caller hands over.

    The opening is the state as handed: every tranche's balance and the cash
    the books carry. Interest is charged on those balances at each tranche's
    own rate and day count; the mandatory amortisation is paid while the term
    runs; the revolver is drawn to the floor when the year's cash falls
    short of it and repaid first from everything left above it; the term loan
    B sweeps its contract fee of the rest; the cure cheque, when the world
    records one for the year, lands top-down through the prepayables; and
    whatever survives is the year's distribution, the cash the balance sheet
    then carries.

    A year past the exit is refused — the exit year closes in a sale — and
    so is a state that does not shape like a balance sheet, one with a
    negative cash, or a revolver booked above its own commitment.
    """
    if isinstance(year, bool) or not isinstance(year, int):
        raise SweepError("the sweep: %s is not a walk year" % (year,))
    if year < 1 or year > MAX_TERM_YEARS:
        raise SweepError("the sweep: year %d walks past the exit — the exit year "
                         "closes in a sale" % (year,))
    balances, cash = _state(estate, debt_state, year)
    terms_by_name = dict((terms["name"], terms) for terms in estate.tranches())
    order = tuple(terms["name"] for terms in estate.tranches())
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
    free = actual["ebitda_cents"] - tax - capex - absorption
    rows = []
    ends = estate.year_ends()
    start = estate.entry_date() if year == 1 else ends[year - 2]
    total_interest = 0
    total_amortisation = 0
    for name in order:
        terms = terms_by_name[name]
        opening = balances[name]
        days = dates.day_count(start, ends[year - 1], terms["basis"])
        interest = opening * terms["rate_bp"] * days \
            // (estate.year_days(terms["basis"]) * 10000)
        amortisation = terms["amort_cents"] if year <= terms["amort_years"] else 0
        rows.append(dict(zip(ROW_KEYS, (name, terms["basis"], terms["rate_bp"],
                                        opening, interest, amortisation, 0, 0,
                                        opening - amortisation))))
        total_interest += interest
        total_amortisation += amortisation
        balances[name] = opening - amortisation
    revolver_row = None
    for attempt in rows:
        if attempt["name"] == "revolver":
            revolver_row = attempt
    projected = cash + free - total_interest - total_amortisation
    draw = 0
    if projected < estate.min_cash_cents():
        revolver = terms_by_name["revolver"]
        undrawn = revolver["commitment_cents"] - balances["revolver"]
        if undrawn < 0:
            raise SweepError("the sweep: the revolver's draw would be %d above its own "
                             "commitment of %d" % (-undrawn, revolver["commitment_cents"]))
        draw = min(estate.min_cash_cents() - projected, undrawn)
        revolver_row["draw_cents"] = draw
        balances["revolver"] += draw
        projected += draw
    excess = projected - estate.min_cash_cents()
    repay = min(excess, balances["revolver"]) if excess > 0 else 0
    revolver_row["repay_cents"] = repay
    balances["revolver"] -= repay
    revolver_row["mandatory_close_cents"] = revolver_row["opening_cents"] \
        - revolver_row["mandatory_amort_cents"] + revolver_row["draw_cents"] \
        - revolver_row["repay_cents"]
    balances["revolver"] = revolver_row["mandatory_close_cents"]
    remaining = excess - repay
    sweeping = terms_by_name["term-loan-b"]
    sweep_amount = 0
    tl_row = None
    for attempt in rows:
        if attempt["name"] == "term-loan-b":
            tl_row = attempt
    if remaining > 0 and sweeping["sweep_bp"]:
        sweep_amount = min(remaining * sweeping["sweep_bp"] // 10000,
                           balances["term-loan-b"])
        balances["term-loan-b"] -= sweep_amount
        tl_row["mandatory_close_cents"] = balances["term-loan-b"]
    remaining = remaining - sweep_amount
    cure_total = estate.cure(year)
    if cure_total:
        left = cure_total
        for name in estate.cure_order():
            take = min(left, balances[name])
            if take:
                balances[name] -= take
                left -= take
            if left == 0:
                break
    distribution = remaining if remaining > 0 else 0
    carried = estate.min_cash_cents() if excess >= 0 else projected
    state = dict(zip(("balances", "cash_cents"), (dict(balances), carried)))
    return dict(zip(SWEEP_KEYS, (year, ends[year - 1],
                                 dict(zip(("balances", "cash_cents"),
                                          (dict(debt_state["balances"]),
                                           debt_state["cash_cents"]))),
                                 tuple(rows), total_interest, total_amortisation,
                                 draw, repay, sweep_amount, cure_total, distribution,
                                 state)))
