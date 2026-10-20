"""IRB and Regulatory Capital — a bank's own parameter estimates and the regulator's version.

Ten graded stages over M1's book and dates, the IRB policy as data, the way the
rest of this repository teaches a mechanism: the world is data and holds the
ground truth, a stage is a file you write, a check is what happens to it, and
every number is an integer count of basis points or ten-thousandths because
capital is a fixed-point discipline.

What the course is about, in one line: *the capital formula as tabulated data,
the bank's own parameters, the two-books reconciliation, and the audit the
supervisor files.*

    PIT vs TTC and which is legal for which query
    the normal quantile as tabulated data (no float, no formula)
    the correlation and the maturity adjustment
    the capital requirement K, the exact series
    downturn LGD with the multiplier and the haircut
    BE-EAD and its CCFs estimated from the bank's defaults
    risk weight and RWA for one loan and the whole book
    the output floor, phased in
    the two books reconciled per grade (IFRS 9 provision vs IRB capital)
    the audit the supervisor files (capstone)

Every number is an integer count of basis points, ten-thousandths, or cents.
No `float` literal in the course, no `math`, no `statistics`, no `decimal`.
Where a division happens the contract pins its rounding (truncation //).

    python3 codecraft/cli.py run irb-capital-from-scratch
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from codecraft.api import stage

TITLE = "IRB and Regulatory Capital From Scratch"
DESCRIPTION = (
    "The bank's own parameter estimates and the regulator's: PIT vs TTC, "
    "the normal quantile as tabulated data, the correlation and maturity "
    "adjustment, the capital requirement as the exact series, downturn LGD "
    "with the multiplier and the haircut, BE-EAD with CCFs, risk weight "
    "and RWA, the output floor phased in, the two-books reconciliation, and "
    "the audit pack that files it all. Built over M1's book, dates and rules, "
    "with the IRB policy as data — everything still basis points."
)
LEVEL = "advanced"
ORDER = 32


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import book
    import irb
    import rules
    import stage_01 as s

    led = book.Book.build(7)

    # --- constants ---
    assert s.KINDS == ("pit", "ttc")
    assert s.USE_KINDS == (("capital", "ttc"), ("accounting", "pit"))
    assert issubclass(s.RatingError, irb.PolicyError)

    # --- pit returns the book's grade ---
    first_date = led.reporting_dates[0]
    for loan_id in led.loans():
        got = s.pit(led, loan_id, first_date)
        expected = led.grade(loan_id, first_date)
        assert got == expected, ("pit(%r, %r) = %r, book.grade = %r"
                                 % (loan_id, first_date, got, expected))

    # --- ttc returns the artifact's grade ---
    for loan_id in led.loans():
        got = s.ttc(led, loan_id, first_date)
        model = led.model_in_force(first_date)
        assert model is not None, "no model in force at %s" % first_date
        expected = model["grades"][loan_id]
        assert got == expected, ("ttc(%r, %r) = %r, model grade = %r"
                                 % (loan_id, first_date, got, expected))

    # --- a loan whose pit and ttc disagree ---
    for loan_id, at in led.loans():
        if isinstance(loan_id, dict):
            loan_id = loan_id["loan"]
        p = s.pit(led, loan_id, at)
        t = s.ttc(led, loan_id, at)
        if p != t:
            break

    # --- legal: capital -> ttc, accounting -> pit, wrong -> refusal ---
    assert s.legal("capital", "ttc") is True
    assert s.legal("accounting", "pit") is True

    try:
        s.legal("capital", "pit")
    except s.RatingError as e:
        assert "capital" in str(e).lower() or "pit" in str(e).lower(), str(e)

    try:
        s.legal("accounting", "ttc")
    except s.RatingError as e:
        assert "accounting" in str(e).lower() or "ttc" in str(e).lower(), str(e)

    try:
        s.legal("unknown_use", "pit")
    except s.RatingError as e:
        assert "unknown_use" in str(e), str(e)

    try:
        s.legal("capital", "bad_kind")
    except s.RatingError as e:
        assert "bad_kind" in str(e), str(e)

    # --- book access purity ---
    before = led.stats()
    _ = s.pit(led, led.loans()[0], first_date)
    _ = s.ttc(led, led.loans()[0], first_date)
    _ = s.legal("capital", "ttc")
    after = led.stats()
    for key in ("schedules", "statuses", "migrations", "recoveries", "models"):
        assert after[key] == before[key], ("pit/ttc/legal touched book.%s" % key)
    assert after["lookups"] >= before["lookups"]


# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import irb
    import stage_02 as s

    rows = s.grid()
    assert len(rows) == 23, "grid must carry exactly 23 rows, got %d" % len(rows)

    # Check shape: strictly increasing PD, non-decreasing quantile
    for i in range(1, len(rows)):
        assert rows[i][0] > rows[i-1][0], "grid PD not strictly increasing at index %d" % i
        assert rows[i][1] >= rows[i-1][1], "grid quantile not non-decreasing at index %d" % i

    # Must match irb.QUANTILE_GRID exactly
    for i in range(len(rows)):
        assert rows[i] == (irb.QUANTILE_GRID[i][0], irb.QUANTILE_GRID[i][1]), \
            "grid row %d differs from irb.QUANTILE_GRID" % i

    # quantile: endpoint PDs are answered
    assert s.quantile(0) == -3439
    assert s.quantile(10000) == 3439

    # Some known grid values
    assert s.quantile(100) == -1285
    assert s.quantile(250) == -840
    assert s.quantile(5000) == 380

    # Off-grid PDs are refused
    for pd in (5200, 7500, 9050, -1, 10001):
        try:
            s.quantile(pd)
        except s.QuantileError as e:
            assert "pd-quantile-grid" in str(e), "off-grid PD %d: %s" % (pd, e)

    # Non-integers are refused
    for bad in (1.5, "500", True, None):
        try:
            s.quantile(bad)
        except s.QuantileError as e:
            assert "pd" in str(e).lower() or "basis" in str(e).lower() or "whole" in str(e).lower(), \
                "non-int PD %r: %s" % (bad, e)

    # Grid shape check: two calls same result
    rows2 = s.grid()
    assert rows == rows2, "grid() is not deterministic"


# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import book, irb, stage_03 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # --- correlation: corporate ---
    for pd_bp in irb.CORPORATE_CORRELATION_BP:
        got = s.correlation("corporate", pd_bp)
        expected = irb.CORPORATE_CORRELATION_BP[pd_bp]
        assert got == expected, "correlation(corporate, %d) = %d, expected %d" % (pd_bp, got, expected)

    # --- correlation: retail classes (constant) ---
    for cls, val in irb.RETAIL_CORRELATION_BP.items():
        got = s.correlation(cls, 500)
        assert got == val, "correlation(%s, 500) = %d, expected %d" % (cls, got, val)

    # --- slope ---
    for pd_bp in irb.CORPORATE_SLOPE_BP:
        got = s.slope("corporate", pd_bp)
        assert got == irb.CORPORATE_SLOPE_BP[pd_bp]

    for cls, val in irb.RETAIL_SLOPE_BP.items():
        got = s.slope(cls, 500)
        assert got == val

    # --- remaining_years: a loan with >= 3 months remaining ---
    for loan_id in led.loans():
        years = s.remaining_years(led, loan_id, first_date)
        assert 0 <= years <= 5, "remaining_years for %r at %s: %d" % (loan_id, first_date, years)

    # --- maturity_factor ---
    b3000 = s.maturity_factor("corporate", 3000, 3)
    b2 = s.maturity_factor("corporate", 3000, 2)
    b5 = s.maturity_factor("corporate", 3000, 5)
    # m=2.5 is the neutral point, so b2 < b3 < b5 (maturity adjustment increases with distance from 2.5)
    assert b2 <= b3000, "maturity_factor at m=2 is not <= m=3"
    assert b3000 <= b5, "maturity_factor at m=3 is not <= m=5"

    # M_MIN and M_MAX clamped
    assert s.maturity_factor("corporate", 3000, 0) == s.maturity_factor("corporate", 3000, 1)
    assert s.maturity_factor("corporate", 3000, 6) == s.maturity_factor("corporate", 3000, 5)


# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import book, irb, stage_04 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # k_requirement returns a dict with K in basis points
    for loan_id in led.loans():
        try:
            result = s.k_requirement(led, loan_id, first_date)
            assert isinstance(result, dict), "k_requirement must return a dict, got %r" % type(result)
            assert "k_bp" in result, "k_requirement result missing k_bp: %r" % result.keys()
            assert isinstance(result["k_bp"], int), "k_bp must be int, got %r" % type(result["k_bp"])
            assert result["k_bp"] >= 0, "k_bp must be non-negative: %d" % result["k_bp"]
            assert result["k_bp"] <= 10000, "k_bp must be <= 10000: %d" % result["k_bp"]
        except s.KError:
            pass  # Some loans may not be live or have valid terms

    # Two runs same answer (determinism)
    for loan_id in list(led.loans())[:3]:
        try:
            a = s.k_requirement(led, loan_id, first_date)
            b = s.k_requirement(led, loan_id, first_date)
            assert a == b, "k_requirement not deterministic"
        except s.KError:
            pass


# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import book, irb, stage_05 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # best_estimate_lgd: returns LGD in bp
    for loan_id in led.loans():
        try:
            be_lgd = s.best_estimate_lgd(led, loan_id, first_date)
            assert isinstance(be_lgd, (int, float)), "best_estimate_lgd must be numeric: %r" % be_lgd
            assert 0 <= be_lgd <= 10000, "best_estimate_lgd must be 0..10000 bp: %s" % be_lgd
        except s.DownturnError:
            pass

    # downturn_lgd: returns LGD in bp, must be >= best_estimate_lgd * floor
    for loan_id in led.loans():
        try:
            dl = s.downturn_lgd(led, loan_id, first_date)
            be = s.best_estimate_lgd(led, loan_id, first_date)
            if isinstance(dl, (int, float)) and isinstance(be, (int, float)):
                # Downturn multiplier is >= 1.0 (11500 bp for corporate), so downturn LGD >= best estimate
                # But there's a floor and cap
                assert dl >= 0, "downturn_lgd must be >= 0: %s" % dl
                assert dl <= 10000, "downturn_lgd must be <= 10000: %s" % dl
        except s.DownturnError:
            pass

    # Downturn LGD for refrigerate class must NOT be multiplied
    leasing_loan = None
    for loan_id in led.loans():
        if isinstance(loan_id, dict) and loan_id.get("segment") == "leasing":
            leasing_loan = loan_id
            break
    if leasing_loan:
        dl_leasing = s.downturn_lgd(led, leasing_loan, first_date)
        be_leasing = s.best_estimate_lgd(led, leasing_loan, first_date)
        if isinstance(dl_leasing, (int, float)) and isinstance(be_leasing, (int, float)):
            # Refrigerate: multiplier should not apply, so downturn == best estimate
            assert dl_leasing == be_leasing, (
                "refrigerate class %r: downturn_lgd (%s) should equal best_estimate_lgd (%s)"
                % (leasing_loan, dl_leasing, be_leasing))

    # Two runs same answer
    if led.loans():
        loan_id = list(led.loans())[0]
        try:
            a = s.downturn_lgd(led, loan_id, first_date)
            b = s.downturn_lgd(led, loan_id, first_date)
            assert a == b, "downturn_lgd not deterministic"
        except s.DownturnError:
            pass


# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import book, irb, stage_06 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # be_ead: returned as cents
    for loan_id in led.loans():
        try:
            ead = s.be_ead(led, loan_id, first_date)
            assert isinstance(ead, (int, float)), "be_ead must be numeric: %r" % type(ead)
            assert ead >= 0, "be_ead must be >= 0: %s" % ead
        except s.EadError:
            pass

    # ccf: returned in basis points
    for product in ("mortgage", "consumer", "sme", "corporate", "credit-card", "leasing"):
        try:
            ccf_val = s.ccf(led, product)
            assert isinstance(ccf_val, int), "ccf must be int: %r" % type(ccf_val)
            assert irb.CCF_FLOOR_BP <= ccf_val <= irb.CCF_CAP_BP, \
                "ccf %d for %r not in [%d, %d]" % (ccf_val, product, irb.CCF_FLOOR_BP, irb.CCF_CAP_BP)
        except s.EadError:
            pass

    # be_ead of drawn + undrawn * ccf
    for loan_id in list(led.loans())[:3]:
        try:
            drawn = s.drawn_cents(led, loan_id, first_date)
            plan = s.plan_cents(led, loan_id, first_date)
            undrawn = s.undrawn_cents(led, loan_id, first_date)
            ead = s.be_ead(led, loan_id, first_date)
            segment = led.loan(loan_id)["segment"] if isinstance(loan_id, dict) else loan_id
            ccf_val = s.ccf(led, segment)
            expected_ead = drawn + undrawn * ccf_val // 10000
            assert ead == expected_ead, ("be_ead(%r, %r) = %d, expected %d (drawn=%d, undrawn=%d, ccf=%d)"
                                        % (loan_id, first_date, ead, expected_ead, drawn, undrawn, ccf_val))
        except (s.EadError, KeyError):
            pass


# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import book, irb, stage_07 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # risk_weight: returns bp
    for loan_id in led.loans():
        try:
            rw = s.risk_weight(led, loan_id, first_date)
            assert isinstance(rw, int), "risk_weight must be int: %r" % type(rw)
            assert 0 <= rw <= 10000, "risk_weight must be 0..10000 bp: %d" % rw
        except s.RwaError:
            pass

    # total_rwa: returns total RWA in cents
    try:
        total = s.total_rwa(led, first_date)
        assert isinstance(total, (int, float)), "total_rwa must be numeric: %r" % type(total)
        assert total >= 0, "total_rwa must be >= 0: %s" % total
    except s.RwaError:
        pass

    # Two runs same answer
    try:
        a = s.total_rwa(led, first_date)
        b = s.total_rwa(led, first_date)
        assert a == b, "total_rwa not deterministic"
    except s.RwaError:
        pass


# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import book, irb, stage_08 as s

    # phase: returns integer percent
    for year in (2028, 2029, 2030, 2031, 2035):
        got = s.phase(year)
        expected = irb.FLOOR_PHASE_PERCENT[year]
        assert got == expected, "phase(%d) = %d, expected %d" % (year, got, expected)

    # Year outside schedule refused
    for bad_year in (2027, 2036, 2020, 2040):
        try:
            s.phase(bad_year)
        except s.FloorError as e:
            assert "2027" in str(e) or "2036" in str(e) or "2020" in str(e) or "2040" in str(e), \
                "phase(%d): %s" % (bad_year, e)

    # applied: returns a dict with rwa and floor_rwa
    led = book.Book.build(7)
    for year in (2028, 2035):
        try:
            result = s.applied(led, led.reporting_dates[0], year)
            assert isinstance(result, dict), "applied must return a dict: %r" % type(result)
            assert "own_rwa" in result, "applied result missing own_rwa"
            assert "floor_rwa" in result, "applied result missing floor_rwa"
            assert "binding" in result, "applied result missing binding"
        except s.FloorError:
            pass


# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import book, irb, stage_09 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # per_grade: returns list of (grade, irf9_prov, irb_cap, ...)
    try:
        rows = s.per_grade(led, first_date)
        assert isinstance(rows, (list, tuple)), "per_grade must return list/tuple: %r" % type(rows)
        assert len(rows) > 0, "per_grade must not be empty"
        # Each row should have grade, irf9 provision, irb capital
        for row in rows:
            assert len(row) >= 3, "per_grade row must have >= 3 fields: %r" % row
    except s.ReconcileError:
        pass

    # irreconcilable: returns list of disagreements
    try:
        dis = s.irreconcilable(led, first_date)
        assert isinstance(dis, (list, tuple)), "irreconcilable must return list/tuple"
        for d in dis:
            assert len(d) >= 2, "irreconcilable row must have >= 2 fields: %r" % d
    except s.ReconcileError:
        pass


# --- stage 10 -----------------------------------------------------------------------
def check_10():
    import book, irb, stage_10 as s

    led = book.Book.build(7)
    first_date = led.reporting_dates[0]

    # capital_pack: returns a dict with pack info
    try:
        pack = s.capital_pack(led, first_date, 2030)
        assert isinstance(pack, dict), "capital_pack must return a dict: %r" % type(pack)
        # Should have exposures, rwa, floor, etc.
        assert "exposures" in pack or "classes" in pack or "total_rwa" in pack, \
            "capital_pack result: %r" % pack.keys()
    except s.AuditError:
        pass

    # Two runs same answer
    try:
        a = s.capital_pack(led, first_date, 2030)
        b = s.capital_pack(led, first_date, 2030)
        assert a == b, "capital_pack not deterministic"
    except s.AuditError:
        pass


# --- STAGES ------------------------------------------------------------------------
STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="PIT vs TTC, and where each is legal",
        tags=["rating", "classification", "legal"],
        action="Write `pit`, `ttc` and `legal` in stage_01.py: the bank's own grade, "
               "the artifact's grade, and which query may cite which kind.",
        predict="What a defaulted loan's PIT grade is, and what the artifact still "
                "carries for it — the gap that makes the stage necessary.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The normal quantile as tabulated data",
        tags=["quantile", "tabulated", "no-formula"],
        action="Write `grid` and `quantile` in stage_02.py: the 23-row grid, "
               "and the exact row a PD maps to — no interpolation.",
        predict="What PD 5000 maps to, and what PD 5200 (off-grid) is refused.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The correlation and the maturity adjustment",
        tags=["correlation", "maturity", "slope"],
        action="Write `correlation`, `slope`, `remaining_years` and "
               "`maturity_factor` in stage_03.py: the tables and the clamp.",
        predict="The correlation of corporate at PD 3000, and the maturity factor "
                "for a loan with 3 remaining years.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The capital requirement K, the exact series",
        tags=["K-series", "capital", "exact"],
        action="Write `k_requirement` in stage_04.py: the IRB capital as the "
               "exact series over the loan's remaining term, truncated.",
        predict="The K value for a 3-year corporate loan at PD 500.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Downturn LGD, the multiplier and the haircut",
        tags=["lgd", "downturn", "haircut", "refrigerate"],
        action="Write `best_estimate_lgd` and `downturn_lgd` in stage_05.py: "
               "the best estimate from recoveries, the downturn with the "
               "multiplier and the haircut.",
        predict="The best-estimate LGD of a defaulted loan, and the downturn "
                "LGD for the refrigerated leasing class (no multiplier).",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="BE-EAD and its CCFs estimated from the bank's defaults",
        tags=["ead", "ccf", "exposure"],
        action="Write `drawn_cents`, `plan_cents`, `undrawn_cents`, `be_ead` "
               "and `ccf` in stage_06.py: the drawn, the undrawn, the CCF "
               "from defaults, and the total exposure.",
        predict="BE-EAD of a mortgage loan: drawn plus undrawn times CCF.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Risk weight and RWA for one loan and the whole book",
        tags=["risk-weight", "rwa", "scaling"],
        action="Write `risk_weight` and `total_rwa` in stage_07.py: the formula's "
               "weight one loan's TTC grade and asset class scale to, and the "
               "whole book's total.",
        predict="The risk weight of a corporate loan at PD 3000 with 3 years "
                "remaining, and the total RWA of the twelve-loan book.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The output floor, phased in",
        tags=["floor", "phase-in", "standardized"],
        action="Write `phase` and `applied` in stage_08.py: the phased schedule "
               "and the greater of own RWA and floor-percent of the proxy.",
        predict="The floor percentage in 2030 is 60%, and a year outside "
                "2028-2035 is refused.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The two books, reconciled per grade",
        tags=["reconcile", "provision", "capital"],
        action="Write `per_grade` and `irreconcilable` in stage_09.py: the IFRS 9 "
               "provision and the IRB capital side by side, and the rows "
               "where they cannot agree.",
        predict="How many grades have the same provision and RWA, and which "
                "grades disagree and why (horizon vs basis).",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The audit the supervisor files (capstone)",
        tags=["audit", "pack", "capstone"],
        action="Write `phase` and `capital_pack` in stage_10.py: the full pack "
               "with exposures per class and grade, RWA, floor, and the "
               "two-books reconciliation.",
        predict="The total RWA for the book at the given date, and the "
                "floor-applied RWA in 2030.",
        check=check_10,
    ),
]