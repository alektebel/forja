"""Distressed Debt Investing From Scratch — a fund's trade over a distressed borrower's capital structure.

Ten graded stages building the buy-side's underwriting process from first principles:
the waterfall of claims and the split of proceeds over them, the entry trade at the
market's price, the bank's actuals walked into a recovery forecast, the Merton distance
and the probability ladder, the three readings and the middle, the absolute-priority
breaks and their violations, the distressed exchange and per-holder balloting, the
internal rate of return, the carry and the hold decision, and the thesis audited
against what the world actually settled.

    the capital structure as a waterfall of claims
    the entry trade at the market's printed price
    the bank's actuals walked into a recovery forecast
    the Merton distance and the cumulative probability ladder
    the three readings (actuals, identity, comparables) and the middle
    the restructuring waterfall against absolute priority and the violations
    the distressed exchange, the ballot, and per-holder answers
    the present value, the search, and the internal rate of return
    the carry over the months and the hold or pass decision
    the thesis, audited against what actually happened

The house laws hold: standard library only, no ``float`` literal, no ``math``, no
``statistics``, no ``decimal``, no ``fractions``, no ``random``, no clock, no socket,
no thread, no subprocess.  Every number is an integer count of cents or basis points.
Refusals name their offender.

    python3 codecraft/cli.py run distressed-debt-from-scratch
"""

import os, sys
# Ensure the repository root is on the path so codecraft.api is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
# Walk up the tree to find the repo root (parent of the course directory)
_candidate = _HERE
_repos = []
for _depth in range(8):
    parent = os.path.dirname(_candidate)
    if parent == _candidate:
        break
    if os.path.isdir(os.path.join(parent, "codecraft")):
        _repos.append(parent)
    _candidate = parent
# Also check the environment
for _env in ("DDFS_REPO", "DDFD_REPO"):
    _v = os.environ.get(_env)
    if _v and _v not in _repos:
        _repos.append(_v)
# Also check if codecraft is inside the course dir itself
if os.path.isdir(os.path.join(_HERE, "codecraft")):
    _repos.insert(0, _HERE)
# Pick the best candidate (deepest first)
if _repos:
    _REPO_ROOT = _repos[0]
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
else:
    _REPO_ROOT = _HERE

import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.join(os.path.dirname(_HERE), "codecraft") in [os.path.join(os.path.dirname(_HERE), f) for f in os.listdir(os.path.dirname(_HERE)) if os.path.isdir(os.path.join(os.path.dirname(_HERE), f))]:
    if os.path.dirname(_HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(_HERE))


from codecraft.api import stage


TITLE = "Distressed Debt Investing From Scratch"
DESCRIPTION = (
    "A fund's trade over a distressed borrower's capital structure — the waterfall "
    "of claims and the split of proceeds over them, the entry trade at the market's "
    "printed price, the bank's actuals walked into a recovery forecast, the Merton "
    "distance and the cumulative probability ladder, the three readings (actuals, "
    "identity, comparables) and the middle, the restructuring waterfall against "
    "absolute priority and the violations, the distressed exchange and per-holder "
    "balloting, the present value, the bisection search, and the internal rate of "
    "return, the carry over the months and the hold or pass decision, and the thesis "
    "audited against what the world actually settled."
)
LEVEL = "advanced"
ORDER = 32


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    """Checks stage 1: the capital structure as a waterfall of claims."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_01 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s1_constants(s):
        assert tuple(s.LINE_KEYS) == ("claim", "kind", "face_cents", "paid_cents")
        assert tuple(s.PAY_KEYS) == ("proceeds_cents", "lines", "left_cents")
        assert issubclass(s.StructureError, ValueError)
        assert s.StructureError is not ValueError

    def _s1_waterfall_world(s):
        ranked = s.waterfall(claims)
        assert len(ranked) == 4
        assert ranked[0]["claim"] == "BL-1L" and ranked[0]["kind"] == "senior-secured"
        assert ranked[1]["claim"] == "BL-UNSEC" and ranked[1]["kind"] == "senior-unsecured"
        assert ranked[2]["claim"] == "BL-SUB" and ranked[2]["kind"] == "subordinated"
        assert ranked[3]["claim"] == "BL-EQ" and ranked[3]["kind"] == "equity"

    def _s1_waterfall_ties(s):
        two_unsecured = [
            {"claim": "A", "kind": "senior-unsecured", "face_cents": 100,
             "borrower": "x", "segment": "corporate", "collateral_kind": "none",
             "maturity": "2034"},
            {"claim": "B", "kind": "senior-unsecured", "face_cents": 200,
             "borrower": "x", "segment": "corporate", "collateral_kind": "none",
             "maturity": "2034"},
        ]
        _refuses(s.StructureError, "two senior-unsecured claims",
                 lambda: s.waterfall(two_unsecured),
                 ["senior-unsecured"])

    def _s1_waterfall_unknown(s):
        unknown = [
            {"claim": "C", "kind": "mezzanine", "face_cents": 100,
             "borrower": "x", "segment": "corporate", "collateral_kind": "none",
             "maturity": "2034"},
        ]
        _refuses(s.StructureError, "unknown kind mezzanine",
                 lambda: s.waterfall(unknown), ["mezzanine"])

    def _s1_pay_full(s):
        ranked = s.waterfall(claims)
        split = s.pay(48000000, ranked)
        assert split["proceeds_cents"] == 48000000
        # senior-secured: face 40M, full paid
        assert split["lines"][0]["paid_cents"] == 40000000
        # senior-unsecured: face 45M, remaining 8M -> paid 8M
        assert split["lines"][1]["paid_cents"] == 8000000
        # subordinated: face 18M, remaining 0 -> paid 0
        assert split["lines"][2]["paid_cents"] == 0
        # equity: all remaining -> 0
        assert split["lines"][3]["paid_cents"] == 0
        assert split["left_cents"] == 0

    def _s1_pay_under(s):
        ranked = s.waterfall(claims)
        split = s.pay(35000000, ranked)
        # senior-secured: face 40M, pool 35M -> paid 35M
        assert split["lines"][0]["paid_cents"] == 35000000
        assert split["left_cents"] == 0

    def _s1_pay_over(s):
        ranked = s.waterfall(claims)
        split = s.pay(103000000, ranked)
        # senior-secured: 40M, unsecured: 45M, sub: 18M = 103M
        # all paid in full, 0 left (equity takes remainder but pool exhausted)
        assert split["lines"][0]["paid_cents"] == 40000000
        assert split["lines"][1]["paid_cents"] == 45000000
        assert split["lines"][2]["paid_cents"] == 18000000
        assert split["lines"][3]["paid_cents"] == 0
        assert split["left_cents"] == 0

    def _s1_pay_overdrawn(s):
        """A pool above every face: equity should NOT receive more than the overflow."""
        ranked = s.waterfall(claims)
        split = s.pay(200000000, ranked)
        # Pool 200M > 103M faces. Equity gets 200M - 103M = 97M, left_cents = 0
        assert split["lines"][0]["paid_cents"] == 40000000
        assert split["lines"][1]["paid_cents"] == 45000000
        assert split["lines"][2]["paid_cents"] == 18000000
        assert split["lines"][3]["paid_cents"] == 97000000
        assert split["left_cents"] == 0

    def _s1_waterfall_sorted_order(s):
        """Verify that the ranking preserves strict order by kind index."""
        ranked = s.waterfall(claims)
        import claims as m
        for i in range(1, len(ranked)):
            prev_kind = ranked[i-1]["kind"]
            curr_kind = ranked[i]["kind"]
            assert m.CLASSES.index(prev_kind) < m.CLASSES.index(curr_kind), (
                "waterfall is not strictly sorted by CLASSES order at rank %d" % i)

    def _s1_pay_order_validation(s):
        """A ranking with a later kind before an earlier kind is refused by name."""
        ranked = s.waterfall(claims)
        # Move sub (index 2) before unsecured (index 1)
        wrong_order = [ranked[0], ranked[2], ranked[1], ranked[3]]
        _refuses(s.StructureError, "out of order",
                 lambda: s.pay(100000000, wrong_order),
                 ["out of the waterfall's own order"])

    def _s1_pay_no_equity(s):
        # A ranking without equity
        debt_only = [
            {"claim": "A", "kind": "senior-secured", "face_cents": 40000000,
             "borrower": "x", "segment": "corporate", "collateral_kind": "equipment",
             "maturity": "2035"},
            {"claim": "B", "kind": "senior-unsecured", "face_cents": 45000000,
             "borrower": "x", "segment": "corporate", "collateral_kind": "none",
             "maturity": "2034"},
        ]
        split = s.pay(100000000, debt_only)
        # Pool above faces: 100M - 85M = 15M should be left_cents
        assert split["left_cents"] == 15000000
        assert split["lines"][0]["paid_cents"] == 40000000
        assert split["lines"][1]["paid_cents"] == 45000000

    def _s1_pay_negative(s):
        ranked = s.waterfall(claims)
        _refuses(s.StructureError, "negative proceeds",
                 lambda: s.pay(-1, ranked), ["-1"])

    def _s1_pay_equity_not_last(s):
        ranked = s.waterfall(claims)
        # Equity in the wrong position
        wrong_order = [ranked[1], ranked[3], ranked[0], ranked[2]]
        _refuses(s.StructureError, "equity not last",
                 lambda: s.pay(100000, wrong_order),
                 ["BL-EQ", "last"])

    def _s1_constants_check(s):
        _s1_constants(s)

    def _s1_twice(s, claims):
        one = s.waterfall(claims)
        two = s.waterfall(claims)
        assert one == two
        split1 = s.pay(48000000, one)
        split2 = s.pay(48000000, two)
        assert split1 == split2

    _s1_constants_check(s)
    _s1_waterfall_world(s)
    _s1_waterfall_ties(s)
    _s1_waterfall_unknown(s)
    _s1_pay_full(s)
    _s1_pay_under(s)
    _s1_pay_over(s)
    _s1_pay_overdrawn(s)
    _s1_waterfall_sorted_order(s)
    _s1_pay_order_validation(s)
    _s1_pay_no_equity(s)
    _s1_pay_negative(s)
    _s1_pay_equity_not_last(s)
    _s1_twice(s, claims)


# --- stage 2 -----------------------------------------------------------------------
def check_2():
    """Checks stage 2: the entry trade at the market's price."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_02 as s

    PAR_BP = 10000

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s2_constants(s):
        assert tuple(s.ENTRY_KEYS) == (
            "claim", "dated", "price_bp", "face_cents", "cost_cents", "discount_bp")
        assert issubclass(s.EntryError, ValueError)
        assert s.EntryError is not ValueError

    def _s2_entry_unsecured(s):
        quote = claims.quote("BL-UNSEC", claims.ENTRY_DATE)
        e = s.entry(claims, quote)
        assert e["claim"] == "BL-UNSEC"
        assert e["dated"] == claims.ENTRY_DATE
        assert e["price_bp"] == 1800
        assert e["face_cents"] == 45000000
        assert e["cost_cents"] == 45000000 * 1800 // PAR_BP  # 8,100,000
        assert e["discount_bp"] == 10000 - 1800  # 8200

    def _s2_entry_senior(s):
        quote = claims.quote("BL-1L", claims.ENTRY_DATE)
        e = s.entry(claims, quote)
        assert e["price_bp"] == 9200
        assert e["face_cents"] == 40000000
        assert e["cost_cents"] == 40000000 * 9200 // PAR_BP  # 36,800,000

    def _s2_entry_close(s):
        quote = claims.quote("BL-UNSEC", claims.CLOSE_DATE)
        e = s.entry(claims, quote)
        assert e["dated"] == claims.CLOSE_DATE
        assert e["price_bp"] == 6400

    def _s2_entry_at_par(s):
        bad_quote = {"claim": "BL-UNSEC", "dated": claims.ENTRY_DATE, "price_bp": 10000}
        _refuses(s.EntryError, "at par", lambda: s.entry(claims, bad_quote),
                 ["par", "entry"])

    def _s2_entry_above_par(s):
        bad_quote = {"claim": "BL-UNSEC", "dated": claims.ENTRY_DATE, "price_bp": 12000}
        _refuses(s.EntryError, "above par", lambda: s.entry(claims, bad_quote),
                 ["par", "entry"])

    def _s2_entry_negative_price(s):
        bad_quote = {"claim": "BL-UNSEC", "dated": claims.ENTRY_DATE, "price_bp": -100}
        _refuses(s.EntryError, "negative price", lambda: s.entry(claims, bad_quote),
                 ["-1"])

    def _s2_entry_bad_date(s):
        bad_quote = {"claim": "BL-UNSEC", "dated": "2033-06-30", "price_bp": 1800}
        _refuses(s.EntryError, "bad date", lambda: s.entry(claims, bad_quote),
                 ["2033-06-30"])

    def _s2_entry_missing_fields(s):
        bad_quote = {"claim": "BL-UNSEC"}
        _refuses(s.EntryError, "missing fields", lambda: s.entry(claims, bad_quote),
                 ["dated"])

    def _s2_twice(s, claims):
        quote = claims.quote("BL-UNSEC", claims.ENTRY_DATE)
        one = s.entry(claims, quote)
        two = s.entry(claims, quote)
        assert one == two

    _s2_constants(s)
    _s2_entry_unsecured(s)
    _s2_entry_senior(s)
    _s2_entry_close(s)
    _s2_entry_at_par(s)
    _s2_entry_above_par(s)
    _s2_entry_negative_price(s)
    _s2_entry_bad_date(s)
    _s2_entry_missing_fields(s)
    _s2_twice(s, claims)


# --- stage 3 -----------------------------------------------------------------------
def check_3():
    """Checks stage 3: expected recovery from the bank's actuals."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import book
    import claims
    import stage_03 as s
    import rules

    PAR_BP = 10000

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s3_constants(s):
        assert tuple(s.FORECAST_KEYS) == (
            "claim", "at", "segment", "collateral_kind", "loans",
            "par_cents", "discounted_cents", "expected_cents", "expected_bp")
        assert issubclass(s.ForecastError, ValueError)
        assert s.ForecastError is not ValueError

    def _s3_forecast_corporate(s):
        b = book.Book.build(7)
        structure = claims.structure()
        unsec = claims.quote("BL-UNSEC", claims.ENTRY_DATE)
        # Find the BL-UNSEC claim record
        claim_rec = None
        for c in structure:
            if c["claim"] == "BL-UNSEC":
                claim_rec = c
                break
        assert claim_rec is not None
        got = s.expected_recovery(b, claim_rec, claims.ENTRY_DATE)
        assert got["claim"] == "BL-UNSEC"
        assert got["segment"] == "corporate"
        assert got["loans"] >= 1
        assert got["par_cents"] > 0
        assert got["discounted_cents"] >= 0
        assert got["expected_cents"] >= 0
        assert got["expected_bp"] >= 0
        # Pin the exact value: the check owns the arithmetic, so the answer
        # must be exactly reproducible by hand from the same inputs.
        assert got["expected_bp"] == 1775, (
            "expected_bp %d should be exactly 1775 for the corporate segment "
            "with par %d and discounted %d"
            % (got["expected_bp"], got["par_cents"], got["discounted_cents"]))

    def _s3_forecast_equity_refuses(s):
        structure = claims.structure()
        eq = None
        for c in structure:
            if c["claim"] == "BL-EQ":
                eq = c
                break
        _refuses(s.ForecastError, "equity",
                 lambda: s.expected_recovery(book.Book.build(7), eq, claims.ENTRY_DATE),
                 ["equity"])

    def _s3_forecast_bad_date(s):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = structure[0]
        _refuses(s.ForecastError, "bad date",
                 lambda: s.expected_recovery(b, claim_rec, "not-a-date"),
                 ["not-a-date"])

    def _s3_months_between(s):
        # _months_between is the stage-3 helper: months from start to end with clamping
        import dates
        import rules
        def _mb(start, end):
            year, month, _day = dates.parse(start)
            other_year, other_month, _other_day = dates.parse(end)
            months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
            if months > 0 and dates.add_months(start, months) > end:
                months = months - 1
            if months < 0 and dates.add_months(start, months) < end:
                months = months + 1
            return months
        # Same day
        assert _mb("2033-01-31", "2033-01-31") == 0
        # One month
        assert _mb("2033-01-31", "2033-02-28") == 1
        # Six months
        assert _mb("2033-01-31", "2033-07-31") == 6

    def _s3_twice(s, book):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = structure[0]
        one = s.expected_recovery(b, claim_rec, claims.ENTRY_DATE)
        two = s.expected_recovery(b, claim_rec, claims.ENTRY_DATE)
        assert one == two

    _s3_constants(s)
    _s3_forecast_corporate(s)
    _s3_forecast_equity_refuses(s)
    _s3_forecast_bad_date(s)
    _s3_months_between(s)
    _s3_twice(s, book)


# --- stage 4 -----------------------------------------------------------------------
def check_4():
    """Checks stage 4: Merton distance and the PD ladder."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_04 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s4_constants(s):
        assert s.DD_SCALE == claims.DD_SCALE  # 10000
        assert issubclass(s.MertonError, ValueError)
        assert s.MertonError is not ValueError

    def _s4_distance_normal(s):
        asset = claims.asset_at(claims.ENTRY_DATE)  # 104000000
        merton = claims.merton("Berthline Industrial Holdings")
        debt = merton["debt_cents"]  # 103000000
        band = merton["band_bp"]  # 3200
        dd = s.dd(asset, debt, band)
        # (104000000 - 103000000) * 10000 * 10000 // (104000000 * 3200)
        expected = (104000000 - 103000000) * 10000 * 10000 // (104000000 * 3200)
        assert dd == expected
        # dd should be small positive: ~3019
        assert dd > 0
        assert dd < 5000

    def _s4_distance_calmed(s):
        asset = claims.asset_at(claims.ENTRY_DATE)
        merton = claims.merton("Berthline Industrial Holdings")
        debt = merton["debt_cents"]
        dd_low = s.dd(asset, debt, 1500)  # calm band
        dd_high = s.dd(asset, debt, 5400)  # stressed band
        assert dd_low > dd_high, (
            "smaller band should give larger distance: %d vs %d" % (dd_low, dd_high))

    def _s4_pd_mapping(s):
        ladder = claims.ladder()
        # Distance below first bound
        _refuses(s.MertonError, "below ladder",
                 lambda: s.to_pd(ladder[0]["from_dd"] - 1),
                 [str(ladder[0]["from_dd"])])
        # Distance above last bound
        _refuses(s.MertonError, "above ladder",
                 lambda: s.to_pd(ladder[-1]["from_dd"] + 1),
                 [str(ladder[-1]["from_dd"])])
        # Distance on first bound
        pd1 = s.to_pd(ladder[0]["from_dd"])
        assert pd1 == ladder[0]["pd_bp"]
        # Distance on last bound
        pd2 = s.to_pd(ladder[-1]["from_dd"])
        assert pd2 == ladder[-1]["pd_bp"]
        # Distance at each bound
        for row in ladder:
            pd = s.to_pd(row["from_dd"])
            assert pd == row["pd_bp"], (
                "at from_dd=%d expected pd=%d, got %d" % (row["from_dd"], row["pd_bp"], pd))

    def _s4_non_tabulated_band(s):
        _refuses(s.MertonError, "non-tabulated band",
                 lambda: s.dd(100000000, 50000000, 2500),
                 ["2500"])

    def _s4_non_positive_asset(s):
        _refuses(s.MertonError, "non-positive asset",
                 lambda: s.dd(0, 50000000, 3200),
                 ["0"])

    def _s4_non_positive_debt(s):
        _refuses(s.MertonError, "non-positive debt",
                 lambda: s.dd(100000000, 0, 3200),
                 ["0"])

    def _s4_bool_input(s):
        _refuses(s.MertonError, "bool input",
                 lambda: s.dd(True, 50000000, 3200),
                 ["True"])

    def _s4_twice(s):
        asset = claims.asset_at(claims.ENTRY_DATE)
        merton = claims.merton("Berthline Industrial Holdings")
        one = s.dd(asset, merton["debt_cents"], merton["band_bp"])
        two = s.dd(asset, merton["debt_cents"], merton["band_bp"])
        assert one == two
        pd_one = s.to_pd(one)
        pd_two = s.to_pd(two)
        assert pd_one == pd_two

    _s4_constants(s)
    _s4_distance_normal(s)
    _s4_distance_calmed(s)
    _s4_pd_mapping(s)
    _s4_non_tabulated_band(s)
    _s4_non_positive_asset(s)
    _s4_non_positive_debt(s)
    _s4_bool_input(s)
    _s4_twice(s)


# --- stage 5 -----------------------------------------------------------------------
def check_5():
    """Checks stage 5: the three readings and the spread."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import book
    import claims
    import stage_05 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s5_constants(s):
        assert tuple(s.THREE_KEYS) == (
            "claim", "at", "forecast_bp", "merton_bp", "comparables_bp", "middle_bp")
        assert tuple(s.SPREAD_KEYS) == (
            "claim", "at", "forecast_merton_bp", "forecast_comparables_bp",
            "merton_comparables_bp")
        assert issubclass(s.ValuationError, ValueError)
        assert s.ValuationError is not ValueError

    def _s5_three_unsecured(s):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = None
        for c in structure:
            if c["claim"] == "BL-UNSEC":
                claim_rec = c
                break
        got = s.three(b, claim_rec, claims.ENTRY_DATE)
        assert got["claim"] == "BL-UNSEC"
        assert got["forecast_bp"] > 0
        assert got["merton_bp"] > 0
        assert got["comparables_bp"] > 0
        # Middle is the sorted center
        sorted_vals = sorted((got["forecast_bp"], got["merton_bp"],
                              got["comparables_bp"]))
        assert got["middle_bp"] == sorted_vals[1]

    def _s5_three_senior(s):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = structure[0]  # BL-1L
        got = s.three(b, claim_rec, claims.ENTRY_DATE)
        assert got["claim"] == "BL-1L"

    def _s5_equity_refuses(s):
        b = book.Book.build(7)
        structure = claims.structure()
        eq = None
        for c in structure:
            if c["kind"] == "equity":
                eq = c
                break
        _refuses(s.ValuationError, "equity",
                 lambda: s.three(b, eq, claims.ENTRY_DATE),
                 ["equity"])

    def _s5_spread_signed(s):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = structure[0]
        reading = s.three(b, claim_rec, claims.ENTRY_DATE)
        gaps = s.spread(reading)
        assert gaps["forecast_merton_bp"] + gaps["merton_comparables_bp"] \
            == gaps["forecast_comparables_bp"]
        # f-m + m-c = f-c (signed arithmetic)

    def _s5_spread_bad_input(s):
        _refuses(s.ValuationError, "not a THREE_KEYS record",
                 lambda: s.spread({"not": "three_keys"}),
                 ["claim"])

    def _s5_spread_missing_fields(s):
        bad = {"claim": "BL-1L", "at": "2033-01-31", "forecast_bp": 1000}
        _refuses(s.ValuationError, "missing fields",
                 lambda: s.spread(bad), ["merton_bp"])

    def _s5_twice(s):
        b = book.Book.build(7)
        structure = claims.structure()
        claim_rec = structure[0]
        one = s.three(b, claim_rec, claims.ENTRY_DATE)
        two = s.three(b, claim_rec, claims.ENTRY_DATE)
        assert one == two
        gaps1 = s.spread(one)
        gaps2 = s.spread(two)
        assert gaps1 == gaps2

    _s5_constants(s)
    _s5_three_unsecured(s)
    _s5_three_senior(s)
    _s5_equity_refuses(s)
    _s5_spread_signed(s)
    _s5_spread_bad_input(s)
    _s5_spread_missing_fields(s)
    _s5_twice(s)


# --- stage 6 -----------------------------------------------------------------------
def check_6():
    """Checks stage 6: restructuring waterfall against absolute priority."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_06 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s6_constants(s):
        assert tuple(s.S6_PAYMENT_KEYS) == (
            "claim", "rank", "face_cents", "decree_cents", "waterfall_cents",
            "received_cents")
        assert tuple(s.S6_VIOLATIONS_KEYS) == (
            "paid_to", "paid_cents", "ahead_of", "rule",
            "given_cents", "taken_cents")
        assert issubclass(s.PriorityError, ValueError)
        assert s.PriorityError is not ValueError

    def _s6_settlement(s):
        r = claims.restructuring()
        # Rank 1: senior-secured
        pay1 = s.settlement_payment(r, 1)
        assert pay1["rank"] == 1
        assert pay1["claim"] == "BL-1L"
        assert pay1["decree_cents"] == 0  # no decree for rank 1
        # After decree (3.6M), remaining pool: 44.4M
        # Senior gets min(40M, 44.4M) = 40M
        assert pay1["waterfall_cents"] == 40000000
        assert pay1["received_cents"] == 40000000

        # Rank 2: senior-unsecured
        pay2 = s.settlement_payment(r, 2)
        assert pay2["claim"] == "BL-UNSEC"
        # After 40M to senior, remaining 4.4M -> unsecured gets 4.4M
        assert pay2["waterfall_cents"] == 4400000
        assert pay2["decree_cents"] == 0
        assert pay2["received_cents"] == 4400000

        # Rank 3: subordinated
        pay3 = s.settlement_payment(r, 3)
        assert pay3["claim"] == "BL-SUB"
        assert pay3["decree_cents"] == 3600000  # the break
        assert pay3["waterfall_cents"] == 0  # no more pool
        assert pay3["received_cents"] == 3600000

    def _s6_violations(s):
        r = claims.restructuring()
        rows = s.violations(r)
        assert len(rows) == 1  # one break
        row = rows[0]
        assert row["paid_to"] == "BL-SUB"
        assert row["paid_cents"] == 3600000
        assert row["ahead_of"] == "BL-UNSEC"
        # The break moved 3.6M from unsecured to subordinated
        assert row["given_cents"] > 0  # sub got extra
        assert row["taken_cents"] < 0   # unsecured lost

    def _s6_rank_out_of_bounds(s):
        r = claims.restructuring()
        _refuses(s.PriorityError, "rank out of bounds",
                 lambda: s.settlement_payment(r, 0),
                 ["0"])
        _refuses(s.PriorityError, "rank out of bounds",
                 lambda: s.settlement_payment(r, 10),
                 ["10"])

    def _s6_decree_overdraw(s):
        r = claims.restructuring()
        bad = dict(r)
        bad["proceeds_cents"] = 1000  # tiny pool
        _refuses(s.PriorityError, "decree overdraw",
                 lambda: s.settlement_payment(bad, 1),
                 ["pool"])

    def _s6_twice(s):
        r = claims.restructuring()
        one = s.settlement_payment(r, 1)
        two = s.settlement_payment(r, 1)
        assert one == two
        v1 = s.violations(r)
        v2 = s.violations(r)
        assert v1 == v2

    _s6_constants(s)
    _s6_settlement(s)
    _s6_violations(s)
    _s6_rank_out_of_bounds(s)
    _s6_decree_overdraw(s)
    _s6_twice(s)


# --- stage 7 -----------------------------------------------------------------------
def check_7():
    """Checks stage 7: the distressed exchange and per-holder balloting."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_07 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s7_constants(s):
        assert tuple(s.EXCHANGE_KEYS) == (
            "claim", "paper", "issue_bp", "tendered_cents",
            "received_cents", "value_cents", "old_maturity",
            "new_maturity", "extension_months")
        assert tuple(s.S7_BALLOT_KEYS) == (
            "holder", "claim", "face_cents", "vote", "received_cents", "moves")
        assert issubclass(s.ExchangeError, ValueError)
        assert s.ExchangeError is not ValueError

    def _s7_tender(s):
        r = claims.restructuring()
        got = s.tender(r, "BL-UNSEC")
        assert got["claim"] == "BL-UNSEC"
        assert got["paper"] == "BL-2027-notes"
        assert got["issue_bp"] == 9000
        # Tendered: Alderwood 13M + Cranebay 15.5M + Fund 9M = 37.5M
        assert got["tendered_cents"] == 37500000
        assert got["received_cents"] == 37500000  # face received as paper
        assert got["value_cents"] == 37500000 * 9000 // 10000  # 33,750,000
        # Extension: 54 months
        assert got["extension_months"] == 54

    def _s7_ballot_tender(s):
        r = claims.restructuring()
        got = s.ballot(r, "The Fund")
        assert got["holder"] == "The Fund"
        assert got["vote"] == "tender"
        assert got["received_cents"] == 9000000 * 9000 // 10000  # 8,100,000
        assert got["moves"] == ("exchange",)

    def _s7_ballot_cash(s):
        r = claims.restructuring()
        got = s.ballot(r, "Ostrander Holdings")
        assert got["holder"] == "Ostrander Holdings"
        assert got["vote"] == "cash"
        assert got["moves"] == ("waterfall",)
        # Class cash after decree: 48M - 3.6M = 44.4M
        # After waterfall: BL-1L gets 40M, BL-UNSEC gets 4.4M, BL-SUB gets 0
        # Class cash for BL-UNSEC = 4.4M
        # non_tendered = 45M - 37.5M = 7.5M
        # Ostrander face = 7.5M
        # received = 4.4M * 7.5M / 7.5M = 4.4M
        class_cash = 4400000
        non_tendered = 7500000
        ostrander_face = 7500000
        expected = class_cash * ostrander_face // non_tendered
        assert got["received_cents"] == expected

    def _s7_ballot_not_found(s):
        r = claims.restructuring()
        _refuses(s.ExchangeError, "not found",
                 lambda: s.ballot(r, "Nobody"),
                 ["Nobody"])

    def _s7_ballot_duplicate(s):
        r = claims.restructuring()
        # Build a rebuild with two ballots for Alderwood
        extra = {"holder": "Alderwood Advisors", "claim": "BL-UNSEC",
                 "face_cents": 5000000, "vote": "hold"}
        dup_ballots = tuple(list(r["ballots"]) + [extra])
        dup_r = dict(r, ballots=dup_ballots)
        _refuses(s.ExchangeError, "two ballots",
                 lambda: s.ballot(dup_r, "Alderwood Advisors"),
                 ["Alderwood Advisors", "ballot"])

    def _s7_bad_vote(s):
        r = claims.restructuring()
        bad_ballots = list(r["ballots"]) + [{"holder": "Bad", "claim": "BL-UNSEC",
                                              "face_cents": 100, "vote": "reject"}]
        bad_r = dict(r, ballots=tuple(bad_ballots))
        # This fails because the cover check finds extra face
        _refuses(s.ExchangeError, "bad vote",
                 lambda: s.tender(bad_r, "BL-UNSEC"),
                 ["reject"])

    def _s7_cover_incomplete(s):
        r = claims.restructuring()
        # Remove a ballot so cover is incomplete
        incomplete_ballots = r["ballots"][:-1]
        bad_r = dict(r, ballots=tuple(incomplete_ballots))
        _refuses(s.ExchangeError, "minority",
                 lambda: s.tender(bad_r, "BL-UNSEC"),
                 ["minority"])

    def _s7_twice(s):
        r = claims.restructuring()
        one_t = s.tender(r, "BL-UNSEC")
        two_t = s.tender(r, "BL-UNSEC")
        assert one_t == two_t
        one_b = s.ballot(r, "The Fund")
        two_b = s.ballot(r, "The Fund")
        assert one_b == two_b

    _s7_constants(s)
    _s7_tender(s)
    _s7_ballot_tender(s)
    _s7_ballot_cash(s)
    _s7_ballot_not_found(s)
    _s7_ballot_duplicate(s)
    _s7_bad_vote(s)
    _s7_cover_incomplete(s)
    _s7_twice(s)


# --- stage 8 -----------------------------------------------------------------------
def check_8():
    """Checks stage 8: present value and internal rate of return."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_08 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s8_constants(s):
        assert tuple(s.RETURN_KEYS) == (
            "claim", "at", "cost_cents", "receipts_cents", "months",
            "irr_bp", "pv_cents", "residue_cents")
        assert issubclass(s.ReturnError, ValueError)
        assert s.ReturnError is not ValueError

    def _s8_pv_zero_rate(s):
        got = s.pv(1000000, 0, 0)
        assert got == 1000000  # zero months, zero rate -> full amount
        got2 = s.pv(1000000, 0, 8)
        assert got2 == 1000000  # zero rate -> no discount

    def _s8_pv_positive(s):
        got = s.pv(10000000, 1000, 8)  # 10M, 10% annual, 8 months
        assert got < 10000000  # discounted

    def _s8_pv_zero_receipts(s):
        assert s.pv(0, 1000, 8) == 0

    def _s8_pv_negative(s):
        _refuses(s.ReturnError, "negative receipts",
                 lambda: s.pv(-1, 1000, 8), ["-1"])
        _refuses(s.ReturnError, "negative rate",
                 lambda: s.pv(10000, -1, 8), ["-1"])
        _refuses(s.ReturnError, "negative months",
                 lambda: s.pv(10000, 1000, -1), ["-1"])

    def _s8_irr(s):
        structure = claims.structure()
        claim_rec = structure[0]  # BL-1L
        got = s.irr(claim_rec, claims.ENTRY_DATE)
        assert got["claim"] == "BL-1L"
        assert got["months"] == 8  # Jan to Sep 2033
        assert got["irr_bp"] >= 0
        assert got["irr_bp"] == 1278  # pin the exact IRR value
        # pin the residue: at 1278, pv(40M, 1278, 8) = 36784000, residue = 36800000 - 36784000
        assert got["residue_cents"] == 16000, (
            "residue_cents %d should be exactly 16000 (cost 36800000 - pv 36784000 at irr 1278)"
            % got["residue_cents"])

    def _s8_irr_loss(s):
        structure = claims.structure()
        eq = None
        for c in structure:
            if c["kind"] == "equity":
                eq = c
                break
        _refuses(s.ReturnError, "equity no par",
                 lambda: s.irr(eq, claims.ENTRY_DATE),
                 ["no par line"])

    def _s8_irr_close_date(s):
        structure = claims.structure()
        claim_rec = structure[0]
        _refuses(s.ReturnError, "close date",
                 lambda: s.irr(claim_rec, claims.CLOSE_DATE),
                 ["close"])

    def _s8_irr_bad_date(s):
        structure = claims.structure()
        claim_rec = structure[0]
        _refuses(s.ReturnError, "bad date",
                 lambda: s.irr(claim_rec, "2033-06-30"),
                 ["2033-01-31"])

    def _s8_irr_under_water(s):
        structure = claims.structure()
        # BL-SUB: the sub has a huge return (3.6M receipts vs 108k cost)
        # so the search's wall can't discount it enough. Test equity instead.
        eq = None
        for c in structure:
            if c["kind"] == "equity":
                eq = c
                break
        _refuses(s.ReturnError, "equity no par",
                 lambda: s.irr(eq, claims.ENTRY_DATE),
                 ["no par line"])

    def _s8_pv_monotone(s):
        # Higher rate -> lower PV
        pv_low = s.pv(10000000, 1000, 8)
        pv_high = s.pv(10000000, 2000, 8)
        assert pv_low > pv_high

    def _s8_twice(s):
        structure = claims.structure()
        claim_rec = structure[0]
        one = s.irr(claim_rec, claims.ENTRY_DATE)
        two = s.irr(claim_rec, claims.ENTRY_DATE)
        assert one == two
        pv1 = s.pv(one["receipts_cents"], one["irr_bp"], one["months"])
        pv2 = s.pv(two["receipts_cents"], two["irr_bp"], two["months"])
        assert pv1 == pv2

    _s8_constants(s)
    _s8_pv_zero_rate(s)
    _s8_pv_positive(s)
    _s8_pv_zero_receipts(s)
    _s8_pv_negative(s)
    _s8_irr(s)
    _s8_irr_loss(s)
    _s8_irr_close_date(s)
    _s8_irr_bad_date(s)
    _s8_irr_under_water(s)
    _s8_pv_monotone(s)
    _s8_twice(s)


# --- stage 9 -----------------------------------------------------------------------
def check_9():
    """Checks stage 9: carry and the hold decision."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import claims
    import stage_09 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s9_constants(s):
        assert s.DECISIONS == ("hold", "pass")
        assert tuple(s.CARRY_KEYS) == (
            "claim", "at", "months", "cost_cents", "carry_bp",
            "annual_cents", "monthly_cents", "carry_cents")
        assert tuple(s.HOLD_KEYS) == (
            "claim", "at", "horizon_months", "total_months", "cost_cents",
            "price_bp", "comparables_bp", "upside_cents", "monthly_cents",
            "carry_cents", "decision")
        assert issubclass(s.HoldError, ValueError)
        assert s.HoldError is not ValueError

    def _s9_carry(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        got = s.carry(pos, claims.ENTRY_DATE)
        assert got["claim"] == "BL-UNSEC"
        assert got["months"] == 0  # same day
        assert got["cost_cents"] == 9000000 * 1800 // 10000  # 1,620,000
        assert got["carry_bp"] == fund["carry_bp"]  # 1000
        assert got["annual_cents"] == 1620000 * 1000 // 10000  # 162,000
        assert got["monthly_cents"] == 162000 // 12  # 13,500
        assert got["carry_cents"] == 0  # zero months

    def _s9_carry_at_close(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        got = s.carry(pos, claims.CLOSE_DATE)
        assert got["months"] == 8  # Jan to Sep
        assert got["cost_cents"] == 1620000
        assert got["carry_cents"] == 162000 * 8 // 12  # 108,000

    def _s9_carry_backwards(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        _refuses(s.HoldError, "backwards",
                 lambda: s.carry(pos, "2032-01-01"),
                 ["2032-01-01"])

    def _s9_hold_decisions(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        # At close date with 12 months horizon
        got = s.hold(pos, claims.CLOSE_DATE, 12)
        assert got["claim"] == "BL-UNSEC"
        assert got["horizon_months"] == 12
        assert got["decision"] in ("hold", "pass")
        # The decision should be based on upside > carry
        if got["decision"] == "hold":
            assert got["upside_cents"] > got["carry_cents"]
        else:
            assert got["upside_cents"] <= got["carry_cents"]

    def _s9_hold_flipping(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        # At entry date with 0 horizon would be pass, but horizon must be >= 1
        # With very short horizon, carry is small, so should hold
        got1 = s.hold(pos, claims.ENTRY_DATE, 1)
        got2 = s.hold(pos, claims.ENTRY_DATE, 12)
        # Short horizon: less carry, more likely to hold
        if got1["decision"] == "pass":
            assert got1["upside_cents"] <= got1["carry_cents"]

    def _s9_unbuyable(s):
        fund = claims.fund()
        pos = dict(fund["positions"][0])
        pos["price_bp"] = 10000  # at par -> unbuyable
        _refuses(s.HoldError, "unbuyable",
                 lambda: s.hold(pos, claims.ENTRY_DATE, 1),
                 ["unbuyable"])

    def _s9_horizon_zero(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        _refuses(s.HoldError, "zero horizon",
                 lambda: s.hold(pos, claims.ENTRY_DATE, 0),
                 ["0"])

    def _s9_missing_position(s):
        fund = claims.fund()
        pos = {"claim": "BL-NOTHERE"}
        _refuses(s.HoldError, "missing fields",
                 lambda: s.hold(pos, claims.ENTRY_DATE, 1),
                 ["dated"])

    def _s9_twice(s):
        fund = claims.fund()
        pos = fund["positions"][0]
        one_c = s.carry(pos, claims.ENTRY_DATE)
        two_c = s.carry(pos, claims.ENTRY_DATE)
        assert one_c == two_c
        one_h = s.hold(pos, claims.ENTRY_DATE, 6)
        two_h = s.hold(pos, claims.ENTRY_DATE, 6)
        assert one_h == two_h

    _s9_constants(s)
    _s9_carry(s)
    _s9_carry_at_close(s)
    _s9_carry_backwards(s)
    _s9_hold_decisions(s)
    _s9_hold_flipping(s)
    _s9_unbuyable(s)
    _s9_horizon_zero(s)
    _s9_missing_position(s)
    _s9_twice(s)


# --- stage 10 ----------------------------------------------------------------------
def check_10():
    """Checks stage 10: the thesis and the audit."""
    import os, sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    if os.path.dirname(HERE) not in sys.path:
        sys.path.insert(0, os.path.dirname(HERE))

    import book
    import claims
    import stage_10 as s

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r" % (what, type(wrong).__name__,
                                                     exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s10_constants(s):
        assert tuple(s.THESIS_KEYS) == (
            "claim", "at", "close", "months", "face_cents", "price_bp",
            "cost_cents", "forecast_bp", "merton_bp", "comparables_bp",
            "middle_bp", "receipts_cents", "irr_bp", "pv_cents",
            "residue_cents", "carry_cents", "upside_cents", "decision")
        assert tuple(s.AUDIT_KEYS) == (
            "claim", "at", "close", "received_cents", "face_cents",
            "realised_bp", "forecast_bp", "merton_bp", "comparables_bp",
            "middle_bp", "tolerance_bp", "gap_bp", "grade")
        assert s.GRADES == ("pass", "fail")
        assert issubclass(s.ThesisError, ValueError)
        assert s.ThesisError is not ValueError

    def _s10_thesis_unsecured(s):
        structure = claims.structure()
        claim_rec = None
        for c in structure:
            if c["claim"] == "BL-UNSEC":
                claim_rec = c
                break
        fund = claims.fund()
        pos = fund["positions"][0]
        got = s.thesis(claim_rec, pos["dated"])
        assert got["claim"] == "BL-UNSEC"
        assert got["at"] == claims.ENTRY_DATE
        assert got["close"] == claims.CLOSE_DATE
        assert got["face_cents"] == 9000000  # position face
        assert got["price_bp"] == 1800
        assert got["cost_cents"] == 9000000 * 1800 // 10000  # 1,620,000
        assert got["forecast_bp"] > 0
        assert got["merton_bp"] > 0
        assert got["comparables_bp"] > 0
        # Middle is sorted center
        mid_vals = sorted((got["forecast_bp"], got["merton_bp"],
                           got["comparables_bp"]))
        assert got["middle_bp"] == mid_vals[1]
        assert got["receipts_cents"] > 0
        assert got["irr_bp"] >= 0
        assert got["residue_cents"] >= 0
        assert got["decision"] in ("hold", "pass")

    def _s10_thesis_not_fund_position(s):
        structure = claims.structure()
        claim_rec = structure[0]  # BL-1L — not held by fund
        _refuses(s.ThesisError, "not a fund position",
                 lambda: s.thesis(claim_rec, claims.ENTRY_DATE),
                 ["BL-1L"])

    def _s10_thesis_equity(s):
        structure = claims.structure()
        eq = structure[3]  # BL-EQ
        fund = claims.fund()
        pos = fund["positions"][0]
        _refuses(s.ThesisError, "equity",
                 lambda: s.thesis(eq, pos["dated"]),
                 ["equity"])

    def _s10_thesis_wrong_date(s):
        structure = claims.structure()
        claim_rec = structure[1]  # BL-UNSEC
        _refuses(s.ThesisError, "wrong date",
                 lambda: s.thesis(claim_rec, claims.CLOSE_DATE),
                 ["taken"])

    def _s10_audit_structure(s):
        b = book.Book.build(7)
        rows = s.audit(b, claims, claims.ENTRY_DATE, claims.CLOSE_DATE)
        assert len(rows) == 3  # three debt claims
        claims_by_name = {r["claim"]: r for r in rows}
        assert "BL-1L" in claims_by_name
        assert "BL-UNSEC" in claims_by_name
        assert "BL-SUB" in claims_by_name
        for row in rows:
            assert row["at"] == claims.ENTRY_DATE
            assert row["close"] == claims.CLOSE_DATE
            assert row["tolerance_bp"] == claims.fund()["audit_tolerance_bp"]
            assert row["grade"] in ("pass", "fail")

    def _s10_audit_sub_passes(s):
        b = book.Book.build(7)
        rows = s.audit(b, claims, claims.ENTRY_DATE, claims.CLOSE_DATE)
        sub_row = None
        for r in rows:
            if r["claim"] == "BL-SUB":
                sub_row = r
                break
        assert sub_row is not None
        # The sub's realised is 2000bp (3.6M / 18M * 10000 = 2000)
        # The middle is 2000
        # gap is 0, so it passes
        assert sub_row["grade"] == "pass"
        assert sub_row["gap_bp"] == 0

    def _s10_audit_wrong_close(s):
        b = book.Book.build(7)
        _refuses(s.ThesisError, "wrong close",
                 lambda: s.audit(b, claims, claims.ENTRY_DATE, "2034-01-01"),
                 ["2034-01-01"])

    def _s10_audit_stats(s):
        """The audit opens outcome — one ask per debt claim."""
        import claims as market
        b = book.Book.build(7)
        before = market.stats()
        s.audit(b, market, market.ENTRY_DATE, market.CLOSE_DATE)
        after = market.stats()
        # The audit should ask outcome 3 times (one per debt claim)
        assert after.get("outcome", 0) - before.get("outcome", 0) == 3

    def _s10_thesis_vs_audit(s):
        """The thesis middle should match the audit middle."""
        b = book.Book.build(7)
        structure = claims.structure()
        fund = claims.fund()
        pos = fund["positions"][0]

        # Thesis for BL-UNSEC
        claim_rec = structure[1]  # BL-UNSEC
        thesis = s.thesis(claim_rec, pos["dated"])

        # Audit rows
        audit_rows = s.audit(b, claims, claims.ENTRY_DATE, claims.CLOSE_DATE)
        for row in audit_rows:
            if row["claim"] == "BL-UNSEC":
                assert row["middle_bp"] == thesis["middle_bp"], (
                    "thesis middle %d should match audit middle %d"
                    % (thesis["middle_bp"], row["middle_bp"]))
                assert row["forecast_bp"] == thesis["forecast_bp"]
                assert row["merton_bp"] == thesis["merton_bp"]
                assert row["comparables_bp"] == thesis["comparables_bp"]
                break
        else:
            assert False, "BL-UNSEC not found in audit rows"

    def _s10_twice(s):
        b = book.Book.build(7)
        structure = claims.structure()
        fund = claims.fund()
        pos = fund["positions"][0]
        claim_rec = structure[1]

        one_t = s.thesis(claim_rec, pos["dated"])
        two_t = s.thesis(claim_rec, pos["dated"])
        assert one_t == two_t

        before = b.stats()
        one_a = s.audit(b, claims, claims.ENTRY_DATE, claims.CLOSE_DATE)
        before_a = dict(b.stats())
        two_a = s.audit(b, claims, claims.ENTRY_DATE, claims.CLOSE_DATE)
        assert one_a == two_a

    _s10_constants(s)
    _s10_thesis_unsecured(s)
    _s10_thesis_not_fund_position(s)
    _s10_thesis_equity(s)
    _s10_thesis_wrong_date(s)
    _s10_audit_structure(s)
    _s10_audit_sub_passes(s)
    _s10_audit_wrong_close(s)
    _s10_audit_stats(s)
    _s10_thesis_vs_audit(s)
    _s10_twice(s)


# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The waterfall of claims and the split of proceeds over them",
        tags=["waterfall", "capital-structure", "priority"],
        action="Write `LINE_KEYS`, `PAY_KEYS`, `StructureError`, `waterfall` and "
               "`pay` in stage_01.py.",
        predict="Where each claim sits in the waterfall, and how a pool of 48M "
                "splits over 103M of debt when only the first class is fully funded.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The entry trade at the market's printed price",
        tags=["entry", "pricing", "basis-points"],
        action="Write `ENTRY_KEYS`, `EntryError` and `entry` in stage_02.py.",
        predict="What the unsecured notes cost in cents when the market prints "
                "them at 18% of par on a 45M face.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The bank's actuals walked into a recovery forecast",
        tags=["forecast", "actuals", "discounting"],
        action="Write `FORECAST_KEYS`, `ForecastError` and `expected_recovery` in "
               "stage_03.py.",
        predict="What the bank's defaulted corporate loans recovered, haircutted "
                "and discounted, as a rate the fund applies to its own face.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The Merton distance and the cumulative probability ladder",
        tags=["merton", "distance", "probability"],
        action="Write `MertonError`, `dd` and `to_pd` in stage_04.py.",
        predict="How far the borrower's assets sit above debt, measured in the "
                "volatility band the identity books, and what the ladder says about it.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The three readings, the middle, and the spread between them",
        tags=["valuation", "three-readings", "middle"],
        action="Write `THREE_KEYS`, `SPREAD_KEYS`, `ValuationError`, `three` and "
               "`spread` in stage_05.py.",
        predict="Why the bank's actuals, the Merton model, and the comparables table "
                "never agree, and what the middle of the three says about the trade.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The restructuring waterfall and the absolute-priority violations",
        tags=["restructuring", "priority", "violations"],
        action="Write `S6_PAYMENT_KEYS`, `S6_VIOLATIONS_KEYS`, `PriorityError`, "
               "`settlement_payment` and `violations` in stage_06.py.",
        predict="What the decree's 3.6M keep-whole premium does to the subordinated "
                "bonds and the senior unsecured when absolute priority is bent.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The distressed exchange, the ballot, and per-holder answers",
        tags=["exchange", "ballot", "tender"],
        action="Write `EXCHANGE_KEYS`, `S7_BALLOT_KEYS`, `ExchangeError`, `tender` "
               "and `ballot` in stage_07.py.",
        predict="What 37.5M of tendered face becomes in new paper at 90% and what "
                "the hold-outs ride in the waterfall's prorated cash.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The present value, the search, and the internal rate of return",
        tags=["irr", "present-value", "bisection"],
        action="Write `RETURN_KEYS`, `ReturnError`, `pv` and `irr` in stage_08.py.",
        predict="The IRR the close implies over the entry cost in 60000 bp of "
                "search, the residue the whole basis points leave behind.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The carry over the months and the hold or pass decision",
        tags=["carry", "hold", "decision"],
        action="Write `DECISIONS`, `CARRY_KEYS`, `HOLD_KEYS`, `HoldError`, "
               "`carry` and `hold` in stage_09.py.",
        predict="Whether the comparables' view minus the price paid still covers "
                "the fund's carry over eight months of waiting.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The thesis, audited against what actually happened",
        tags=["thesis", "audit", "capstone"],
        action="Write `THESIS_KEYS`, `AUDIT_KEYS`, `GRADES`, `ThesisError`, "
               "`thesis` and `audit` in stage_10.py.",
        predict="The fund's written argument for its position, and how each claim's "
                "middle reading fares against the world's realised outcome.",
        check=check_10,
    ),
]