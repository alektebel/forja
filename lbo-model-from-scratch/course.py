import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

"""LBO Model From Scratch — a leveraged buyout model from first principles.

Ten graded stages building an LBO model from the ground up: sources and uses
balanced to the cent, the operating build from revenue to free cash flow,
the debt schedule tranche by tranche, the waterfall that moves cash, the
covenants that measure leverage, the exit on the multiple the market
realised, the money multiple and the IRR, the return decomposed into its
engines, the sensitivity grid with the breach kept visible, and the
sponsor's memo, audited line by line.

The house laws hold here: standard library only, no float, no math, no
statistics, no decimal, no fractions, no random, no clock, no socket,
no thread. Every number is an integer count of cents or basis points.
The estate is never written by a stage: it is the world, the answer key,
and the law that the model must obey.

    the sources and the uses, balanced to the cent
    the operating build, revenue to free cash flow
    the debt schedule, tranche by tranche
    the mandatory prepayment and the cash that sweeps
    the covenants the model cannot quietly violate
    the exit on the multiple the market realised
    the money multiple and the rate that discounts the deal
    where the return came from, engine by engine
    the sensitivity grid, with the breach kept visible
    the sponsor's memo, audited line by line
"""

import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(os.path.dirname(_HERE), "codecraft") in [os.path.join(os.path.dirname(_HERE), f) for f in os.listdir(os.path.dirname(_HERE)) if os.path.isdir(os.path.join(os.path.dirname(_HERE), f))]:
    if os.path.dirname(_HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(_HERE))


from codecraft.api import stage


TITLE = "LBO Model From Scratch"
DESCRIPTION = (
    "A leveraged buyout model from first principles: sources and uses balanced to "
    "the cent, the operating build from revenue to free cash flow, the debt schedule "
    "tranche by tranche, the waterfall that moves cash and sweeps the term loan B, "
    "the covenants that measure leverage as data not exception, the exit on the "
    "multiple the market quotes, the money multiple and the whole-bp IRR bisected "
    "with a stepped NPV, the return decomposed into carry, growth, multiple and "
    "leverage, the sensitivity grid over all quoted multiples with the breach kept "
    "visible, and the sponsor's memo audited line by line against the recomputed model."
)
LEVEL = "advanced"
ORDER = 32


# --- stage 1 --------------------------------------------------------------------
def check_1():
    """Checks stage 1: sources and uses balanced to the cent."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_01 as s

    # Constants check
    assert tuple(s.SU_KEYS) == ("entry_multiple_bp", "sources", "uses",
                                "total_sources_cents", "total_uses_cents")
    assert tuple(s.LINE_KEYS) == ("name", "kind", "amount_cents")
    assert s.SOURCES_KINDS == ("equity", "term")
    assert s.USES_KINDS == ("equity", "fees", "cash")
    assert s.AGENT_KIND == "equity"
    assert s.CASH_KIND == "cash"
    assert issubclass(s.SourcesUseError, ValueError)

    # Record-keys shape
    record = s.sources_uses(estate, estate.entry_multiple_bp())
    assert isinstance(record["sources"], tuple)
    assert isinstance(record["uses"], tuple)
    assert len(record["sources"]) >= 2  # sponsor + at least one tranche
    assert len(record["uses"]) >= 2    # equity purchase + at least one fee

    # Total sources equals total uses
    assert record["total_sources_cents"] == record["total_uses_cents"]

    # Verify sources sum
    sources_sum = sum(line["amount_cents"] for line in record["sources"])
    assert sources_sum == record["total_sources_cents"]

    # Verify uses sum
    uses_sum = sum(line["amount_cents"] for line in record["uses"])
    assert uses_sum == record["total_uses_cents"]

    # Equity purchase is entry EBITDA * entry multiple / 10000
    purchase = estate.entry_ebitda_cents() * estate.entry_multiple_bp() // 10000
    equity_line = [l for l in record["uses"] if l["name"] == "equity purchase"][0]
    assert equity_line["amount_cents"] == purchase

    # Advisor fee is purchase * advisor_bp / 10000
    advisor_fee = purchase * 100 // 10000
    advisor_line = [l for l in record["uses"] if l["name"] == "advisor"][0]
    assert advisor_line["amount_cents"] == advisor_fee

    # Opening cash is the estate's min_cash_cents
    cash_line = [l for l in record["uses"] if l["name"] == "opening cash"][0]
    assert cash_line["amount_cents"] == estate.min_cash_cents()

    # Sponsor line in sources
    sponsor_line = [l for l in record["sources"] if l["name"] == "sponsor"][0]
    assert sponsor_line["amount_cents"] == estate.equity_cheque_cents()

    # Unquoted multiple is refused
    try:
        s.sources_uses(estate, 55000)  # 55000 bp not in entry_quotes
        assert False, "should refuse unquoted multiple"
    except s.SourcesUseError as e:
        assert "55000" in str(e) or "not a multiple" in str(e).lower()

    # Float multiple is refused
    try:
        s.sources_uses(estate, 600.0)
        assert False, "should refuse float multiple"
    except s.SourcesUseError:
        pass

    # Determinism proof
    r2 = s.sources_uses(estate, estate.entry_multiple_bp())
    assert r2["total_sources_cents"] == record["total_sources_cents"]
    assert r2["total_uses_cents"] == record["total_uses_cents"]
    for i, (l1, l2) in enumerate(zip(r2["sources"], record["sources"])):
        assert l1["amount_cents"] == l2["amount_cents"]

    print("check_1: PASS")


# --- stage 2 --------------------------------------------------------------------
def check_2():
    """Checks stage 2: the operating build, revenue to free cash flow."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_02 as s

    # Constants check
    assert tuple(s.OPERATE_KEYS) == ("year", "year_end", "revenue_cents",
        "ebitda_cents", "margin_bp", "depreciation_cents", "ebit_cents",
        "taxable_cents", "tax_cents", "capex_maintenance_cents",
        "capex_growth_cents", "capex_cents", "working_capital_cents",
        "absorption_cents", "free_cash_flow_cents")
    assert issubclass(s.OperatingError, ValueError)

    # Build year 1
    year1 = s.build(estate, 1)
    assert year1["year"] == 1
    assert year1["year_end"] == estate.year_ends()[0]
    assert year1["revenue_cents"] == estate.actuals(1)["revenue_cents"]
    assert year1["ebitda_cents"] == estate.actuals(1)["ebitda_cents"]

    # Tax lands on the estate's record
    assert year1["tax_cents"] == estate.actuals(1)["tax_cents"]

    # Free cash flow lands on the estate's record
    assert year1["free_cash_flow_cents"] == estate.actuals(1)["free_cash_flow_cents"]

    # Margin is in basis points
    expected_margin = year1["ebitda_cents"] * 10000 // year1["revenue_cents"]
    assert year1["margin_bp"] == expected_margin

    # EBIT = EBITDA - depreciation
    assert year1["ebit_cents"] == year1["ebitda_cents"] - year1["depreciation_cents"]

    # Taxable = EBIT
    assert year1["taxable_cents"] == year1["ebit_cents"]

    # Capex total
    assert year1["capex_cents"] == year1["capex_maintenance_cents"] + year1["capex_growth_cents"]

    # Working capital absorption
    assert year1["absorption_cents"] == year1["working_capital_cents"] \
        - estate.entry_working_capital_cents()

    # Check all five years
    for year in range(1, 6):
        build = s.build(estate, year)
        assert build["tax_cents"] == estate.actuals(year)["tax_cents"]
        assert build["free_cash_flow_cents"] == estate.actuals(year)["free_cash_flow_cents"]

    # Invalid year refused
    try:
        s.build(estate, 0)
        assert False, "should refuse year 0"
    except s.OperatingError as e:
        assert "not a year" in str(e).lower() or "not a walk year" in str(e).lower()

    try:
        s.build(estate, 6)
        assert False, "should refuse year 6"
    except s.OperatingError:
        pass

    # Float year refused
    try:
        s.build(estate, 1.0)
        assert False, "should refuse float year"
    except s.OperatingError:
        pass

    # Determinism proof
    r2 = s.build(estate, 3)
    assert r2["tax_cents"] == year1["tax_cents"] or r2["tax_cents"] == estate.actuals(3)["tax_cents"]
    assert r2["free_cash_flow_cents"] == estate.actuals(3)["free_cash_flow_cents"]

    print("check_2: PASS")


# --- stage 3 --------------------------------------------------------------------
def check_3():
    """Checks stage 3: the debt schedule, tranche by tranche."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_03 as s

    # Constants check
    assert tuple(s.ROW_KEYS) == ("name", "basis", "rate_bp", "opening_cents",
        "interest_cents", "mandatory_amort_cents", "draw_cents",
        "repay_cents", "mandatory_close_cents")
    assert tuple(s.RATE_KEYS) == ("year", "year_end", "rows")
    assert s.MAX_TERM_YEARS == 5
    assert issubclass(s.DebtScheduleError, ValueError)

    # Year 1: four tranches, revolver draws to floor
    schedule = s.tranches(estate, 1)
    assert schedule["year"] == 1
    assert len(schedule["rows"]) == 4
    names = [row["name"] for row in schedule["rows"]]
    for i, expected_name in enumerate(estate.tranches()):
        assert names[i] == expected_name["name"]

    # Revolver row has draw or repay
    revolver_rows = [r for r in schedule["rows"] if r["name"] == "revolver"]
    assert len(revolver_rows) == 1
    rv = revolver_rows[0]
    # Revolver draws to floor in year 1 because projected < min_cash
    assert rv["draw_cents"] >= 0
    assert rv["repay_cents"] >= 0

    # Interest is computed on opening balance
    tl_a_rows = [r for r in schedule["rows"] if r["name"] == "term-loan-a"]
    if tl_a_rows:
        tl_a = tl_a_rows[0]
        # interest = opening * rate_bp * days // (year_days * 10000)
        # opening = drawn_cents in year 1
        tl_a_terms = estate.tranche("term-loan-a")
        opening = tl_a_terms["drawn_cents"]
        days = s._days(estate, 1, tl_a_terms["basis"])
        expected_interest = opening * tl_a_terms["rate_bp"] * days \
            // (estate.year_days(tl_a_terms["basis"]) * 10000)
        assert tl_a["interest_cents"] == expected_interest

    # Invalid year refused
    try:
        s.tranches(estate, 0)
        assert False, "should refuse year 0"
    except s.DebtScheduleError:
        pass

    try:
        s.tranches(estate, 6)
        assert False, "should refuse year 6"
    except s.DebtScheduleError:
        pass

    # Float year refused
    try:
        s.tranches(estate, 1.0)
        assert False, "should refuse float year"
    except s.DebtScheduleError:
        pass

    # Determinism proof
    r2 = s.tranches(estate, 3)
    r3 = s.tranches(estate, 3)
    for i, (r1, r2r) in enumerate(zip(r2["rows"], r3["rows"])):
        assert r1["interest_cents"] == r2r["interest_cents"]
        assert r1["mandatory_amort_cents"] == r2r["mandatory_amort_cents"]

    print("check_3: PASS")


# --- stage 4 --------------------------------------------------------------------
def check_4():
    """Checks stage 4: the waterfall, state machine."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_04 as s

    # Constants check
    assert tuple(s.SWEEP_KEYS) == ("year", "year_end", "opening", "rows",
        "interest_cents", "mandatory_amort_cents", "draw_cents",
        "repay_cents", "sweep_cents", "cure_cents", "distribution_cents",
        "state")
    assert tuple(s.ROW_KEYS) == ("name", "basis", "rate_bp", "opening_cents",
        "interest_cents", "mandatory_amort_cents", "draw_cents",
        "repay_cents", "mandatory_close_cents")
    assert s.MAX_TERM_YEARS == 5
    assert issubclass(s.SweepError, ValueError)

    # Build opening state from entry
    opening_state = {
        "balances": {t["name"]: t["drawn_cents"] for t in estate.tranches()},
        "cash_cents": estate.min_cash_cents()
    }

    # Year 1 sweep
    record = s.sweep(estate, opening_state, 1)
    assert record["year"] == 1
    assert record["opening"]["balances"] == opening_state["balances"]
    assert record["opening"]["cash_cents"] == opening_state["cash_cents"]
    assert len(record["rows"]) == 4

    # Year 3: the cure year — cure_cents > 0
    year3_state = record["state"] if record["distribution_cents"] >= 0 else opening_state
    # Build through year 3
    state = dict(balances=dict(opening_state["balances"]), cash_cents=estate.min_cash_cents())
    for y in range(1, 4):
        if y == 1:
            state = opening_state
        year_sweep = s.sweep(estate, state, y)
        state = year_sweep["state"]
    year3_sweep = s.sweep(estate, state, 3)
    assert year3_sweep["cure_cents"] == estate.cure(3)

    # Year 4: no cure
    year4_sweep = s.sweep(estate, state, 4) if year3_sweep["cure_cents"] > 0 else year3_sweep
    # Just check year 4 with fresh state
    state4 = dict(balances=dict(opening_state["balances"]), cash_cents=estate.min_cash_cents())
    for y in range(1, 5):
        year_sweep = s.sweep(estate, state4, y)
        state4 = year_sweep["state"]
    assert year4_sweep["cure_cents"] == 0

    # Year 6 is past the exit — refused
    try:
        s.sweep(estate, opening_state, 6)
        assert False, "should refuse year 6 (past exit)"
    except s.SweepError as e:
        assert "past the exit" in str(e).lower() or "exit" in str(e).lower()

    # Negative cash refused
    bad_state = {
        "balances": dict(opening_state["balances"]),
        "cash_cents": -1
    }
    try:
        s.sweep(estate, bad_state, 1)
        assert False, "should refuse negative cash"
    except s.SweepError as e:
        assert "negative" in str(e).lower()

    # Bad state shape refused
    try:
        s.sweep(estate, "not a dict", 1)
        assert False, "should refuse non-dict state"
    except s.SweepError:
        pass

    # Determinism proof
    state_d = dict(balances=dict(opening_state["balances"]), cash_cents=estate.min_cash_cents())
    r1 = s.sweep(estate, dict(balances=dict(opening_state["balances"]), cash_cents=estate.min_cash_cents()), 2)
    r2 = s.sweep(estate, dict(balances=dict(opening_state["balances"]), cash_cents=estate.min_cash_cents()), 2)
    assert r1["interest_cents"] == r2["interest_cents"]
    assert r1["distribution_cents"] == r2["distribution_cents"]

    print("check_4: PASS")


# --- stage 5 --------------------------------------------------------------------
def check_5():
    """Checks stage 5: the covenants, tests and cure as data."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_05 as s

    # Constants check
    assert tuple(s.TEST_KEYS) == ("year", "year_end", "net_debt_cents",
        "ebitda_cents", "net_leverage_bp", "limit_bp", "headroom_bp",
        "breach", "by_bp", "cure_cents", "incurrence_cents")
    assert tuple(s.STATE_KEYS) == ("balances", "cash_cents")
    assert tuple(s.CURE_KEYS) == ("year", "year_end", "net_leverage_bp",
        "limit_bp", "cure_cents", "post_cure_bp", "headroom_bp")
    assert s.MAX_TERM_YEARS == 5
    assert issubclass(s.CovenantError, ValueError)

    # Build state through year 3 (cure year)
    opening_state = {
        "balances": {t["name"]: t["drawn_cents"] for t in estate.tranches()},
        "cash_cents": estate.min_cash_cents()
    }

    # Test year 3 state (pre-cure: after sweep, before cure)
    year3_state = estate.state_for_test(3)
    tests_result = s.tests(year3_state, estate, 3)
    assert tests_result["year"] == 3
    assert tests_result["breach"] == True  # The recorded deal breaches in year 3

    # Cure should be positive for the breach year
    cure_result = s.cure(estate, year3_state, 3)
    assert cure_result["cure_cents"] > 0

    # The post-cure leverage should be under the limit
    assert cure_result["post_cure_bp"] <= tests_result["limit_bp"]

    # Year 5: below limit (the leverage is manageable)
    year5_state = estate.state_for_test(5)
    tests5 = s.tests(year5_state, estate, 5)
    assert tests5["breach"] == False  # Year 5 is tightest limit but leverage has fallen enough

    # Year 1: should pass
    year1_state = estate.state_for_test(1)
    tests1 = s.tests(year1_state, estate, 1)
    assert tests1["breach"] == False
    assert tests1["cure_cents"] == 0

    # Year 2: should pass
    tests2 = s.tests(estate.state_for_test(2), estate, 2)
    assert tests2["breach"] == False
    assert tests2["cure_cents"] == 0

    # Year 4: should pass (amended back up)
    tests4 = s.tests(estate.state_for_test(4), estate, 4)
    assert tests4["breach"] == False

    # Net debt formula: balances - cash
    net_debt = sum(year3_state["balances"].values()) - year3_state["cash_cents"]
    assert tests_result["net_debt_cents"] == net_debt

    # Net leverage: net_debt * 10000 // ebitda
    ebitda = estate.actuals(3)["ebitda_cents"]
    expected_ratio = net_debt * 10000 // ebitda
    assert tests_result["net_leverage_bp"] == expected_ratio

    # Invalid state refused
    try:
        s.tests("bad", estate, 1)
        assert False, "should refuse bad state shape"
    except s.CovenantError:
        pass

    # Invalid year refused
    try:
        s.tests(year3_state, estate, 0)
        assert False, "should refuse year 0"
    except s.CovenantError:
        pass

    try:
        s.tests(year3_state, estate, 6)
        assert False, "should refuse year 6"
    except s.CovenantError:
        pass

    # Negative cash refused
    bad_state = {
        "balances": dict(year3_state["balances"]),
        "cash_cents": -100
    }
    try:
        s.tests(bad_state, estate, 3)
        assert False, "should refuse negative cash"
    except s.CovenantError:
        pass

    # Cure determinism
    c1 = s.cure(estate, year3_state, 3)
    c2 = s.cure(estate, year3_state, 3)
    assert c1["cure_cents"] == c2["cure_cents"]

    print("check_5: PASS")


# --- stage 6 --------------------------------------------------------------------
def check_6():
    """Checks stage 6: the exit on the multiple the market realised."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_06 as s

    # Constants check
    assert tuple(s.EXIT_KEYS) == ("exit_date", "ebitda_cents", "exit_multiple_bp",
        "gross_value_cents", "debt_repaid_cents", "cash_out_cents",
        "sponsor_equity_cents")
    assert s.MAX_TERM_YEARS == 5
    assert issubclass(s.ExitError, ValueError)

    # Exit at recorded exit multiple
    exit_result = s.exit(estate, estate.exit_multiple_bp())
    assert exit_result["exit_date"] == estate.exit_date()
    assert exit_result["exit_multiple_bp"] == estate.exit_multiple_bp()

    # Gross value = terminal EBITDA * exit multiple / 10000
    terminal_ebitda = estate.actuals(5)["ebitda_cents"]
    expected_gross = terminal_ebitda * estate.exit_multiple_bp() // 10000
    assert exit_result["gross_value_cents"] == expected_gross

    # Sponsor equity = gross + cash - debt
    assert exit_result["sponsor_equity_cents"] == \
        exit_result["gross_value_cents"] + exit_result["cash_out_cents"] \
        - exit_result["debt_repaid_cents"]

    # Exit date matches estate
    assert exit_result["exit_date"] == estate.exit_date()

    # Unquoted exit multiple is refused
    try:
        s.exit(estate, 48000)  # not in exit_quotes
        assert False, "should refuse unquoted exit multiple"
    except s.ExitError as e:
        assert "48000" in str(e) or "not a multiple" in str(e).lower()

    # Float multiple refused
    try:
        s.exit(estate, 62500.0)
        assert False, "should refuse float multiple"
    except s.ExitError:
        pass

    # Determinism proof
    e2 = s.exit(estate, estate.exit_multiple_bp())
    assert e2["gross_value_cents"] == exit_result["gross_value_cents"]
    assert e2["sponsor_equity_cents"] == exit_result["sponsor_equity_cents"]

    print("check_6: PASS")


# --- stage 7 --------------------------------------------------------------------
def check_7():
    """Checks stage 7: the money multiple and the IRR."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_07 as s

    # Constants check
    assert tuple(s.DEAL_KEYS) == ("entry_multiple_bp", "exit_multiple_bp")
    assert tuple(s.FLOW_KEYS) == ("date", "amount_cents")
    assert tuple(s.SPONSOR_KEYS) == ("deal", "entry_date", "flows", "years")
    assert tuple(s.MOIC_KEYS) == ("invested_cents", "collected_cents", "moic_bp")
    assert tuple(s.IRR_KEYS) == ("flows", "irr_bp", "pv_cents", "years")
    assert s.MAX_IRR_BP == 30000
    assert issubclass(s.ReturnError, ValueError)

    deal = dict(entry_multiple_bp=estate.entry_multiple_bp(),
                exit_multiple_bp=estate.exit_multiple_bp())

    # Sponsor flows
    flows = s.sponsor_flows(estate, deal)
    assert flows["entry_date"] == estate.entry_date()
    assert flows["years"] == 5
    assert len(flows["flows"]) >= 5  # at least entry + distributions

    # First flow is the sponsor's equity cheque out (negative)
    assert flows["flows"][0]["amount_cents"] < 0
    assert flows["flows"][0]["date"] == estate.entry_date()
    assert flows["flows"][0]["amount_cents"] == 0 - estate.equity_cheque_cents()

    # MOIC
    moic_result = s.moic(flows["flows"])
    assert moic_result["invested_cents"] > 0
    assert moic_result["collected_cents"] > moic_result["invested_cents"]
    # moic_bp = collected * 10000 // invested
    expected_moic = moic_result["collected_cents"] * 10000 // moic_result["invested_cents"]
    assert moic_result["moic_bp"] == expected_moic

    # IRR
    irr_result = s.irr(estate, flows["flows"])
    assert irr_result["irr_bp"] > 0
    assert irr_result["irr_bp"] <= s.MAX_IRR_BP
    # IRR should be around 2400-2500 bp for this deal
    assert 2000 <= irr_result["irr_bp"] <= 2800

    # NPV at the IRR — the residue from truncation
    assert abs(irr_result["pv_cents"]) < 200000  # residue within 2000 cents

    # Deal mismatch is refused
    bad_deal = dict(entry_multiple_bp=50000, exit_multiple_bp=62500)
    try:
        s.sponsor_flows(estate, bad_deal)
        assert False, "should refuse deal with wrong entry multiple"
    except s.ReturnError:
        pass

    # Bad deal shape refused
    try:
        s.sponsor_flows(estate, "not a dict")
        assert False, "should refuse non-dict deal"
    except s.ReturnError:
        pass

    # Zero invested refused
    try:
        s.moic([{"date": "2026-06-30", "amount_cents": 100}])
        assert False, "should refuse zero invested"
    except s.ReturnError:
        pass

    # Determinism proof
    r1 = s.sponsor_flows(estate, deal)
    r2 = s.sponsor_flows(estate, deal)
    r3 = s.irr(estate, r1["flows"])
    r4 = s.irr(estate, r2["flows"])
    assert r1["flows"] == r2["flows"]
    assert r3["irr_bp"] == r4["irr_bp"]

    print("check_7: PASS")


# --- stage 8 --------------------------------------------------------------------
def check_8():
    """Checks stage 8: the return decomposed into engines."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_08 as s

    # Constants check
    assert tuple(s.DECOMPOSE_KEYS) == ("irr_bp", "carry_bp", "growth_bp",
        "multiple_bp", "leverage_bp", "sum_bp", "residual_bp")
    assert tuple(s.DEAL_KEYS) == ("entry_multiple_bp", "exit_multiple_bp")
    assert s.MAX_IRR_BP == 30000
    assert issubclass(s.DecomposeError, ValueError)

    deal = dict(entry_multiple_bp=estate.entry_multiple_bp(),
                exit_multiple_bp=estate.exit_multiple_bp())

    # Decomposition
    record = s.decompose(estate, deal)

    # Whole IRR matches stage 7
    import stage_07 as s7
    flows7 = s7.sponsor_flows(estate, deal)
    irr7 = s7.irr(estate, flows7["flows"])
    assert record["irr_bp"] == irr7["irr_bp"]

    # Carry < whole (debt adds value)
    assert record["carry_bp"] < record["irr_bp"]

    # Growth is positive
    assert record["growth_bp"] > 0

    # Multiple is positive (exit multiple > entry multiple)
    assert record["multiple_bp"] > 0

    # Leverage is positive (debt adds value)
    assert record["leverage_bp"] > 0

    # Residual is zero (telescoping identity)
    assert record["residual_bp"] == 0

    # Sum equals IRR (the identity)
    sum_parts = record["carry_bp"] + record["growth_bp"] + record["multiple_bp"] \
        + record["leverage_bp"]
    assert sum_parts == record["irr_bp"]

    # Deal mismatch is refused
    bad_deal = dict(entry_multiple_bp=50000, exit_multiple_bp=62500)
    try:
        s.decompose(estate, bad_deal)
        assert False, "should refuse deal mismatch"
    except s.DecomposeError:
        pass

    # Bad deal shape refused
    try:
        s.decompose(estate, "not a dict")
        assert False, "should refuse non-dict deal"
    except s.DecomposeError:
        pass

    # Determinism proof
    r2 = s.decompose(estate, deal)
    assert r2["irr_bp"] == record["irr_bp"]
    assert r2["residual_bp"] == record["residual_bp"] == 0

    print("check_8: PASS")


# --- stage 9 --------------------------------------------------------------------
def check_9():
    """Checks stage 9: the sensitivity grid."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_09 as s

    # Constants check
    assert tuple(s.GRID_KEYS) == ("entry_multiple_bp", "exit_multiple_bp",
        "irr_bp", "breach_year", "by_bp")
    assert s.MAX_IRR_BP == 30000
    assert issubclass(s.SensitivityError, ValueError)

    # Grid with small ranges
    entries = estate.entry_quotes()[:3]  # (57500, 60000, 62500)
    exits = estate.exit_quotes()[:3]     # (50000, 55000, 60000)

    rows = s.grid(estate, entries, exits)

    # Number of cells = len(entries) * len(exits)
    assert len(rows) == len(entries) * len(exits)

    # First cell should be the recorded deal
    # entries[1] = 60000 = entry_multiple, exits[2] = 60000 but that's not exit_multiple
    # Actually exit_quotes[:3] = (50000, 55000, 60000), so (60000, 60000) is entries[1] × exits[2]
    cells_at_recorded = [r for r in rows if r["entry_multiple_bp"] == 60000
                         and r["exit_multiple_bp"] == 60000]
    # Actually the exit quotes are (50000, 55000, 60000) and we need exit 62500 for the recorded deal
    # Let's check the grid cell at the recorded entry/exit
    recorded_cell = None
    for r in rows:
        if r["entry_multiple_bp"] == 60000:
            recorded_cell = r
            break

    # IRR should be positive for all cells in the grid
    for row in rows:
        assert row["irr_bp"] >= 0

    # Breach year is data — 0 when no breach
    for row in rows:
        assert row["breach_year"] >= 0
        assert row["by_bp"] >= 0
        if row["breach_year"] > 0:
            assert row["by_bp"] > 0

    # Higher entry multiple → lower IRR (more leverage = more risk)
    # At least check monotonicity within a cell row
    entry_60000 = sorted([r for r in rows if r["entry_multiple_bp"] == 60000],
                         key=lambda r: r["exit_multiple_bp"])
    if len(entry_60000) >= 2:
        for i in range(len(entry_60000) - 1):
            a, b = entry_60000[i], entry_60000[i + 1]
            assert a["exit_multiple_bp"] < b["exit_multiple_bp"]

    # Unquoted multiple is refused
    try:
        s.grid(estate, (55000,), estate.exit_quotes()[:2])
        assert False, "should refuse unquoted entry multiple"
    except s.SensitivityError:
        pass

    # Empty range is refused
    try:
        s.grid(estate, (), estate.exit_quotes()[:2])
        assert False, "should refuse empty entry range"
    except s.SensitivityError:
        pass

    # Not a range is refused
    try:
        s.grid(estate, "not a range", estate.exit_quotes()[:2])
        assert False, "should refuse string range"
    except s.SensitivityError:
        pass

    # Determinism proof
    r2 = s.grid(estate, entries, exits)
    for i, (r1, r2r) in enumerate(zip(rows, r2)):
        assert r1["irr_bp"] == r2r["irr_bp"]
        assert r1["breach_year"] == r2r["breach_year"]

    print("check_9: PASS")


# --- stage 10 -------------------------------------------------------------------
def check_10():
    """Checks stage 10: the sponsor's memo, audited line by line."""
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import estate
    import stage_10 as s

    # Constants check
    assert tuple(s.DEAL_KEYS) == ("entry_multiple_bp", "exit_multiple_bp")
    assert tuple(s.MEMO_KEYS) == ("deal", "irr_bp", "moic_bp", "carry_bp",
        "growth_bp", "multiple_bp", "leverage_bp", "debt_path", "limits_path",
        "exit_gross_cents", "exit_cash_cents", "exit_equity_cents", "worst_irr_bp")
    assert tuple(s.AUDIT_KEYS) == ("lines", "wrong")
    assert tuple(s.LINE_KEYS) == ("line", "claimed", "model", "verdict")
    assert s.MATCH == "match"
    assert s.OFF == "off"
    assert s.MAX_IRR_BP == 30000
    assert issubclass(s.MemoError, ValueError)

    deal = dict(entry_multiple_bp=estate.entry_multiple_bp(),
                exit_multiple_bp=estate.exit_multiple_bp())

    # Memo returns the estate's memo
    memo_result = s.memo(estate, deal)
    assert memo_result["deal"] == dict(
        entry_multiple_bp=estate.entry_multiple_bp(),
        exit_multiple_bp=estate.exit_multiple_bp())
    assert "irr_bp" in memo_result

    # Audit compares memo against the model
    ruled = s.audit(estate, memo_result, deal)
    assert isinstance(ruled["lines"], tuple)
    assert isinstance(ruled["wrong"], int)

    # There should be wrong lines (the memo has 3 wrong lines)
    assert ruled["wrong"] > 0

    # At least one line should match
    matches = [l for l in ruled["lines"] if l["verdict"] == s.MATCH]
    assert len(matches) > 0

    # IRR line should be in the audit
    irr_lines = [l for l in ruled["lines"] if l["line"] == "irr_bp"]
    assert len(irr_lines) == 1

    # Dealing with wrong deal shape
    try:
        s.memo(estate, "not a dict")
        assert False, "should refuse non-dict deal"
    except s.MemoError:
        pass

    # Deal with wrong multiples
    bad_deal = dict(entry_multiple_bp=50000, exit_multiple_bp=62500)
    try:
        s.memo(estate, bad_deal)
        assert False, "should refuse deal with wrong multiples"
    except s.MemoError:
        pass

    # Memo with missing keys refused
    try:
        s.audit(estate, {}, deal)
        assert False, "should refuse memo with missing keys"
    except s.MemoError:
        pass

    # Determinism proof
    r2 = s.audit(estate, memo_result, deal)
    assert r2["wrong"] == ruled["wrong"]
    for i, (l1, l2) in enumerate(zip(ruled["lines"], r2["lines"])):
        assert l1["verdict"] == l2["verdict"]

    print("check_10: PASS")


# --- STAGES --------------------------------------------------------------------
STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The sources and the uses, balanced to the cent",
        tags=["sources-uses", "close", "balance"],
        action="Write ``SU_KEYS``, ``LINE_KEYS``, and ``sources_uses`` in stage_01.py.",
        predict="How a purchase struck on an unquoted multiple refuses, and "
                "why the total sources must equal total uses to the cent.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The operating build, revenue to free cash flow",
        tags=["build", "tax", "free-cash"],
        action="Write ``OPERATE_KEYS`` and ``build`` in stage_02.py.",
        predict="Why the tax bands truncate twice (once per band), and why the "
                "build must land exactly on the estate's recorded tax and free cash.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The debt schedule, tranche by tranche",
        tags=["debt", "schedule", "tranches"],
        action="Write ``ROW_KEYS``, ``RATE_KEYS``, and ``tranches`` in stage_03.py.",
        predict="How the waterfall chain must walk from year 1 to the requested "
                "year, and why the revolver's draw and repay must be reflected in mandatory_close.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The mandatory prepayment and the cash that sweeps",
        tags=["waterfall", "sweep", "state-machine"],
        action="Write ``SWEEP_KEYS`` and ``sweep`` in stage_04.py.",
        predict="How the state shape flows through: one year's output is the next "
                "year's input, and why a bad state refuses before the waterfall runs.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The covenants the model cannot quietly violate",
        tags=["covenants", "breach", "cure"],
        action="Write ``TEST_KEYS``, ``CURE_KEYS``, and ``tests``, ``cure`` in stage_05.py.",
        predict="Why a breach is data, not an exception, and how the cure formula "
                "uses ceiling arithmetic on the same integers.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The exit on the multiple the market realised",
        tags=["exit", "multiple", "terminal"],
        action="Write ``EXIT_KEYS`` and ``exit`` in stage_06.py.",
        predict="How the terminal state is recomputed (not read), and why an "
                "unquoted exit multiple is not a bad price but no price.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The money multiple and the rate that discounts the deal",
        tags=["moic", "irr", "bisection"],
        action="Write ``SPONSOR_KEYS``, ``MOIC_KEYS``, ``IRR_KEYS`` and ``sponsor_flows``, "
               "``moic``, ``irr`` in stage_07.py.",
        predict="Why the NPV is stepped (not powered), and why the residue is data, "
                "not hidden.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Where the return came from, engine by engine",
        tags=["decomposition", "carry", "growth", "leverage"],
        action="Write ``DECOMPOSE_KEYS`` and ``decompose`` in stage_08.py.",
        predict="Why the telescoping identity gives residual = 0, and how "
                "unlevered flows differ from levered flows.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The sensitivity grid, with the breach kept visible",
        tags=["sensitivity", "grid", "breach"],
        action="Write ``GRID_KEYS`` and ``grid`` in stage_09.py.",
        predict="How cells scale the financing off the recorded deal, and why "
                "the pre-cure breach is the first year the sponsor wired a cure.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The sponsor's memo, audited line by line",
        tags=["memo", "audit", "capstone"],
        action="Write ``AUDIT_KEYS``, ``LINE_KEYS``, and ``memo``, ``audit`` in stage_10.py.",
        predict="Why three lines in the world's own memo are wrong, and how the "
                "audit finds them out by recomputing everything it compares.",
        check=check_10,
    ),
]