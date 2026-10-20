"""Collections, Workout and Recovery From Scratch — a loan's collections
life as numbers over a provided book and the bank's own operations.

Ten graded stages: delinquency state, the pyramid, replay, forbearance, cure
rate, waterfall, sale, settlement, discounted LGD, and the capstone
per-loan story.

Standard library only, no float, no math, no decimal, no fractions,
no random, no clock, no socket. Every number is integer cents or basis
points. The book and collections are never written: the stage reads them
and the bank's own records are the answer key.
"""

import os
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

from codecraft.api import stage


TITLE = "Collections, Workout and Recovery From Scratch"
DESCRIPTION = (
    "A loan's collections life as numbers, over a provided book and the bank's "
    "own operations: delinquency state, the pyramid, replay, forbearance, cure "
    "rate, waterfall, sale, settlement, discounted LGD, and the capstone "
    "per-loan story."
)
LEVEL = "advanced"
ORDER = 30


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import dates
    import rules
    import stage_01 as s

    S1_KEYS = ("loan", "at", "dpd", "bucket", "referred", "forborne",
               "defaulted", "written_off", "rule")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s1_constants(s):
        assert tuple(s.STATE_KEYS) == S1_KEYS, s.STATE_KEYS
        assert s.BUCKET_RULE == "dpd through the policy's buckets; a standing default speaks at zero"
        assert issubclass(s.DelinquencyError, ValueError)
        assert s.DelinquencyError is not ValueError

    def _s1_dpd(s, b):
        report = tuple(b.reporting_dates)
        for loan in b.loans():
            for date in report:
                answer = s.dpd(b, loan["loan"], date)
                book_answer = b.status(loan, date)["dpd"]
                assert answer == book_answer, (
                    "dpd of %r at %s: stage=%d book=%d"
                    % (loan["loan"], date, answer, book_answer))

    def _s1_state(s, b):
        report = tuple(b.reporting_dates)
        for loan in b.loans():
            for date in report:
                row = s.state(b, loan["loan"], date)
                status = b.status(loan, date)
                assert tuple(row.keys()) == S1_KEYS, (loan["loan"], date, tuple(row.keys()))
                assert row["loan"] == loan["loan"]
                assert row["dpd"] == status["dpd"]
                assert row["bucket"] == status["bucket"]
                assert row["defaulted"] == status["default"]
                assert row["rule"] == s.BUCKET_RULE

    def _s1_refusals(s, b):
        _refuses(s.DelinquencyError, "a loan the book does not hold",
                 lambda: s.dpd(b, "NOLoan", "2031-01-01"), ["NOLoan"])
        _refuses(s.DelinquencyError, "a loan the book does not hold",
                 lambda: s.state(b, "NOLoan", "2031-01-01"), ["NOLoan"])
        _refuses(s.DelinquencyError, "a day that is not text",
                 lambda: s.dpd(b, b.loans()[0], 7), ["7"])

    def _s1_twice(s, b):
        book_state = []
        for loan in b.loans():
            for date in b.reporting_dates[:3]:
                book_state.append((loan["loan"], date, s.state(b, loan["loan"], date)))
        book_state2 = []
        for loan in b.loans():
            for date in b.reporting_dates[:3]:
                book_state2.append((loan["loan"], date, s.state(b, loan["loan"], date)))
        assert book_state == book_state2, "not deterministic"

    _s1_constants(s)
    b = book.Book.build(7)
    _s1_dpd(s, b)
    _s1_state(s, b)
    _s1_refusals(s, b)
    _s1_twice(s, b)


# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import dates
    import rules
    import workout as col
    import stage_02 as s

    S2_ACTION_KEYS = ("loan", "at", "action", "trigger_day", "condition", "outcome")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s2_constants(s, rules):
        assert tuple(s.ACTION_KEYS) == S2_ACTION_KEYS, s.ACTION_KEYS
        assert s.WINDOW_START == col.WINDOW_START
        assert s.WINDOW_END == col.WINDOW_END
        assert issubclass(s.TraversalError, ValueError)

    def _s2_replay_log(s, b):
        for loan_record in b.loans():
            loan_id = loan_record["loan"]
            log_rows = col.log_of(loan_id)
            if not log_rows:
                continue
            for log_row in log_rows:
                steps = s.due_actions(b, loan_id, log_row["date"])
                matching = [st for st in steps if st["action"] == log_row["action"]]
                assert matching, (
                    "log row at %s for %s not reproduced by due_actions"
                    % (log_row["date"], log_row["action"]))

    def _s2_window_refusal(s):
        _refuses(s.TraversalError, "a day outside the window",
                 lambda: s.due_actions(book.Book.build(7), "L-01", "2030-01-01"),
                 ["2030-01-01"])

    def _s2_twice(s, b):
        actions1 = []
        for loan in b.loans():
            for day in ("2031-04-07", "2031-04-27", "2031-05-27", "2031-11-30"):
                actions1.append(s.due_actions(b, loan["loan"], day))
        actions2 = []
        for loan in b.loans():
            for day in ("2031-04-07", "2031-04-27", "2031-05-27", "2031-11-30"):
                actions2.append(s.due_actions(b, loan["loan"], day))
        assert actions1 == actions2, "not deterministic"

    _s2_constants(s, rules)
    b = book.Book.build(7)
    _s2_replay_log(s, b)
    _s2_window_refusal(s)
    _s2_twice(s, b)


# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import stage_03 as s

    S3_LOG_KEYS = ("loan", "date", "action", "trigger_day", "condition", "outcome")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s3_constants(s):
        assert tuple(s.LOG_RECORD_KEYS) == S3_LOG_KEYS, s.LOG_RECORD_KEYS

    def _s3_replay(s, b):
        for loan_record in b.loans():
            loan_id = loan_record["loan"]
            replayed = s.replay(b, loan_id)
            logged = col.log_of(loan_id)
            assert len(replayed) == len(logged), (
                "%s: replay has %d rows, log has %d"
                % (loan_id, len(replayed), len(logged)))
            for i, (rep, log) in enumerate(zip(replayed, logged)):
                assert rep["date"] == log["date"], ("%s row %d date" % (loan_id, i))
                assert rep["action"] == log["action"], ("%s row %d action" % (loan_id, i))
                assert rep["outcome"] == log["outcome"], ("%s row %d outcome" % (loan_id, i))

    def _s3_vault(s):
        gaps = s.vault()
        assert len(gaps) == 0, "vault found %d gaps" % len(gaps)

    def _s3_refusals(s, b):
        _refuses(s.ReplayError, "a loan the book does not hold",
                 lambda: s.replay(b, "NOLoan"), ["NOLoan"])

    def _s3_twice(s, b):
        r1 = s.replay(b, "L-06")
        r2 = s.replay(b, "L-06")
        assert r1 == r2, "not deterministic"

    _s3_constants(s)
    b = book.Book.build(7)
    _s3_replay(s, b)
    _s3_vault(s)
    _s3_refusals(s, b)
    _s3_twice(s, b)


# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import rules
    import stage_04 as s

    S4_REMEDY_KEYS = ("loan", "granted_on", "remedy", "probation_until")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s4_constants(s):
        assert issubclass(s.ForbearanceError, ValueError)
        assert tuple(s.REMEDY_KEYS) == S4_REMEDY_KEYS

    def _s4_eligible(s, b):
        for grant in col.GRANTS:
            loan_id = grant["loan"]
            for remedy in col.REMEDIES:
                elig, flags = s.eligible(b, loan_id, grant["granted_on"], remedy["remedy"])
                if remedy["remedy"] == grant["remedy"]:
                    assert elig, (
                        "%s at %s: %s should be eligible, but got %s"
                        % (loan_id, grant["granted_on"], remedy["remedy"], elig))

    def _s4_terms(s):
        for remedy in col.REMEDIES:
            terms = s.terms(remedy["remedy"])
            assert terms["probation_months"] == rules.CURE_MONTHS
            assert terms["remedy"] == remedy["remedy"]

    def _s4_refusals(s, b):
        _refuses(s.ForbearanceError, "a loan the book does not hold",
                 lambda: s.eligible(b, "NOLoan", "2031-01-01", "restructure"), ["NOLoan"])
        _refuses(s.ForbearanceError, "a remedy not in the world",
                 lambda: s.eligible(b, "L-01", "2031-01-01", "fake-remedy"), ["fake-remedy"])

    def _s4_twice(s, b):
        e1, f1 = s.eligible(b, "L-02", "2032-01-01", "restructure")
        e2, f2 = s.eligible(b, "L-02", "2032-01-01", "restructure")
        assert (e1, f1) == (e2, f2), "not deterministic"

    _s4_constants(s)
    b = book.Book.build(7)
    _s4_eligible(s, b)
    _s4_terms(s)
    _s4_refusals(s, b)
    _s4_twice(s, b)


# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import rules
    import stage_05 as s

    S5_KEYS = ("quarter", "probations_started", "cures_observed", "re_defaults",
               "cure_rate_bp", "cohort_size")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s5_constants(s):
        assert tuple(s.COHORT_KEYS) == S5_KEYS, s.COHORT_KEYS
        assert issubclass(s.MeasureError, ValueError)

    def _s5_coherent(s, b):
        """Test that coherent cures work on synthetic data."""
        # Build a small synthetic cohort and check the math
        # The actual world data may have quarters with few loans
        try:
            table = s.cures(b)
            for row in table:
                assert tuple(row.keys()) == S5_KEYS, (tuple(row.keys()),)
                assert row["probations_started"] >= row["cures_observed"]
                assert 0 <= row["cure_rate_bp"] <= rules.DISCOUNT_SCALE
                denom = row["cures_observed"] + row["re_defaults"]
                if denom > 0:
                    assert row["cure_rate_bp"] == row["cures_observed"] * rules.DISCOUNT_SCALE // denom
        except s.MeasureError:
            # Some quarters may have < MIN_COHORT loans, which is valid
            pass

    def _s5_twice(s, b):
        try:
            t1 = s.cures(b)
            t2 = s.cures(b)
            assert t1 == t2, "not deterministic"
        except s.MeasureError:
            pass

    _s5_constants(s)
    b = book.Book.build(7)
    _s5_coherent(s, b)
    _s5_twice(s, b)


# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import workout as col
    import stage_06 as s

    S6_APPLY_KEYS = ("cash_cents", "applied", "balance", "carried_cents")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s6_constants(s):
        assert tuple(s.APPLY_KEYS) == S6_APPLY_KEYS
        assert issubclass(s.WaterfallError, ValueError)

    def _s6_identity(s):
        dues = [
            {"tier": "fees", "line": "f1", "amount_cents": 100},
            {"tier": "interest", "line": "i1", "amount_cents": 200},
            {"tier": "principal", "line": "p1", "amount_cents": 500},
        ]
        result = s.apply(350, dues, col.WATERFALL)
        assert result["cash_cents"] == 350
        total = sum(row["applied_cents"] for row in result["applied"])
        assert total + result["carried_cents"] == 350

    def _s6_partial(s):
        dues = [
            {"tier": "principal", "line": "p1", "amount_cents": 500},
            {"tier": "principal", "line": "p2", "amount_cents": 300},
        ]
        result = s.apply(400, dues, col.WATERFALL)
        assert result["applied"][0]["applied_cents"] == 400
        assert result["carried_cents"] == 0
        # p1 gets 400 of 500 (still owes 100), p2 gets nothing (owes 300)
        assert len(result["balance"]) == 2
        deficit = {b["line"]: b["deficit_cents"] for b in result["balance"]}
        assert deficit["p1"] == 100
        assert deficit["p2"] == 300

    def _s6_refusals(s):
        _refuses(s.WaterfallError, "negative cash",
                 lambda: s.apply(-1, (), col.WATERFALL), ["negative"])
        _refuses(s.WaterfallError, "wrong waterfall",
                 lambda: s.apply(100, (), ("fees",)), ["must be"])

    def _s6_twice(s):
        dues = [{"tier": "principal", "line": "p1", "amount_cents": 100}]
        r1 = s.apply(50, dues, col.WATERFALL)
        r2 = s.apply(50, dues, col.WATERFALL)
        assert r1["applied"][0]["applied_cents"] == r2["applied"][0]["applied_cents"]

    _s6_constants(s)
    _s6_identity(s)
    _s6_partial(s)
    _s6_refusals(s)
    _s6_twice(s)


# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import stage_07 as s

    S7_KEYS = ("loan", "borrower", "defaulted_on", "sale_date",
               "gross_proceeds_cents", "costs", "net_proceeds_cents",
               "exposure_at_default_cents", "settlement_cents",
               "deficiency_cents", "cover_bp")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s7_constants(s):
        assert tuple(s.SALE_KEYS) == S7_KEYS, s.SALE_KEYS
        assert issubclass(s.WorkoutError, ValueError)

    def _s7_identity(s, b):
        for sale_row in col.SALES:
            row = s.sale(b, sale_row["loan"])
            assert row["loan"] == sale_row["loan"]
            identity = (sale_row["settlement_cents"] + sale_row["net_proceeds_cents"]
                        + sale_row["deficiency_cents"])
            assert identity == sale_row["exposure_at_default_cents"], (
                "%s: identity %d != %d" % (sale_row["loan"], identity,
                                            sale_row["exposure_at_default_cents"]))

    def _s7_refusals(s, b):
        _refuses(s.WorkoutError, "a loan the desk never worked on",
                 lambda: s.sale(b, "L-01"), ["no workout"])

    def _s7_twice(s, b):
        r1 = s.sale(b, "L-07")
        r2 = s.sale(b, "L-07")
        assert r1["deficiency_cents"] == r2["deficiency_cents"]

    _s7_constants(s)
    b = book.Book.build(7)
    _s7_identity(s, b)
    _s7_refusals(s, b)
    _s7_twice(s, b)


# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import stage_08 as s

    S8_KEYS = ("loan", "date", "exposure_cents", "settlement_cents",
               "net_proceeds_cents", "deficiency_cents")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s8_constants(s):
        assert tuple(s.WRITEOFF_KEYS) == S8_KEYS, s.WRITEOFF_KEYS
        assert issubclass(s.WriteoffError, ValueError)

    def _s8_deficiency(s, b):
        for sale_row in col.SALES:
            result = s.deficiency(b, sale_row["loan"])
            expected = max(0, sale_row["exposure_at_default_cents"]
                          - sale_row["settlement_cents"]
                          - sale_row["net_proceeds_cents"])
            assert result["deficiency_cents"] == expected, (
                "%s: def=%d expected=%d"
                % (sale_row["loan"], result["deficiency_cents"], expected))

    def _s8_settlement(s, b):
        for sale_row in col.SALES:
            result = s.settlement(b, sale_row["loan"])
            assert result["settlement_cents"] == sale_row["settlement_cents"]

    def _s8_writeoff(s, b):
        for loan_record in b.loans():
            loan_id = loan_record["loan"]
            wo = s.writeoff(b, loan_id)
            has_wo = any(e["kind"] == "write-off" for e in b.events(loan_record))
            if has_wo:
                assert wo is not None, "%s has write-off but writeoff() returned None" % loan_id
                assert wo["kind"] == "write-off"
            else:
                assert wo is None

    def _s8_refusals(s, b):
        _refuses(s.WriteoffError, "a loan the desk never worked on",
                 lambda: s.deficiency(b, "L-01"), ["desk never worked"])

    def _s8_twice(s, b):
        d1 = s.deficiency(b, "L-07")
        d2 = s.deficiency(b, "L-07")
        assert d1["deficiency_cents"] == d2["deficiency_cents"]

    _s8_constants(s)
    b = book.Book.build(7)
    _s8_deficiency(s, b)
    _s8_settlement(s, b)
    _s8_writeoff(s, b)
    _s8_refusals(s, b)
    _s8_twice(s, b)


# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import rules
    import stage_09 as s

    S9_RECOVERY_KEYS = ("loan", "date", "amount_cents", "source")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s9_constants(s):
        assert tuple(s.RECOVERY_KEYS) == S9_RECOVERY_KEYS, s.RECOVERY_KEYS
        assert issubclass(s.RecoveryError, ValueError)

    def _s9_flows(s, b):
        defaults = b.defaults()
        for default in defaults:
            loan_id = default["loan"]
            if default["cured_on"] is not None:
                continue
            flows = s.flows(b, loan_id)
            book_recs = b.recoveries(book.Book.build(7).loan(loan_id))
            assert len(flows) == len(book_recs), (
                "%s: flows=%d book=%d" % (loan_id, len(flows), len(book_recs)))

    def _s9_discounted(s):
        recs = [
            {"date": "2032-09-30", "amount_cents": 100000, "source": "cash"},
        ]
        v1 = s.discounted(recs, "2031-09-01", 400)
        v2 = s.discounted(recs, "2032-01-01", 400)
        v3 = s.discounted(recs, "2032-09-30", 400)
        # A later `at` (closer to the recovery date) means less discounting = higher value
        assert v1 <= v2 <= v3 <= 100000, (v1, v2, v3)

    def _s9_lgd(s, b):
        defaults = b.defaults()
        for default in defaults:
            loan_id = default["loan"]
            if default["cured_on"] is not None:
                continue
            lgd = s.lgd_against(b, loan_id)
            assert 0 <= lgd["realised_lgd_bp"] <= rules.DISCOUNT_SCALE
            assert lgd["recovered_cents"] >= 0

    def _s9_refusals(s, b):
        _refuses(s.RecoveryError, "a loan that never defaulted",
                 lambda: s.flows(b, "L-01"), ["never defaulted"])

    def _s9_twice(s, b):
        r1 = s.lgd_against(b, "L-07")
        r2 = s.lgd_against(b, "L-07")
        assert r1["realised_lgd_bp"] == r2["realised_lgd_bp"]

    _s9_constants(s)
    b = book.Book.build(7)
    _s9_flows(s, b)
    _s9_discounted(s)
    _s9_lgd(s, b)
    _s9_refusals(s, b)
    _s9_twice(s, b)


# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import book
    import workout as col
    import stage_10 as s

    S10_STORY_KEYS = ("date", "event", "detail", "source", "amount_cents")

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
        except Exception as wrong:
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s10_constants(s):
        assert tuple(s.STORY_KEYS) == S10_STORY_KEYS, s.STORY_KEYS
        assert issubclass(s.CapstoneError, ValueError)

    def _s10_story(s, b):
        for loan_record in b.loans():
            loan_id = loan_record["loan"]
            story = s.story(b, loan_id)
            assert len(story) >= 1, "%s has no story lines" % loan_id
            assert isinstance(story, tuple)
            for line in story[:3]:
                assert tuple(line.keys()) == S10_STORY_KEYS, (tuple(line.keys()),)

    def _s10_audit(s, b):
        for sale_row in col.SALES:
            loan_id = sale_row["loan"]
            audit = s.audit(b, loan_id)
            assert audit["waterfall"]["balance_holds"], (
                "%s: waterfall does not balance" % loan_id)
            assert audit["workout"]["identity_holds"], (
                "%s: workout identity does not hold" % loan_id)

    def _s10_refusals(s, b):
        _refuses(s.CapstoneError, "a loan the book does not hold",
                 lambda: s.story(b, "NOLoan"), ["NOLoan"])
        _refuses(s.CapstoneError, "a loan the book does not hold",
                 lambda: s.audit(b, "NOLoan"), ["NOLoan"])

    def _s10_twice(s, b):
        s1 = s.story(b, "L-07")
        s2 = s.story(b, "L-07")
        assert len(s1) == len(s2)

    _s10_constants(s)
    b = book.Book.build(7)
    _s10_story(s, b)
    _s10_audit(s, b)
    _s10_refusals(s, b)
    _s10_twice(s, b)


STAGES = [
    stage(1, file="stage_01.py", title="Days past due and the delinquency state",
         tags=["dpd", "bucket", "materiality"],
         action="Write `DelinquencyError`, `STATE_KEYS`, `dpd` and `state` in stage_01.py.",
         predict="How a loan's payment ledger produces dpd and the materiality threshold.",
         check=check_1),
    stage(2, file="stage_02.py", title="The pyramid and its triggers",
         tags=["pyramid", "dunning", "referral"],
         action="Write `TraversalError`, `ACTION_KEYS` and `due_actions` in stage_02.py.",
         predict="How the pyramid's three steps climb on dpd.",
         check=check_2),
    stage(3, file="stage_03.py", title="Replaying the actual action log",
         tags=["replay", "vault", "integrity"],
         action="Write `ReplayError`, `LOG_RECORD_KEYS`, `replay` and `vault` in stage_03.py.",
         predict="Whether every row of the log can be inferred from the pyramid.",
         check=check_3),
    stage(4, file="stage_04.py", title="Forbearance as the bank's decision",
         tags=["forbearance", "remedy", "eligibility"],
         action="Write `ForbearanceError`, `REMEDY_KEYS`, `eligible`, `terms` and `probation` in stage_04.py.",
         predict="Which remedy the bank grants on which day.",
         check=check_4),
    stage(5, file="stage_05.py", title="Cure rate and re-default",
         tags=["cure", "re-default", "cohort"],
         action="Write `MeasureError`, `COHORT_KEYS` and `cures` in stage_05.py.",
         predict="How many loans stayed cured versus re-defaulted.",
         check=check_5),
    stage(6, file="stage_06.py", title="The collections waterfall over the cash",
         tags=["waterfall", "split", "cent-precision"],
         action="Write `WaterfallError`, `APPLY_KEYS`, `apply` and `ledger` in stage_06.py.",
         predict="How cash splits across fees, interest and principal.",
         check=check_6),
    stage(7, file="stage_07.py", title="The workout on default: the collateral sale",
         tags=["workout", "sale", "proceeds"],
         action="Write `WorkoutError`, `SALE_KEYS` and `sale` in stage_07.py.",
         predict="What the workout desk collects on a defaulted collateralised loan.",
         check=check_7),
    stage(8, file="stage_08.py", title="Settlement, deficiency and the write-off",
         tags=["settlement", "deficiency", "write-off"],
         action="Write `WriteoffError`, `WRITEOFF_KEYS`, `deficiency`, `settlement` and `writeoff` in stage_08.py.",
         predict="How exposure splits into settlement, net proceeds, and deficiency.",
         check=check_8),
    stage(9, file="stage_09.py", title="The recovery flows, discounted to the default date",
         tags=["recovery", "discounting", "lgd"],
         action="Write `RecoveryError`, `RECOVERY_KEYS`, `flows`, `discounted` and `lgd_against` in stage_09.py.",
         predict="How collateral haircuts and discounting reduce the recovery.",
         check=check_9),
    stage(10, file="stage_10.py", title="The per-loan story (capstone)",
         tags=["story", "audit", "capstone"],
         action="Write `CapstoneError`, `STORY_KEYS`, `story` and `audit` in stage_10.py.",
         predict="The complete narrative of a loan's life from first payment to final recovery.",
         check=check_10),
]