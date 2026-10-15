"""Eval Framework From Scratch — course manifest.

Ten graded stages that build the RUNNER of an eval framework: the machine that
runs other people's code and other people's judgements and then has to say
something true about them. The task set, the solvers, the judges and the clock
are provided (`lab.py`); the exercise is everything that decides whether the
numbers mean anything — a suite config that refuses a typo instead of running
differently from what its author believed, metrics resolved as plugins before the
first call, one record per case from the position the case was actually in,
budgets that stop a call instead of reporting one, an aggregation whose unit is
the case and not the line, a judge that is cached, budgeted and order-blind,
records whose bytes two runs share, a gate that refuses to pass what it cannot
evaluate, a baseline diff that only cries regression when the difference beats
the noise, and a resume that leaves behind the log of an uninterrupted run.

This is the framework half of phase C1's lesson: `evals-from-scratch` owns what
to measure (EM, token F1, nDCG, judge bias, kappa, significance); this course owns
the machine those metrics live in, which is where the quiet failures are — the
run that recorded a case that never happened, the mean over lines instead of
cases, the cached judge verdict that leaked across a suite, the corpus that
entered the aggregate as a zero, the resume that bought itself a new budget.

No network, no wall clock, no uuid, no global state: the clock is `lab.Ticker`,
every float that lands in a record is rounded to `METRIC_DP`, and two runs of the
same suite produce byte-identical logs.

    python3 codecraft/cli.py run eval-framework-from-scratch
"""

from codecraft.api import stage

TITLE = "Eval Framework From Scratch"
DESCRIPTION = ("The runner under an eval: parse and validate a suite config, "
               "resolve metric plugins before the first call, run one case per "
               "record with an error taxonomy that blames the right side, check "
               "the call and clock budgets BEFORE the call, aggregate by case "
               "with the weights the suite declared, ask a judge through a "
               "cached and budgeted session that survives a position bias, write "
               "records whose bytes two runs share, gate the run with exit codes "
               "that order an invalid run before a failed gate, diff a candidate "
               "against a baseline through the noise of both runs, and resume a "
               "killed run into the exact bytes of an uninterrupted one.")
LEVEL = "intermediate"
ORDER = 15

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import os
import shutil
import sys
import tempfile
import json
import types
import re


def check_1():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        from lab import ConfigError
        try:
            fn(*args, **kwargs)
        except ConfigError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    from lab import ConfigError
    import stage_01 as s

    # --- a minimal suite materialises every default ------------------------
    minimal = {"id": "toy", "cases": [{"id": "a", "prompt": "2+3?", "answer": "5"}]}
    suite = s.parse_suite(minimal)
    assert suite.id == "toy", "the suite id is not the spec's id: %r" % (suite.id,)
    assert isinstance(suite.cases, tuple) and len(suite.cases) == 1, \
        "cases must be a tuple of parsed cases, got %r" % (type(suite.cases).__name__,)
    case = suite.cases[0]
    assert (case.id, case.prompt, case.answer) == ("a", "2+3?", "5"), \
        "the case's own fields did not survive parsing: %r" % (case,)
    assert (case.weight, case.max_ticks, case.repeats, case.tags) == (1.0, 10, 1, ()), \
        ("a case's defaults are the contract's, not something else: %r"
         % ((case.weight, case.max_ticks, case.repeats, case.tags),))
    assert (suite.metrics, suite.max_ticks, suite.max_calls, suite.max_judge_calls,
            suite.notes) == ((), 1000, 1000, 500, ""), \
        "the suite's defaults are the contract's: %r" % (suite,)
    assert type(case).__name__ == "Case" and type(suite).__name__ == "Suite", \
        "parse_suite must return the declared Case/Suite types, got %r/%r" \
        % (type(case).__name__, type(suite).__name__)
    for obj, field in ((case, "id"), (suite, "id")):
        try:
            setattr(obj, field, "nope")
            raise AssertionError("a %s is frozen: assigning to .%s must raise"
                                 % (type(obj).__name__, field))
        except ConfigError:
            raise
        except AttributeError:
            pass

    # --- an empty suite is a measurement of nothing ------------------------
    assert _refused(s.parse_suite, {"id": "toy", "cases": []}) is not None, \
        "a suite with no cases is refused: there is nothing to measure"
    assert _refused(s.parse_suite, ["id", "cases"]) is not None, \
        "a spec that is not a mapping is refused"

    # --- typos -------------------------------------------------------------
    for spec, bad in (
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "a"}], "metric": ["em"]},
         "metric"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "a", "repeat": 2}]},
         "repeat"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "a"}], "max_tick": 5},
         "max_tick"),
    ):
        message = _refused(s.parse_suite, spec)
        assert message is not None, "an unknown key must be refused, not ignored: %r" % (bad,)
        assert bad in message, \
            "the refusal names the offending key %r, got %r" % (bad, message)

    # --- ids ---------------------------------------------------------------
    for spec, why in (
        ({"cases": [{"id": "a", "prompt": "p", "answer": "a"}]}, "a suite without an id"),
        ({"id": "", "cases": [{"id": "a", "prompt": "p", "answer": "a"}]}, "an empty suite id"),
        ({"id": "   ", "cases": [{"id": "a", "prompt": "p", "answer": "a"}]},
         "a whitespace-only suite id"),
        ({"id": "toy"}, "a suite without cases"),
        ({"id": 7, "cases": [{"id": "a", "prompt": "p", "answer": "a"}]}, "a numeric suite id"),
        ({"id": "toy", "cases": [{"prompt": "p", "answer": "a"}]}, "a case without an id"),
        ({"id": "toy", "cases": [{"id": "", "prompt": "p", "answer": "a"}]},
         "an empty case id"),
    ):
        assert _refused(s.parse_suite, spec) is not None, "%s is refused" % (why,)

    duplicate = {"id": "toy", "cases": [
        {"id": "a", "prompt": "p", "answer": "1"},
        {"id": "b", "prompt": "q", "answer": "2"},
        {"id": "a", "prompt": "r", "answer": "3"},
    ]}
    message = _refused(s.parse_suite, duplicate)
    assert message is not None, \
        "a duplicated case id is refused: downstream, one of the two would be silently lost"
    assert "a" in message, "the duplicate refusal names the id, got %r" % (message,)

    # --- prompts, answers, tags -------------------------------------------
    for spec, why in (
        ({"id": "toy", "cases": [{"id": "a", "answer": "5"}]}, "a case without a prompt"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "", "answer": "5"}]},
         "an empty prompt"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p"}]}, "a case without an answer"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": 5}]},
         "a numeric answer"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "tags": "easy"}]},
         "tags written as a bare string"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "tags": [""]}]},
         "an empty tag"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "tags": [7]}]},
         "a numeric tag"),
    ):
        assert _refused(s.parse_suite, spec) is not None, "%s is refused" % (why,)
    empty_answer = s.parse_suite({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": ""}]})
    assert empty_answer.cases[0].answer == "", \
        "an empty answer is a legitimate expected answer (a case that expects silence)"
    tagged = s.parse_suite({"id": "toy", "cases": [
        {"id": "a", "prompt": "p", "answer": "5", "tags": ["easy", "math"]}]})
    assert tagged.cases[0].tags == ("easy", "math"), \
        "tags are materialised as a tuple in declared order, got %r" % (tagged.cases[0].tags,)

    # --- numbers that are not numbers --------------------------------------
    for spec, why in (
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "weight": 0}]},
         "a zero weight"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "weight": -2}]},
         "a negative weight"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "weight": "2"}]},
         "a weight written as a string"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "weight": True}]},
         "a boolean weight (True == 1)"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "max_ticks": True}]},
         "a boolean max_ticks"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "max_ticks": 0}]},
         "a zero per-case tick budget"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "max_ticks": 2.5}]},
         "a fractional max_ticks"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "repeats": 0}]},
         "zero repeats"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5", "repeats": "2"}]},
         "repeats written as a string"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "max_calls": 0},
         "a zero call budget"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}],
          "max_judge_calls": -1}, "a negative judge budget"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "max_ticks": True},
         "a boolean run budget"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "notes": 5},
         "notes that are not a string"),
    ):
        assert _refused(s.parse_suite, spec) is not None, "%s is refused" % (why,)

    weighted = s.parse_suite({"id": "toy", "cases": [
        {"id": "a", "prompt": "p", "answer": "5", "weight": 2.5, "max_ticks": 3, "repeats": 2}]})
    assert (weighted.cases[0].weight, weighted.cases[0].max_ticks,
            weighted.cases[0].repeats) == (2.5, 3, 2), \
        "an explicit weight/max_ticks/repeats survives parsing: %r" % (weighted.cases[0],)

    # --- metrics -----------------------------------------------------------
    for spec, why in (
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "metrics": "em"},
         "metrics written as a bare string"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}],
          "metrics": ["em", "em"]}, "the same metric listed twice"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "metrics": [""]},
         "an empty metric name"),
        ({"id": "toy", "cases": [{"id": "a", "prompt": "p", "answer": "5"}], "metrics": [7]},
         "a numeric metric name"),
    ):
        assert _refused(s.parse_suite, spec) is not None, "%s is refused" % (why,)
    measured = s.parse_suite({"id": "toy", "cases": [
        {"id": "a", "prompt": "p", "answer": "5"}], "metrics": ["em", "f1"]})
    assert measured.metrics == ("em", "f1"), \
        "metrics are materialised in declared order, got %r" % (measured.metrics,)

    # --- the canonical text belongs to the run, not to the file ------------
    spelled_out = {"id": "toy", "cases": [
        {"id": "a", "prompt": "2+3?", "answer": "5", "weight": 1.0, "max_ticks": 10,
         "repeats": 1, "tags": []}],
        "metrics": [], "max_ticks": 1000, "max_calls": 1000, "max_judge_calls": 500,
        "notes": ""}
    assert s.canonical_suite(s.parse_suite(minimal)) \
        == s.canonical_suite(s.parse_suite(spelled_out)), \
        ("two specs that describe the same run must canonicalise equal: a default spelled "
         "out is not a different run")
    assert s.canonical_suite(s.parse_suite(minimal)) == (
        '{"cases":[{"answer":"5","id":"a","max_ticks":10,"prompt":"2+3?","repeats":1,'
        '"tags":[],"weight":1.0}],"id":"toy","max_calls":1000,"max_judge_calls":500,'
        '"max_ticks":1000,"metrics":[],"notes":""}'), \
        "the canonical form is the effective config, sorted, with no whitespace: %r" \
        % (s.canonical_suite(s.parse_suite(minimal)),)
    assert s.canonical_suite(s.parse_suite(minimal)) == s.canonical_suite(s.parse_suite(minimal)), \
        "the canonical form is a pure function of the parsed suite"
    reordered = {"id": "toy", "cases": [
        {"id": "b", "prompt": "3+4?", "answer": "7"},
        {"id": "a", "prompt": "2+3?", "answer": "5"}]}
    swapped = {"id": "toy", "cases": [
        {"id": "a", "prompt": "2+3?", "answer": "5"},
        {"id": "b", "prompt": "3+4?", "answer": "7"}]}
    assert s.canonical_suite(s.parse_suite(reordered)) \
        != s.canonical_suite(s.parse_suite(swapped)), \
        "case order is part of the config: the declared order is what the log follows"
    other = {"id": "toy2", "cases": [{"id": "a", "prompt": "2+3?", "answer": "5"}]}
    assert s.canonical_suite(s.parse_suite(other)) != s.canonical_suite(s.parse_suite(minimal)), \
        "a different suite id is a different config"
    assert s.canonical_suite(s.parse_suite(reordered)).find('"b"') \
        < s.canonical_suite(s.parse_suite(reordered)).find('"a"'), \
        "the canonical form keeps the declared case order (b first): %r" \
        % (s.canonical_suite(s.parse_suite(reordered)),)

    print("check_01: a typo, an identity, a number that is a bool, an empty answer and a "
          "canonical form that belongs to the run — all asserted (%d refusals probed)"
          % (16 + len(s.SUITE_KEYS) + len(s.CASE_KEYS),))

def check_2():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        from lab import ConfigError
        try:
            fn(*args, **kwargs)
        except ConfigError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    def _refusal(why, fn, *args, **kwargs):
        """The ConfigError message for `why`, or an AssertionError naming the mistake.

        A call that returns normally, or that raises something that is not a
        ConfigError, is not a refusal.
        """
        message = _refused(fn, *args, **kwargs)
        assert message is not None, "%s must be refused, and it was not" % (why,)
        assert not message.startswith("WRONG TYPE"), \
            "%s must be refused with a ConfigError, got %r" % (why, message)
        return message

    from lab import make_case
    import stage_02 as s

    case = make_case("q1", prompt="2+3?", answer="5")

    # --- a name resolves to the plugin it was registered under -------------
    call_log = []

    def em(case_, answer):
        call_log.append((case_, answer))
        return 1.0

    def f1(case_, answer):
        return 0.5

    registry = s.MetricRegistry()
    assert registry.register("em", em) is None, \
        "register returns nothing: the registry is the state, not the return"
    registry.register("f1", f1)
    assert registry.resolve("em") is em and registry.resolve("f1") is f1, \
        ("resolve returns the very callable that was registered, not a name and "
         "not a wrapper: %r" % (registry.resolve("em"),))

    bound = registry.bind(["em", "f1"])
    assert type(bound) is tuple, \
        "bind returns a tuple of pairs, got %r" % (type(bound).__name__,)
    assert [name for name, _ in bound] == ["em", "f1"], \
        "bind keeps the declared order and every name: %r" % (bound,)
    assert all(callable(fn) for _, fn in bound), \
        "bind resolves each name to its plugin, not to the name itself: %r" % (bound,)
    assert bound[0][1] is em and bound[1][1] is f1, \
        "each entry carries the plugin registered under its own name: %r" % (bound,)
    assert registry.bind(()) == (), \
        "binding nothing resolves nothing, cleanly: %r" % (registry.bind(()),)
    assert call_log == [], \
        "binding resolves the plugins; it does not run them: %r" % (call_log,)

    # --- a name that is a typo is refused, before the first case -----------
    message = _refusal("an unknown plugin name", registry.resolve, "f2")
    assert "f2" in message, "the refusal names the missing plugin, got %r" % (message,)
    assert "em" in message and "f1" in message, \
        ("the refusal lists the plugins that do exist, so a typo is obvious: %r"
         % (message,))
    _refusal("a list with one unknown plugin", registry.bind, ["em", "nope"])
    assert call_log == [], \
        "a refused binding measured nothing at all: %r" % (call_log,)

    # --- one registry is not another ---------------------------------------
    left, right = s.MetricRegistry(), s.MetricRegistry()
    left.register("em", em)
    _refusal("a name registered in a different registry", right.resolve, "em")

    # --- a duplicate name, and a plugin that is not callable ---------------
    other = s.MetricRegistry()
    other.register("em", em)
    _refusal("registering the same name twice", other.register, "em", f1)
    assert other.resolve("em") is em, \
        ("a refused duplicate must not have replaced the first plugin: a silent "
         "last-wins hides a copy-pasted metric list")
    _refusal("a plugin that is not callable", other.register, "boxed", 5)
    _refusal("the name of a refused non-callable plugin", other.resolve, "boxed")

    # --- a plugin that returns a number ------------------------------------
    result = s.apply_metrics(case, "5", (("em", em),))
    assert sorted(result) == ["errors", "values"], \
        ("apply_metrics answers with exactly {'values': ..., 'errors': ...}, got %r"
         % (sorted(result),))
    assert call_log == [(case, "5")], \
        ("the plugin is called as metric(case, answer), the case object included: %r"
         % (call_log,))
    assert result["values"] == {"em": 1.0} and result["errors"] == {}, \
        "a finite number is a value and nothing else: %r" % (result,)
    call_log.clear()

    def count(case_, answer):
        return 7

    def not_applicable(case_, answer):
        return None

    def boom(case_, answer):
        raise ValueError("boom")

    result = s.apply_metrics(case, "5", (("count", count),))
    assert type(result["values"]["count"]) is float and result["values"]["count"] == 7.0, \
        ("a value in a record is a float (the log is JSON), got %r"
         % (result["values"]["count"],))

    # --- "not applicable" is not a zero ------------------------------------
    result = s.apply_metrics(case, "5", (("na", not_applicable),))
    assert "na" in result["values"], \
        ("a plugin that returns None ran and reported 'not applicable to this "
         "case': the entry stays, because stage 5 shrinks its n by it")
    assert result["values"]["na"] is None, \
        ("None is not applicable, not a zero: 0.0 would make this case vote in "
         "every mean instead of shrinking the denominator")
    assert result["errors"] == {}, \
        "'not applicable' is not a failure: %r" % (result["errors"],)

    # --- a plugin that raises is recorded, not fatal -----------------------
    result = s.apply_metrics(case, "5", (("em", em), ("raiser", boom)))
    assert result["values"] == {"em": 1.0}, \
        ("a plugin that raises contributes nothing to values, and the metrics "
         "that already succeeded are kept: %r" % (result["values"],))
    assert result["errors"] == {"raiser": "ValueError: boom"}, \
        ("a failure is recorded under the metric's NAME as '<ExceptionType>: "
         "<message>' — the name is the key, not the message: %r" % (result["errors"],))
    result = s.apply_metrics(case, "5", (("raiser", boom), ("em", em)))
    assert result["values"] == {"em": 1.0} and set(result["errors"]) == {"raiser"}, \
        "a broken plugin is isolated: the plugins after it still run: %r" % (result,)

    # --- what is not a measurement is an error, never a value --------------
    for fn, label, named in (
        (lambda case_, answer: True, "the bool True (True == 1)", "bool"),
        (lambda case_, answer: False, "the bool False", "bool"),
        (lambda case_, answer: "0.5", "the string '0.5'", "str"),
        (lambda case_, answer: float("nan"), "nan", "nan"),
        (lambda case_, answer: float("inf"), "inf", "inf"),
        (lambda case_, answer: float("-inf"), "-inf", "-inf"),
        (lambda case_, answer: [1.0], "a list", "list"),
    ):
        result = s.apply_metrics(case, "5", (("m", fn),))
        assert "m" not in result["values"], \
            "%s is not a measurement, so it must not land in values: %r" % (label, result)
        assert "m" in result["errors"], \
            "%s must be an error the record carries, got %r" % (label, result["errors"])
        assert named in result["errors"]["m"], \
            ("the error names the bad type or value (%r), got %r"
             % (named, result["errors"]["m"]))

    # --- no metrics at all -------------------------------------------------
    empty = s.apply_metrics(case, "5", ())
    assert empty == {"values": {}, "errors": {}}, \
        "a case with no metrics measures nothing, and says so: %r" % (empty,)

    print("check_02: a typo refused before the first case, a duplicate name that does "
          "not replace, a None that shrinks the denominator instead of voting zero, and "
          "the four shapes of a broken plugin (a raise, a bool, a str, nan/inf) — all "
          "asserted (13 apply_metrics shapes)")

def check_3():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _identity(case, answer):
        """A metric that scores exactly the answers the strict judge would."""
        return 1.0 if answer.strip() == case.answer.strip() else 0.0

    import lab
    import stage_03 as s

    # --- the frozen vocabulary ---------------------------------------------
    assert s.STATUSES == ("ok", "no_answer", "solver_error", "timeout", "case_error"), \
        "the status vocabulary is the contract's, got %r" % (s.STATUSES,)
    assert s.CASE_RECORD_KEYS == ("case", "repeat", "weight", "status", "answer", "metrics",
                                  "metric_errors", "ticks", "calls", "note"), \
        "the record's keys are the contract's, got %r" % (s.CASE_RECORD_KEYS,)
    assert s.METRIC_DP == 6, "METRIC_DP is the contract's, got %r" % (s.METRIC_DP,)

    clock = lab.Ticker()
    case = lab.make_case("sum-2-3", max_ticks=5)
    bound = (("identity", _identity),)

    # --- an answer in budget -----------------------------------------------
    solver = lab.perfect(clock=clock)
    record = s.run_case(case, solver, clock=clock, bound=bound)
    assert list(record) == list(s.CASE_RECORD_KEYS), \
        ("a record carries exactly the contract's keys, in order: %r" % (list(record),))
    assert record["case"] == "sum-2-3" and record["repeat"] == 0, \
        "the record names the case and the repeat: %r" % (record,)
    assert record["status"] == "ok", "an answer in budget is ok, got %r" % (record["status"],)
    assert record["answer"] == "5", "the answer is kept, got %r" % (record["answer"],)
    assert record["calls"] == 1, "the solver was called once, got %r" % (record["calls"],)
    assert record["weight"] == 1.0, \
        ("the record carries the case's declared weight: the rollup happens after the run "
         "and reads records, so the weight has to travel with the measurement (%r)"
         % (record["weight"],))
    assert record["ticks"] == 0, "a solver that spends nothing costs no ticks, got %r" \
        % (record["ticks"],)
    assert record["metrics"] == {"identity": 1.0}, \
        "the bound metric measured the answer, got %r" % (record["metrics"],)
    assert record["metric_errors"] == {}, \
        "a metric that worked leaves no error, got %r" % (record["metric_errors"],)
    assert record["note"] == "", "an ok record has nothing to explain, got %r" % (record["note"],)
    assert json.dumps(record, sort_keys=True), "a record is JSON-serialisable as it stands"

    repeat = s.run_case(case, solver, clock=clock, bound=bound, repeat=2)
    assert repeat["repeat"] == 2, "the repeat index is the caller's, got %r" % (repeat["repeat"],)
    assert repeat["ticks"] == 0 and record["ticks"] == 0, \
        "the ticks are measured around the call, not from the start of the run"

    weighted = s.run_case(lab.make_case("sum-2-3", weight=2.5), lab.perfect(clock=clock),
                          clock=clock, bound=bound)
    assert weighted["weight"] == 2.5, \
        "and it is the case's own weight, not a default: %r" % (weighted["weight"],)
    for bad_weight, why in ((0.0, "a zero weight"), ("2", "a weight written as a string"),
                            (True, "a boolean weight")):
        broken = s.run_case(lab.make_case("sum-2-3", weight=bad_weight),
                            lab.perfect(clock=clock), clock=clock, bound=bound)
        assert broken["status"] == "case_error", \
            ("%s is our own preparation failure, so the case is a case_error and the reason "
             "is in the note: %r" % (why, broken))

    # --- the clock is the cost, not the stopwatch --------------------------
    ticker = lab.Ticker()
    slow_case = lab.make_case("sum-2-3", max_ticks=5)
    slow_record = s.run_case(slow_case, lab.slow(3, clock=ticker), clock=ticker, bound=bound)
    assert slow_record["status"] == "ok" and slow_record["ticks"] == 3, \
        "a solver that spends three ticks is a call of three ticks: %r" % (slow_record,)

    # --- a timeout discards the answer -------------------------------------
    ticker = lab.Ticker()
    late_case = lab.make_case("sum-2-3", max_ticks=2)
    late = s.run_case(late_case, lab.slow(3, clock=ticker), clock=ticker, bound=bound)
    assert late["status"] == "timeout", \
        "a call past the case's deadline is a timeout, got %r" % (late["status"],)
    assert late["answer"] is None, \
        "a timed-out answer is discarded: it was not produced under the budget"
    assert late["ticks"] == 3, "the cost that caused it is recorded, got %r" % (late["ticks"],)
    assert late["metrics"] == {} and late["metric_errors"] == {}, \
        ("no metric runs for a timeout: a number computed on work the budget forbade is a "
         "number about nothing: %r" % (late,))
    assert "3" in late["note"] and "2" in late["note"], \
        "the note says how far past the deadline the call went, got %r" % (late["note"],)

    # --- a silent solver is not a zero ------------------------------------
    ticker = lab.Ticker()
    quiet = s.run_case(lab.make_case("sum-2-3"), lab.silent(clock=ticker), clock=ticker,
                       bound=bound)
    assert quiet["status"] == "no_answer" and quiet["answer"] is None, \
        "a solver that answers nothing is no_answer, got %r" % (quiet,)
    assert quiet["calls"] == 1, "it was still a call, got %r" % (quiet["calls"],)
    assert quiet["metrics"] == {}, \
        "there is nothing to measure: a missing answer is not an empty one"

    # --- the solver's failure is data, ours is a bug -----------------------
    ticker = lab.Ticker()
    boom = s.run_case(lab.make_case("sum-2-3", max_ticks=9),
                      lab.slow(2, wrapped=lab.crashing(1, clock=ticker), clock=ticker),
                      clock=ticker, bound=bound)
    assert boom["status"] == "solver_error", \
        "an exception from the solver is a solver_error, got %r" % (boom["status"],)
    assert boom["note"].startswith("RuntimeError: "), \
        "the note carries the type and the message so a run can be read without a traceback: %r" \
        % (boom["note"],)
    assert boom["calls"] == 1 and boom["answer"] is None, \
        "the call happened and produced no answer: %r" % (boom,)
    assert boom["ticks"] == 2, \
        "what a failing solver spent is still cost, got %r" % (boom["ticks"],)
    assert boom["metrics"] == {} and boom["metric_errors"] == {}, \
        "nothing was measured because nothing was answered: %r" % (boom,)

    ticker = lab.Ticker()
    wrong_type = s.run_case(lab.make_case("sum-2-3"),
                            lab.Solver(lambda prompt, ticker_, call: 5, clock=ticker),
                            clock=ticker, bound=bound)
    assert wrong_type["status"] == "solver_error", \
        ("a solver that answers with something that is not a str is a protocol violation, "
         "not an answer to score: %r" % (wrong_type,))
    assert "int" in wrong_type["note"], \
        "the note names the type that came back, got %r" % (wrong_type["note"],)

    ticker = lab.Ticker()
    raised_late = s.run_case(lab.make_case("sum-2-3", max_ticks=1),
                             lab.slow(5, wrapped=lab.crashing(1, clock=ticker), clock=ticker),
                             clock=ticker, bound=bound)
    assert raised_late["status"] == "solver_error", \
        ("a call that raised past its deadline is still a solver_error: we know why it "
         "failed, and that is more useful than 'timeout': %r" % (raised_late,))
    ticker = lab.Ticker()
    quiet_late = s.run_case(lab.make_case("sum-2-3", max_ticks=1),
                            lab.slow(5, wrapped=lab.silent(clock=ticker), clock=ticker),
                            clock=ticker, bound=bound)
    assert quiet_late["status"] == "timeout", \
        "a late silence is a timeout first: the budget is the binding constraint: %r" \
        % (quiet_late,)

    # --- our own broken case is our own bug, and the solver never runs -----
    for broken, why in (
        (types.SimpleNamespace(id="bad", prompt="p", max_ticks="ten"),
         "a max_ticks that is a string"),
        (types.SimpleNamespace(id="bad", prompt="", max_ticks=3), "an empty prompt"),
        (types.SimpleNamespace(id="bad", max_ticks=3), "a case with no prompt at all"),
        (types.SimpleNamespace(id="bad", prompt="p", max_ticks=0), "a zero deadline"),
        (types.SimpleNamespace(id="bad", prompt="p", max_ticks=True), "a boolean deadline"),
    ):
        ticker = lab.Ticker()
        caller = lab.perfect(clock=ticker)
        rec = s.run_case(broken, caller, clock=ticker, bound=bound)
        assert rec["status"] == "case_error", \
            "%s is OUR bug in preparing the case, so it is a case_error, got %r" \
            % (why, rec["status"])
        assert caller.calls == 0, \
            "a case that cannot be prepared must not cost a model call (%s)" % (why,)
        assert rec["ticks"] == 0 and rec["calls"] == 0, \
            "no call happened, so nothing was spent: %r" % (rec,)
        assert rec["note"], "a case_error says why: %r" % (rec,)
    nameless = s.run_case(types.SimpleNamespace(prompt="p", max_ticks=3),
                          lab.perfect(clock=lab.Ticker()), clock=lab.Ticker(), bound=bound)
    assert nameless["case"] == "", \
        "a record whose case has no usable id still has a record: %r" % (nameless["case"],)
    assert nameless["status"] == "case_error", "and it is still a case_error: %r" % (nameless,)

    try:
        s.run_case(case, lab.perfect(), clock=lab.Ticker(), bound=bound, repeat=True)
        raise AssertionError("repeat must be an int, not a bool: %r" % (True,))
    except lab.ConfigError:
        pass

    # --- the metric layer is separate from the answer's status -------------
    def broken_metric(case, answer):
        raise KeyError("no such field")

    def inapplicable(case, answer):
        return None

    ticker = lab.Ticker()
    mixed = s.run_case(lab.make_case("sum-2-3"), lab.perfect(clock=ticker), clock=ticker,
                       bound=(("identity", _identity), ("broken", broken_metric),
                              ("n/a", inapplicable)))
    assert mixed["status"] == "ok", \
        "a metric that broke does not turn an answered case into a failure: %r" % (mixed,)
    assert mixed["metrics"] == {"identity": 1.0, "n/a": None}, \
        ("a metric that raised contributes nothing to metrics, and a metric that says "
         "'not applicable' is recorded as None (it shrinks the denominator, it is not a "
         "zero): %r" % (mixed["metrics"],))
    assert "broken" in mixed["metric_errors"], \
        "the metric error is filed under the metric's name: %r" % (mixed["metric_errors"],)
    assert "KeyError" in mixed["metric_errors"]["broken"], \
        "the metric error carries the type and the message: %r" % (mixed["metric_errors"],)

    # --- the rounding that makes two runs the same bytes -------------------
    raw = {"case": "c", "repeat": 0, "status": "ok", "answer": "5",
           "metrics": {"third": 1 / 3, "tenth": 0.1 + 0.2, "exact": 0.5,
                       "tiny": 1e-9, "na": None, "neg": -0.0},
           "metric_errors": {}, "ticks": 1, "calls": 1, "note": ""}
    rounded = s.round_metrics(raw)
    assert rounded["metrics"] == {"third": 0.333333, "tenth": 0.3, "exact": 0.5,
                                  "tiny": 0.0, "na": None, "neg": 0.0}, \
        "metric values are rounded to METRIC_DP with -0.0 normalised: %r" % (rounded["metrics"],)
    assert str(rounded["metrics"]["neg"]) == "0.0", \
        "the log is compared as text, so -0.0 is not 0.0: %r" % (str(rounded["metrics"]["neg"]),)
    assert raw["metrics"]["tenth"] == 0.1 + 0.2 and repr(raw["metrics"]["neg"]) == "-0.0", \
        "round_metrics is a copy: the record handed in is not modified: %r" % (raw["metrics"],)
    assert rounded["ticks"] == 1 and rounded["note"] == "" and rounded["status"] == "ok", \
        "only the metric values are rounded: %r" % (rounded,)
    assert rounded["metrics"] is not raw["metrics"], \
        "the rounded metrics are a new dict, not the caller's"

    print("check_03: %d statuses and the rounding rules asserted" % (len(s.STATUSES),))

def check_4():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _identity(case, answer):
        return 1.0 if answer is not None and answer.strip() == case.answer.strip() else 0.0

    class _Registry:
        """A hand-built plugin registry: this check asserts the runner's contract
        with it, not stage 2's implementation."""

        def __init__(self, bound=(), unknown=None, per_case=None):
            self.binds = []
            self._bound = bound
            self._unknown = unknown
            self._per_case = per_case

        def bind(self, names):
            from lab import ConfigError
            self.binds.append(tuple(names))
            if self._per_case is not None and len(self.binds) >= self._per_case:
                self._bound = (("late", _identity),)
            if self._unknown is not None and self._unknown in names:
                raise ConfigError("no plugin named %r" % (self._unknown,))
            return self._bound

    class _Sink:
        def __init__(self):
            self.records = []

        def __call__(self, record):
            self.records.append(record)

    import lab
    import stage_04 as s

    assert s.RUN_KEYS == ("suite", "cases", "records", "status_counts", "metric_errors",
                          "ticks", "calls", "stopped"), \
        "the run summary's keys are the contract's, got %r" % (s.RUN_KEYS,)

    # every case points at a real lab question, so lab's actors can answer it
    def case(case_id, *, repeats=1, max_ticks=10, weight=1.0):
        return lab.make_case(case_id, "What is 2 + 3?", "5", repeats=repeats,
                             max_ticks=max_ticks, weight=weight)

    def solver_for(clock, ticks=0):
        solver = lab.perfect(clock=clock)
        return solver if not ticks else lab.slow(ticks, wrapped=solver, clock=clock)

    # --- the order of the log, and the counters ----------------------------
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("b", repeats=2), case("a"), case("c")],
                           metrics=("identity",))
    registry = _Registry(bound=(("identity", _identity),))
    sink = _Sink()
    solver = solver_for(clock)
    run = s.run_suite(suite, solver, clock=clock, registry=registry, sink=sink)

    assert [r["case"] for r in sink.records] == ["b", "b", "a", "c"], \
        ("the log follows the suite's declared order, with a case's repeats adjacent: %r"
         % ([r["case"] for r in sink.records],))
    assert [r["repeat"] for r in sink.records] == [0, 1, 0, 0], \
        ("a case's repeats are numbered from zero: %r" % ([r["repeat"] for r in sink.records],))
    assert run["suite"] == "toy" and run["cases"] == 3 and run["records"] == 4, \
        "cases counts what the suite declares, records what the log holds: %r" % (run,)
    assert run["status_counts"] == {"ok": 4, "no_answer": 0, "solver_error": 0,
                                    "timeout": 0, "case_error": 0}, \
        "status_counts carries every status, zero-filled: %r" % (run["status_counts"],)
    assert run["stopped"] is None, "a run that finished reports no stop: %r" % (run["stopped"],)
    assert run["ticks"] == 0 and run["calls"] == 4, \
        "ticks and calls are the sums over the records: %r" % (run,)
    assert run["metric_errors"] == 0, \
        "a run whose metrics all worked carries no metric failures: %r" % (run["metric_errors"],)
    assert solver.calls == 4, "one call per record, got %r" % (solver.calls,)
    assert registry.binds == [("identity",)], \
        "the plugins are bound once, before the first case: %r" % (registry.binds,)
    assert all(r["metrics"] == {"identity": 1.0} for r in sink.records), \
        "the bound metrics reach every record: %r" % (sink.records[0]["metrics"],)

    # --- a missing plugin fails the run before it costs anything -----------
    clock = lab.Ticker()
    registry = _Registry(unknown="nope")
    solver = solver_for(clock)
    try:
        s.run_suite(lab.make_suite("toy", [case("a")], metrics=("nope",)), solver,
                    clock=clock, registry=registry)
        raise AssertionError("an unknown metric plugin must fail the run, not be ignored")
    except lab.ConfigError as exc:
        assert "nope" in str(exc), "the refusal names the plugin: %r" % (str(exc),)
    assert solver.calls == 0, \
        ("the config is checked before the first call: a run that cannot be measured must "
         "not spend anything (%r calls)" % (solver.calls,))

    # --- the call budget is a limit, not a receipt -------------------------
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a"), case("b"), case("c")], max_calls=2)
    sink = _Sink()
    solver = solver_for(clock)
    run = s.run_suite(suite, solver, clock=clock, registry=_Registry(),
                      sink=sink)
    assert [r["case"] for r in sink.records] == ["a", "b"], \
        ("the call that would exceed max_calls does not happen: %r"
         % ([r["case"] for r in sink.records],))
    assert solver.calls == 2, "the model was called exactly max_calls times: %r" % (solver.calls,)
    assert run["stopped"] == "calls" and run["records"] == 2 and run["cases"] == 3, \
        ("a stopped run says which budget stopped it, keeps what it produced, and does not "
         "pretend the suite was smaller: %r" % (run,))

    # --- the budget counts calls, not cases -------------------------------
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a", repeats=3), case("b")], max_calls=2)
    sink = _Sink()
    s.run_suite(suite, solver_for(clock), clock=clock, registry=_Registry(), sink=sink)
    assert [(r["case"], r["repeat"]) for r in sink.records] == [("a", 0), ("a", 1)], \
        ("max_calls counts calls, so a repeated case can be cut in the middle: %r"
         % ([(r["case"], r["repeat"]) for r in sink.records],))

    # --- the clock budget is checked before the call ----------------------
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a"), case("b"), case("c")], max_ticks=3)
    sink = _Sink()
    solver = solver_for(clock, ticks=2)
    run = s.run_suite(suite, solver, clock=clock, registry=_Registry(), sink=sink)
    assert [r["case"] for r in sink.records] == ["a", "b"], \
        ("the clock budget is checked before each call: after a (2) and b (4) the run stops, "
         "and c never runs: %r" % ([r["case"] for r in sink.records],))
    assert run["stopped"] == "ticks", "and it says the clock stopped it: %r" % (run["stopped"],)
    assert run["ticks"] == 4 and solver.calls == 2, \
        ("the clock budget cannot be enforced exactly: it is checked before the call, so a "
         "run can exceed it by one case's cost — that is the honest limit, and the cost is "
         "in the log: %r" % (run,))
    # the boundary: reaching exactly the budget does not stop the run early
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a"), case("b")], max_ticks=2)
    sink = _Sink()
    s.run_suite(suite, solver_for(clock, ticks=2), clock=clock, registry=_Registry(), sink=sink)
    assert len(sink.records) == 2, \
        ("a run that is exactly at its clock budget is not stopped: the check is strictly "
         "greater-than, and the next call is what spends past it: %r" % (sink.records,))

    # --- when both budgets are spent, the call budget is the reason --------
    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a"), case("b")], max_ticks=1, max_calls=1)
    sink = _Sink()
    run = s.run_suite(suite, solver_for(clock, ticks=5), clock=clock, registry=_Registry(),
                      sink=sink)
    assert run["stopped"] == "calls", \
        ("with both budgets spent the call budget is the reason: it is exact, and it is the "
         "one that cannot be overspent: %r" % (run["stopped"],))

    # --- statuses flow through, and a broken case is ours ------------------
    clock = lab.Ticker()
    broken = types.SimpleNamespace(id="broken", prompt="p", max_ticks="ten")
    suite = lab.make_suite("toy", [case("a"), broken, case("b")])
    sink = _Sink()
    solver = lab.crashing(when=2, clock=clock)
    run = s.run_suite(suite, solver, clock=clock, registry=_Registry(), sink=sink)
    assert [r["status"] for r in sink.records] == ["ok", "case_error", "solver_error"], \
        ("a case that fails does not stop the run and is not the harness's fault, and a "
         "broken case does not stop it either: %r" % ([r["status"] for r in sink.records],))
    assert run["status_counts"] == {"ok": 1, "no_answer": 0, "solver_error": 1,
                                    "timeout": 0, "case_error": 1}, \
        "the status counts are the log's: %r" % (run["status_counts"],)
    assert run["calls"] == 2 and solver.calls == 2, \
        ("a case_error costs no call, so the run's calls are the records' calls: %r"
         % (run,))
    assert run["cases"] == 3 and run["records"] == 3, \
        "the whole suite ran: %r" % (run,)

    # --- a record that was answered but not measured -----------------------
    def angry(case, answer):
        raise ValueError("this metric is broken")

    clock = lab.Ticker()
    suite = lab.make_suite("toy", [case("a"), case("b")])
    run = s.run_suite(suite, solver_for(clock), clock=clock,
                      registry=_Registry(bound=(("angry", angry),)))
    assert run["status_counts"]["ok"] == 2, \
        ("a metric that broke does not turn an answered case into a failure: %r"
         % (run["status_counts"],))
    assert run["metric_errors"] == 2, \
        ("but the summary counts the records whose metrics failed: run_exit (stage 8) refuses "
         "to publish a run it cannot measure, and it reads the summary, not the log: %r"
         % (run,))

    # --- the quiet paths --------------------------------------------------
    clock = lab.Ticker()
    run = s.run_suite(lab.make_suite("toy", [case("a")]), solver_for(clock), clock=clock,
                      registry=_Registry())
    assert run["records"] == 1 and run["stopped"] is None, \
        "the sink is optional: %r" % (run,)
    clock = lab.Ticker()
    empty = s.run_suite(lab.make_suite("toy", []), solver_for(clock), clock=clock,
                        registry=_Registry())
    assert empty["cases"] == 0 and empty["records"] == 0 and empty["stopped"] is None, \
        "an empty suite is a run of nothing, not a crash: %r" % (empty,)
    assert sum(empty["status_counts"].values()) == 0, \
        "and its counters are still all there: %r" % (empty["status_counts"],)

    print("check_04: order, repeats, two budgets, the bind before the first call, and "
          "counters that come from the log — %d records asserted by hand"
          % (len(sink.records) + 4,))

def check_5():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    STATUSES = ("ok", "no_answer", "solver_error", "timeout", "case_error")

    def _record(case, repeat, status="ok", metrics=None, weight=1.0,
                metric_errors=None, ticks=1, calls=1, answer="an answer", note=""):
        """One case record, hand-built: stage 3's nine keys plus the case's weight.

        Stage 3's record has no room for the weight, so the runner hands it to the
        rollup alongside the record; a record that does not carry one weighs 1.0.
        """
        return {"case": case, "repeat": repeat, "status": status, "answer": answer,
                "metrics": dict(metrics or {}),
                "metric_errors": dict(metric_errors or {}),
                "ticks": ticks, "calls": calls, "note": note, "weight": weight}

    import stage_05 as s
    from stage_03 import METRIC_DP

    assert METRIC_DP == 6, \
        ("the rollup rounds the way the records do: METRIC_DP is 6, got %r"
         % (METRIC_DP,))
    assert (s.MIN_N, s.MAX_SPREAD) == (3, 0.35), \
        ("the thresholds are the contract's — MIN_N=3, MAX_SPREAD=0.35 — got %r"
         % ((s.MIN_N, s.MAX_SPREAD),))

    # --- the unit is the case, and a case's weight is applied exactly once --
    weighted = [
        _record("solo", 0, metrics={"em": 1.0}, weight=4.0),
        _record("duo", 0, metrics={"em": 0.2}),
        _record("duo", 1, metrics={"em": 0.4}),
        _record("ghost", 0, metrics={"em": None}),
        _record("ghost", 1, metrics={}),
    ]
    values = s.case_values(weighted)
    assert set(values) == {"solo", "duo", "ghost"}, \
        ("the rollup has one entry per CASE id, not one per record: 3 cases, got %r"
         % (sorted(values),))
    assert set(values["duo"]) == {"weight", "repeats", "values"}, \
        ("a case's entry is {weight, repeats, values}: %r" % (sorted(values["duo"]),))
    assert values["solo"] == {"weight": 4.0, "repeats": 1, "values": {"em": 1.0}}, \
        ("a case with one record keeps that record's weight and value: %r"
         % (values["solo"],))
    assert values["duo"]["repeats"] == 2, \
        ("`repeats` counts the records seen for the case — `duo` has 2 — got %r"
         % (values["duo"]["repeats"],))
    assert values["duo"]["values"]["em"] == 0.3, \
        ("a case's value is the mean over its repeats that produced one: "
         "[0.2, 0.4] -> 0.3, got %r" % (values["duo"]["values"]["em"],))
    assert values["ghost"] == {"weight": 1.0, "repeats": 2, "values": {}}, \
        ("a case whose records produced no value has an empty `values`, not a "
         "zero: %r" % (values["ghost"],))

    agg = s.aggregate(weighted)
    assert set(agg) == {"records", "cases", "status_counts", "metrics",
                        "case_errors"}, \
        ("the aggregate has exactly the contract's keys: %r" % (sorted(agg),))
    assert agg["records"] == 5 and agg["cases"] == 3, \
        ("the run reports its records (5) and its distinct cases (3) — not one "
         "twice: records=%r, cases=%r" % (agg["records"], agg["cases"]))
    em = agg["metrics"]["em"]
    assert set(em) == {"n", "mean", "min", "max", "spread", "stable"}, \
        ("a metric's statistics are {n, mean, min, max, spread, stable}: %r"
         % (sorted(em),))
    assert em["n"] == 2, \
        ("`n` counts the CASES that produced a value — `solo` and `duo`, not the "
         "4 records that mention the metric: got %r" % (em["n"],))
    assert em["mean"] == round((4.0 * 1.0 + 1.0 * 0.3) / (4.0 + 1.0), METRIC_DP), \
        ("the metric's mean is the WEIGHTED mean of the case values, "
         "(4*1.0 + 1*0.3)/5 = 0.86, got %r" % (em["mean"],))
    assert em["mean"] != round((1.0 + 0.2 + 0.4) / 3, METRIC_DP), \
        "a case's three repeats are not three votes in the mean"
    assert (em["min"], em["max"], em["spread"]) == (0.3, 1.0, 0.7), \
        ("min/max/spread are over the case values (0.3 and 1.0), got %r"
         % ((em["min"], em["max"], em["spread"]),))
    assert em["stable"] is False, \
        ("2 cases are fewer than MIN_N=3: a metric over two cases is not stable")
    assert s.stability_verdict(agg, "em") == "thin", \
        ("`n` is checked before the spread: 2 cases is `thin` even though the "
         "spread is wide — there is not enough data to call it noisy — got %r"
         % (s.stability_verdict(agg, "em"),))

    unweighted = s.case_values([
        {"case": "x", "repeat": 0, "status": "ok", "answer": "a",
         "metrics": {"em": 0.5}, "metric_errors": {}, "ticks": 1, "calls": 1,
         "note": ""}])
    assert unweighted["x"]["weight"] == 1.0, \
        ("a record that carries no weight weighs 1.0, so a plain stage 3 record "
         "aggregates: %r" % (unweighted["x"],))

    # --- three repeats of one case are still one case ----------------------
    balance = [
        _record("a", 0, metrics={"em": 0.0}),
        _record("a", 1, metrics={"em": 0.0}),
        _record("a", 2, metrics={"em": 1.0}),
        _record("b", 0, metrics={"em": 1.0}),
    ]
    per_case = s.case_values(balance)
    assert per_case["a"]["values"]["em"] == round(1 / 3, METRIC_DP), \
        ("a case's value is the mean over its repeats, rounded to METRIC_DP: %r, "
         "got %r" % (round(1 / 3, METRIC_DP), per_case["a"]["values"]["em"]))
    many = s.aggregate(balance)
    assert many["metrics"]["em"]["n"] == 2, \
        ("the three repeats of `a` are ONE case: n=2, got %r"
         % (many["metrics"]["em"]["n"],))
    assert round(many["metrics"]["em"]["mean"], 5) == 0.66667, \
        ("the mean is (1/3 + 1.0)/2 = 0.66667 over cases; 0.5 would be the mean "
         "over records, where `a`'s three repeats outvote `b`: got %r"
         % (many["metrics"]["em"]["mean"],))
    assert (many["metrics"]["em"]["min"], many["metrics"]["em"]["max"]) \
        == (round(1 / 3, METRIC_DP), 1.0), \
        ("min/max are over the case values (1/3 and 1.0), not over the records "
         "(0.0 and 1.0): got %r"
         % ((many["metrics"]["em"]["min"], many["metrics"]["em"]["max"]),))
    assert many["metrics"]["em"]["spread"] == round(1 - 1 / 3, METRIC_DP), \
        ("the spread is over the case values, so 1.0 - 1/3 = 0.666667, not the "
         "record spread of 1.0: got %r" % (many["metrics"]["em"]["spread"],))

    # --- every number in the rollup is rounded to METRIC_DP ----------------
    rounding = [
        _record("one", 0, metrics={"f1": 1.0, "raw": 1.0}, weight=1.0),
        _record("two", 0, metrics={"f1": 0.0, "raw": 0.7}, weight=2.0),
    ]
    rounded = s.aggregate(rounding)
    assert rounded["metrics"]["f1"]["mean"] == round(1 / 3, METRIC_DP), \
        ("the metric's mean is rounded to METRIC_DP like every other number in "
         "the log: the weighted mean of 1.0 and 0.0 at weights 1 and 2 is 1/3 = "
         "%r, got %r" % (round(1 / 3, METRIC_DP), rounded["metrics"]["f1"]["mean"]))
    assert rounded["metrics"]["raw"]["spread"] == 0.3, \
        ("the spread is rounded too: 1.0 - 0.7 is 0.30000000000000004 as a float "
         "and 0.3 in the log, got %r" % (rounded["metrics"]["raw"]["spread"],))

    # --- enough cases AND a narrow spread ----------------------------------
    spread = [
        _record("t1", 0, metrics={"tight": 0.5}),
        _record("t2", 0, metrics={"tight": 0.5}),
        _record("t3", 0, metrics={"tight": 0.5}),
        _record("e1", 0, metrics={"edge": 0.65}),
        _record("e2", 0, metrics={"edge": 1.0}),
        _record("e3", 0, metrics={"edge": 0.8}),
        _record("w1", 0, metrics={"wide": 0.64}),
        _record("w2", 0, metrics={"wide": 1.0}),
        _record("w3", 0, metrics={"wide": 0.8}),
        _record("l1", 0, metrics={"lonely": 0.7}),
        _record("p1", 0, metrics={"pair": 0.5}),
        _record("p2", 0, metrics={"pair": 0.5}),
        _record("g1", 0, metrics={"ghost": None}),
    ]
    rolled = s.aggregate(spread)
    assert set(rolled["metrics"]) == {"tight", "edge", "wide", "lonely", "pair",
                                      "ghost"}, \
        ("every metric the records mention appears in the rollup, including the "
         "one that never produced a value: %r" % (sorted(rolled["metrics"]),))
    tight = rolled["metrics"]["tight"]
    assert tight == {"n": 3, "mean": 0.5, "min": 0.5, "max": 0.5, "spread": 0.0,
                     "stable": True}, \
        ("three cases at one value: n=3 meets MIN_N and a zero spread is stable, "
         "got %r" % (tight,))
    assert rolled["metrics"]["edge"]["spread"] == s.MAX_SPREAD \
        and rolled["metrics"]["edge"]["stable"] is True, \
        ("the boundary is inclusive: a spread of exactly MAX_SPREAD is stable, "
         "got spread=%r, stable=%r"
         % (rolled["metrics"]["edge"]["spread"],
            rolled["metrics"]["edge"]["stable"]))
    assert rolled["metrics"]["wide"]["spread"] == 0.36 \
        and rolled["metrics"]["wide"]["stable"] is False, \
        ("0.36 is wider than MAX_SPREAD=0.35: not stable, got spread=%r, stable=%r"
         % (rolled["metrics"]["wide"]["spread"],
            rolled["metrics"]["wide"]["stable"]))
    assert rolled["metrics"]["lonely"] == {"n": 1, "mean": 0.7, "min": 0.7,
                                           "max": 0.7, "spread": 0.0,
                                           "stable": False}, \
        ("one case is a coin flip, not a stable metric: %r"
         % (rolled["metrics"]["lonely"],))
    assert rolled["metrics"]["pair"]["n"] == 2 \
        and rolled["metrics"]["pair"]["stable"] is False, \
        ("two cases are fewer than MIN_N=3, whatever the spread: %r"
         % (rolled["metrics"]["pair"],))
    assert rolled["metrics"]["ghost"] == {"n": 0, "mean": None, "min": None,
                                         "max": None, "spread": None,
                                         "stable": False}, \
        ("a metric with no data anywhere has no statistics at all — not a "
         "flattering 0.0 and not a stable zero: %r"
         % (rolled["metrics"]["ghost"],))

    for name, verdict, mistake in (
        ("tight", "stable", "three cases inside MAX_SPREAD is stable"),
        ("edge", "stable", "a spread of exactly MAX_SPREAD is stable"),
        ("wide", "noisy", "a spread wider than MAX_SPREAD is noisy"),
        ("pair", "thin", "two cases is thin, not stable"),
        ("lonely", "thin", "one case is thin, not stable"),
        ("ghost", "missing", "a metric with no data is missing, not thin"),
        ("never_measured", "missing", "a metric with no entry at all is missing"),
    ):
        got = s.stability_verdict(rolled, name)
        assert got == verdict, \
            ("the verdict for %r must be %r — %s — got %r"
             % (name, verdict, mistake, got))

    # --- the statuses, and whose errors are whose --------------------------
    mixed = [
        _record("c1", 0, metrics={"em": 1.0},
                metric_errors={"f1": "ValueError: boom"}),
        _record("c1", 1, metrics={}, metric_errors={"em": "TypeError: nah"}),
        _record("c2", 0, status="no_answer", metrics={}),
        _record("c3", 0, status="solver_error", metrics={}, note="RuntimeError: x"),
        _record("c4", 0, status="timeout", metrics={}, note="took 12 ticks of 3"),
        _record("c5", 0, status="case_error", metrics={}, note="case 'c5': prompt"),
        _record("c5", 1, metrics={"em": 0.0}),
    ]
    run = s.aggregate(mixed)
    assert run["records"] == 7 and run["cases"] == 5, \
        ("7 records over 5 distinct cases: records=%r, cases=%r"
         % (run["records"], run["cases"]))
    assert run["status_counts"] == {"ok": 3, "no_answer": 1, "solver_error": 1,
                                    "timeout": 1, "case_error": 1}, \
        ("`status_counts` counts every record by its status, with the absent "
         "statuses zero-filled: %r" % (run["status_counts"],))
    assert set(run["status_counts"]) == set(STATUSES), \
        ("the zero-fill is the whole status vocabulary, got %r"
         % (sorted(run["status_counts"]),))
    assert run["case_errors"] == 1, \
        ("`case_errors` counts OUR bug (status `case_error`) — 1 here — not the "
         "records whose metric plugin raised (2 of them): got %r"
         % (run["case_errors"],))
    assert run["metrics"]["em"]["n"] == 2, \
        ("only records that carry a value feed the metric: `em` has 2 cases, "
         "got %r" % (run["metrics"]["em"]["n"],))

    empty = s.aggregate([])
    assert empty == {"records": 0, "cases": 0,
                     "status_counts": {status: 0 for status in STATUSES},
                     "metrics": {}, "case_errors": 0}, \
        ("an empty run measures nothing, and it must invent neither a metric nor "
         "a case: %r" % (empty,))
    assert s.stability_verdict(empty, "em") == "missing", \
        "nothing measured is missing, not stable and not zero"

    print("check_05: the case is the unit, a weight is applied once, a `None` is "
          "not a zero, the spread decides `noisy` only with enough cases, and a "
          "missing metric stays missing — all asserted (7 verdicts, 6 statuses)")

def check_6():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        from lab import ConfigError
        try:
            fn(*args, **kwargs)
        except ConfigError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    class _Case:
        """A case bag: the check for stage 6 must not import stage 1 to build one."""

        def __init__(self, id, prompt, answer, weight=1.0, max_ticks=10, repeats=1, tags=()):
            self.id = id
            self.prompt = prompt
            self.answer = answer
            self.weight = weight
            self.max_ticks = max_ticks
            self.repeats = repeats
            self.tags = tuple(tags)

    class _Scripted:
        """A judge with a scripted reply; it counts calls like `lab`'s actors do."""

        def __init__(self, fn):
            self._fn = fn
            self.clock = None
            self.calls = 0

        def __call__(self, *, prompt, answer, reference, clock=None):
            self.calls += 1
            return self._fn(prompt=prompt, answer=answer, reference=reference,
                            call=self.calls)

    from lab import (JUDGE_TICKS, Ticker, bad_shape_judge, exact_judge,
                     order_sensitive_judge, substring_judge, sulking_judge,
                     unclear_judge)
    import stage_06 as s

    # --- the vocabulary, and what a verdict is worth ------------------------
    assert tuple(s.JUDGE_VERDICTS) == ("correct", "incorrect", "unclear"), \
        "the vocabulary is these three words, not %r" % (s.JUDGE_VERDICTS,)
    assert s.judge_score("correct") == 1.0, "a correct verdict scores 1.0"
    assert s.judge_score("incorrect") == 0.0, "an incorrect verdict scores 0.0"
    assert s.judge_score("unclear") is None, \
        ("an unclear judgement is not a wrong answer: judge_score('unclear') must be None "
         "('not applicable'), not %r — scoring it as failure publishes the judge's "
         "hesitation as the model's mistake" % (s.judge_score("unclear"),))
    message = _refused(s.judge_score, "maybe")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        "a verdict outside the vocabulary is refused, got %r" % (message,)

    # --- a reply is a verdict, a reason, and nothing else -------------------
    good = s.check_verdict({"verdict": "correct", "reason": "exact match"})
    assert good == {"verdict": "correct", "reason": "exact match"}, \
        "a well-formed reply survives validation, got %r" % (good,)
    for reply, why in (
        (None, "a reply that is not a mapping"),
        ("correct", "a reply that is a bare string"),
        ({"reason": "no verdict"}, "a reply without a verdict"),
        ({"verdict": "maybe", "reason": "?"}, "a verdict outside the vocabulary"),
        ({"verdict": "correct"}, "a verdict without a reason"),
        ({"verdict": "correct", "reason": 5}, "a reason that is not a string"),
    ):
        message = _refused(s.check_verdict, reply)
        assert message is not None and not message.startswith("WRONG TYPE"), \
            "%s is a bad shape and is refused, got %r" % (why, message)
    message = _refused(s.check_verdict, {"verdict": "maybe", "reason": "?"})
    assert "maybe" in message, \
        "the refusal names the verdict it did not understand, got %r" % (message,)

    # --- the cache belongs to the session and to the question ---------------
    judge = exact_judge(clock=Ticker())
    session = s.JudgeSession(judge)
    metric = s.judge_metric(session)
    case = _Case("a", "2+3?", "5")
    first, second = metric(case, "5"), metric(case, "5")
    assert (first, second) == (1.0, 1.0), \
        "a correct answer is judged correct twice: %r" % ((first, second),)
    assert judge.calls == 1, \
        ("the same question asked twice is ONE invocation of the judge, got %d: the cache "
         "exists so that a repeated question costs nothing" % (judge.calls,))
    assert (session.calls, session.asks) == (1, 2), \
        ("a hit does not call the judge but is still a question asked: expected calls=1 "
         "asks=2, got calls=%d asks=%d" % (session.calls, session.asks))

    ticker = Ticker()
    session = s.JudgeSession(exact_judge(), clock=ticker)
    session.ask(prompt="p", answer="5", reference="5")
    session.ask(prompt="p", answer="5", reference="5")
    assert ticker.now() == JUDGE_TICKS, \
        ("the session hands its clock to the judge, and the hit does not tick it again: "
         "expected %d tick(s) after one invocation and one hit, got %d"
         % (JUDGE_TICKS, ticker.now()))

    judge = exact_judge(clock=Ticker())
    metric = s.judge_metric(s.JudgeSession(judge))
    right = metric(_Case("a", "p", "5"), "5")
    wrong = metric(_Case("b", "p", "7"), "5")
    assert (right, wrong) == (1.0, 0.0), \
        ("the cache key carries the reference: the same candidate answer judged against a "
         "different reference is a different question, got %r then %r — a key of the answer "
         "alone serves the first case's verdict for the second" % (right, wrong))
    assert judge.calls == 2, \
        "two different questions are two invocations, got %d" % (judge.calls,)

    def by_prompt(*, prompt, answer, reference, call):
        return {"verdict": "correct" if prompt == "p1" else "incorrect", "reason": prompt}

    judge = _Scripted(by_prompt)
    metric = s.judge_metric(s.JudgeSession(judge))
    first = metric(_Case("a", "p1", "x"), "x")
    second = metric(_Case("b", "p2", "x"), "x")
    assert (first, second) == (1.0, 0.0), \
        ("the cache key carries the prompt: two questions with the same answer and reference "
         "but different prompts are different questions, got %r then %r" % (first, second))

    judge = exact_judge(clock=Ticker())
    one = s.JudgeSession(judge)
    two = s.JudgeSession(judge)
    one.ask(prompt="p", answer="5", reference="5")
    two.ask(prompt="p", answer="5", reference="5")
    assert judge.calls == 2, \
        ("a session is a run: a second session must ask the judge again, got %d invocation(s) "
         "— a cache at module level leaks one run's verdicts into the next" % (judge.calls,))
    assert (two.calls, two.asks) == (1, 1), \
        "the new session counts its own call: calls=%d asks=%d" % (two.calls, two.asks)

    # --- the budget: a hit spends nothing, a miss is the only cost ----------
    judge = exact_judge(clock=Ticker())
    session = s.JudgeSession(judge, max_calls=1)
    session.ask(prompt="p", answer="5", reference="5")
    message = _refused(session.ask, prompt="q", answer="9", reference="9")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        "over max_calls the session refuses to ask, got %r" % (message,)
    assert "max_calls" in message, \
        "the refusal names the budget it exhausted, got %r" % (message,)
    again = session.ask(prompt="p", answer="5", reference="5")
    assert again["verdict"] == "correct", \
        "a hit does not spend the budget: the cached verdict is still served"
    assert (session.calls, judge.calls) == (1, 1), \
        ("one call was spent and the refusals never reached the judge: calls=%d "
         "judge.calls=%d" % (session.calls, judge.calls))
    assert session.asks == 3, \
        ("asks counts every question the framework asked — the first, the refused one and "
         "the hit: expected 3, got %d" % (session.asks,))

    session = s.JudgeSession(exact_judge(clock=Ticker()), max_calls=2)
    session.ask(prompt="p1", answer="1", reference="1")
    session.ask(prompt="p2", answer="2", reference="2")
    assert session.calls == 2, \
        ("max_calls=2 permits exactly two invocations, got %d: a budget that stops one call "
         "early is a budget that cannot be spent" % (session.calls,))
    assert _refused(session.ask, prompt="p3", answer="3", reference="3") is not None, \
        "max_calls=2 is exhausted by the third question"

    session = s.JudgeSession(exact_judge(clock=Ticker()))
    for index in range(5):
        session.ask(prompt="p%d" % index, answer="a", reference="a")
    assert (session.calls, session.asks) == (5, 5), \
        ("max_calls=None is no budget at all, got calls=%d asks=%d"
         % (session.calls, session.asks))

    for bad in (True, 0, -1, "3", 2.5):
        assert _refused(s.JudgeSession, exact_judge(clock=Ticker()), max_calls=bad) is not None, \
            "max_calls=%r is not a budget a session can honour" % (bad,)

    # --- a broken judge aborts the measurement ------------------------------
    judge = sulking_judge(clock=Ticker())
    session = s.JudgeSession(judge)
    message = _refused(session.ask, prompt="p", answer="5", reference="5")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        ("a judge that raises makes the ask raise ConfigError instead of inventing a verdict, "
         "got %r" % (message,))
    assert "RuntimeError" in message, \
        "the refusal names what the judge did, got %r" % (message,)
    assert (session.calls, judge.calls) == (1, 1), \
        ("the invocation happened even though it failed: calls=%d judge.calls=%d"
         % (session.calls, judge.calls))

    metric = s.judge_metric(s.JudgeSession(sulking_judge(clock=Ticker())))
    message = _refused(metric, _Case("a", "p", "5"), "5")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        ("a metric over a broken judge raises: it must not score the answer 0.0, because a "
         "judge that is down would then be published as a model failure — got %r" % (message,))

    for reply, why in (
        ({"verdict": "maybe", "confidence": 0.9}, "a verdict outside the vocabulary"),
        ({"verdict": "correct"}, "a verdict without a reason"),
        ({"verdict": "correct", "reason": None}, "a null reason"),
        (["correct"], "a reply that is not a mapping"),
    ):
        session = s.JudgeSession(_Scripted(lambda *, reply=reply, **_: reply))
        message = _refused(session.ask, prompt="p", answer="5", reference="5")
        assert message is not None and not message.startswith("WRONG TYPE"), \
            "%s reaches the session as a broken judge, got %r" % (why, message)
    session = s.JudgeSession(bad_shape_judge(clock=Ticker()))
    message = _refused(session.ask, prompt="p", answer="5", reference="5")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        ("`lab.bad_shape_judge` answers 'maybe' with a confidence score: the session refuses "
         "it rather than caching it, got %r" % (message,))
    assert "maybe" in message, \
        "the refusal names the offending verdict, got %r" % (message,)

    # --- what a metric does with a verdict ----------------------------------
    case = _Case("a", "2+3?", "5")
    metric = s.judge_metric(s.JudgeSession(exact_judge(clock=Ticker())))
    assert metric(case, "5") == 1.0, "a correct answer scores 1.0"
    assert metric(case, "6") == 0.0, "a wrong answer scores 0.0"
    assert metric(case, "") == 0.0, "an empty answer is judged, not skipped"
    metric = s.judge_metric(s.JudgeSession(substring_judge(clock=Ticker())))
    assert metric(_Case("a", "p", "the capital is Paris"), "Paris") == 1.0, \
        "the reference the judge sees is the case's declared answer"
    value = s.judge_metric(s.JudgeSession(unclear_judge(clock=Ticker())))(case, "5")
    assert value is None, \
        ("an unclear verdict is None, never 0.0: None shrinks the metric's n (not applicable), "
         "while 0.0 would file the judge's hesitation as a wrong answer — got %r" % (value,))

    # --- two orders, one measurement ----------------------------------------
    judge = order_sensitive_judge(clock=Ticker())
    value = s.pairwise_metric(s.JudgeSession(judge))(case, "6")
    assert value == 0.5, \
        ("a judge that rewards the first slot must come out at 0.5: asking once measures the "
         "slot instead of the answer, and calling the disagreement a win hands this judge a "
         "perfect score — got %r" % (value,))
    assert judge.calls == 2, \
        ("a pairwise measurement asks both orders, so the judge is invoked twice, got %d"
         % (judge.calls,))

    metric = s.pairwise_metric(s.JudgeSession(exact_judge(clock=Ticker())))
    assert metric(case, "5 ") == 1.0, "both orders judge a correct answer correct"
    assert metric(case, "6") == 0.0, "both orders judge a wrong answer incorrect"
    judge = unclear_judge(clock=Ticker())
    value = s.pairwise_metric(s.JudgeSession(judge))(case, "6")
    assert value is None, \
        "two unclear verdicts are None, not 0.0: got %r" % (value,)
    assert judge.calls == 2, \
        "both orders are asked even though neither decided, got %d" % (judge.calls,)

    def half_clear(*, prompt, answer, reference, call):
        verdict = "correct" if answer == "cand" else "unclear"
        return {"verdict": verdict, "reason": verdict}

    judge = _Scripted(half_clear)
    value = s.pairwise_metric(s.JudgeSession(judge))(_Case("a", "p", "ref"), "cand")
    assert value == 1.0, \
        ("one definite verdict beats one unclear, because the judge did decide once: "
         "'correct' and 'unclear' together are 1.0, not None — got %r" % (value,))
    assert judge.calls == 2, "both orders were asked, got %d" % (judge.calls,)

    def unclear_first(*, prompt, answer, reference, call):
        verdict = "correct" if answer == "ref" else "unclear"
        return {"verdict": verdict, "reason": verdict}

    value = s.pairwise_metric(s.JudgeSession(_Scripted(unclear_first)))(_Case("a", "p", "ref"),
                                                                       "cand")
    assert value == 1.0, \
        ("the definite verdict wins whichever order it arrived in: 'unclear' then 'correct' "
         "is 1.0, not None — got %r" % (value,))

    def half_wrong(*, prompt, answer, reference, call):
        verdict = "correct" if answer == "cand" else "incorrect"
        return {"verdict": verdict, "reason": verdict}

    value = s.pairwise_metric(s.JudgeSession(_Scripted(half_wrong)))(_Case("a", "p", "ref"), "cand")
    assert value == 0.5, \
        ("a disagreement between the two orders is a tie, never a win: got %r — rewarding it "
         "hands a position-biased judge a perfect score" % (value,))

    seen = []

    def recorder(*, prompt, answer, reference, call):
        seen.append((answer, reference))
        return {"verdict": "correct", "reason": "recorded"}

    s.pairwise_metric(s.JudgeSession(_Scripted(recorder)))(_Case("a", "p", "ref"), "cand")
    assert seen == [("cand", "ref"), ("ref", "cand")], \
        ("the two asks are the same question with the answers swapped, got %r — asking the "
         "same order twice is one call through the cache" % (seen,))

    metric = s.pairwise_metric(s.JudgeSession(sulking_judge(clock=Ticker())))
    message = _refused(metric, case, "5")
    assert message is not None and not message.startswith("WRONG TYPE"), \
        "a pairwise measurement over a broken judge raises, got %r" % (message,)

    print("check_06: a three-word vocabulary with unclear != wrong, a reply validated as "
          "(verdict, reason), a per-session cache keyed by prompt/answer/reference whose hits "
          "cost no budget, a journal of calls vs asks, a broken judge that aborts instead of "
          "scoring, and a pairwise metric that asks both orders and calls a disagreement a "
          "tie — all asserted")

def check_7():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        from lab import ConfigError
        try:
            fn(*args, **kwargs)
        except ConfigError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    def _record(case="a", repeat=0, status="ok", answer="5", metrics=None,
                metric_errors=None, ticks=4, calls=1, note=""):
        """A record in the shape stage 3 produces, built here by hand."""
        return {"case": case, "repeat": repeat, "status": status, "answer": answer,
                "metrics": dict(metrics or {}), "metric_errors": dict(metric_errors or {}),
                "ticks": ticks, "calls": calls, "note": note}

    def _slurp(path):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _names_the_line(message, path, number):
        """Whether a refusal names `number`, with the path kept out of the digits."""
        stripped = message.replace(path, "")
        return re.search(r"(?<!\d)%d(?!\d)" % (number,), stripped) is not None

    def _check_canonical(s, work):
        record = _record(metrics={"em": 0.3})
        text = s.canonical(record)
        expected = ('{"answer":"5","calls":1,"case":"a","metric_errors":{},'
                    '"metrics":{"em":0.3},"note":"","repeat":0,"status":"ok","ticks":4}')
        assert text == expected, \
            ("canonical() is the record with sorted keys and no whitespace around the separators: "
             "got %r, expected %r" % (text, expected))
        assert "\n" not in text and text.strip() == text, \
            "canonical() is one line without surrounding whitespace: %r" % (text,)
        assert s.record_line(record) == text + "\n", \
            ("record_line() is the canonical line plus exactly one terminator: got %r"
             % (s.record_line(record),))

        drift = _record(metrics={"em": 0.1 + 0.2})
        exact = _record(metrics={"em": 0.3})
        assert s.canonical(drift) == s.canonical(exact), \
            ("metric values are rounded before they are written: 0.1 + 0.2 and 0.3 are the same "
             "measurement, and an unrounded float makes two runs differ in bytes (%r vs %r)"
             % (s.canonical(drift), s.canonical(exact)))
        long_value = _record(metrics={"em": 0.123456789})
        assert '"em":0.123457' in s.canonical(long_value), \
            ("a metric value keeps METRIC_DP=6 decimal places in the log: got %r"
             % (s.canonical(long_value),))
        absent = _record(metrics={"em": None})
        assert '"em":null' in s.canonical(absent), \
            ("a metric that was not applicable stays a key with a null value, it is not dropped: "
             "got %r" % (s.canonical(absent),))

        accented = _record(answer="caf\u00e9 \u2713")
        escaped = s.canonical(accented)
        assert escaped.isascii(), \
            ("the log is written in ASCII: a non-ASCII answer must be escaped, or two runs that "
             "measured the same thing can compare unequal over an encoding; got %r" % (escaped,))
        assert json.loads(escaped)["answer"] == "caf\u00e9 \u2713", \
            "the escaped answer round-trips through json.loads: got %r" % (json.loads(escaped),)

        try:
            laundered = s.canonical({"metrics": {}, "note": object()})
        except TypeError:
            laundered = None
        assert laundered is None, \
            ("a record that JSON cannot write must raise, not be stringified: default=str writes an "
             "object's address into a field the analysis reads as a name, and the address differs "
             "between runs; got %r" % (laundered,))

        kept = _record(metrics={"em": 0.123456789})
        s.canonical(kept)
        assert kept["metrics"] == {"em": 0.123456789}, \
            ("canonical() rounds a copy and never the record handed in: the caller may still need "
             "the measurement it took; got %r" % (kept["metrics"],))

    def _check_log(s, work):
        path = os.path.join(work, "run.jsonl")
        log = s.RunLog(path)
        assert log.path == path, \
            "a log remembers the path it was built with: got %r, expected %r" % (log.path, path)

        first = _record(case="a", repeat=0, metrics={"em": 0.5})
        log.append(first)
        content = _slurp(path)
        assert content == s.canonical(first) + "\n", \
            ("append() writes the canonical line and one terminator, nothing else: got %r"
             % (content,))
        assert content.endswith("\n") and content.count("\n") == 1, \
            ("a record is one line with exactly one terminator, so a reader can tell a cut write "
             "from a complete one: got %r" % (content,))

        second = _record(case="b", repeat=0, status="no_answer", answer=None, metrics={}, ticks=2)
        log.append(second)
        assert _slurp(path).splitlines() == [s.canonical(first), s.canonical(second)], \
            ("appends accumulate in order: got %r" % (_slurp(path),))

        third = _record(case="b", repeat=1, metrics={"em": 0.25})
        s.RunLog(path).append(third)
        records = s.read_records(path)
        assert len(records) == 3, \
            ("a log is appended to, never truncated: a new RunLog over an existing log keeps the "
             "records already there; got %r" % (records,))

        nested = os.path.join(work, "deep", "nested", "log.jsonl")
        s.RunLog(nested).append(first)
        assert os.path.isfile(nested), \
            "append() creates the parent directory: a log may live in a directory the run owns"

        for rec in records:
            assert isinstance(rec, dict), \
                "read_records() returns records (dicts), not the lines it read: got %r" % (rec,)
        assert records[0] == first and records[1] == second and records[2] == third, \
            ("the records survive the round trip unchanged: got %r" % (records,))

        one = os.path.join(work, "one.jsonl")
        two = os.path.join(work, "two.jsonl")
        for where in (one, two):
            other = s.RunLog(where)
            other.append(_record(metrics={"em": 0.1 + 0.2}))
            other.append(_record(case="b", repeat=1, metrics={"em": 0.0}))
        with open(one, "rb") as left, open(two, "rb") as right:
            bytes_one, bytes_two = left.read(), right.read()
        assert bytes_one == bytes_two and bytes_one.count(b"\n") == 2, \
            ("two runs that measured the same thing share the log's bytes: got %r vs %r"
             % (bytes_one, bytes_two))

    def _check_reader(s, work):
        first = _record(case="a", repeat=0, metrics={"em": 0.5})
        second = _record(case="b", repeat=0, status="no_answer", answer=None, metrics={}, ticks=2)
        good_line = s.canonical(first) + "\n"

        missing = os.path.join(work, "nothing-here.jsonl")
        assert s.read_records(missing) == [], \
            "a log that does not exist is an empty log, not an error"
        assert s.read_records(missing, tolerant=True) == [], \
            "a missing log is an empty log for the tolerant reader too"

        damaged = os.path.join(work, "damaged.jsonl")
        with open(damaged, "w", encoding="utf-8") as handle:
            handle.write(good_line)
            handle.write(good_line)
            handle.write("{not json\n")
            handle.write(good_line)
        message = _refused(s.read_records, damaged)
        assert message is not None and not message.startswith("WRONG TYPE"), \
            ("a line that is not a JSON object is refused with a ConfigError: got %r" % (message,))
        assert _names_the_line(message, damaged, 3), \
            ("the refusal names the line number of the bad line (line 3), so a damaged log can be "
             "found rather than guessed at; got %r" % (message,))
        tolerant_message = _refused(s.read_records, damaged, tolerant=True)
        assert tolerant_message is not None, \
            ("tolerant=True forgives only an unterminated FINAL line: a bad line in the middle is "
             "corruption, and skipping it would silently shorten the run")

        first_bad = os.path.join(work, "first-bad.jsonl")
        with open(first_bad, "w", encoding="utf-8") as handle:
            handle.write("oops\n")
            handle.write(good_line)
        message = _refused(s.read_records, first_bad)
        assert message is not None, "a bad first line is refused with a ConfigError"
        assert _names_the_line(message, first_bad, 1), \
            ("the refusal names the FIRST line as line 1: lines are numbered from one, not from "
             "zero; got %r" % (message,))

        shaped = os.path.join(work, "shaped.jsonl")
        with open(shaped, "w", encoding="utf-8") as handle:
            handle.write(good_line)
            handle.write('["not", "an", "object"]\n')
        message = _refused(s.read_records, shaped)
        assert message is not None, \
            ("a line that is valid JSON but not an object is not a record: it is refused, not "
             "handed back as a list")
        assert _names_the_line(message, shaped, 2), \
            "the refusal names line 2: got %r" % (message,)

        truncated = os.path.join(work, "truncated.jsonl")
        with open(truncated, "w", encoding="utf-8") as handle:
            handle.write(good_line)
            handle.write(s.canonical(second)[:12])          # cut mid-record, no terminator
        assert _refused(s.read_records, truncated) is not None, \
            ("a truncated final line is a bad line for the strict reader: only tolerant=True "
             "forgives the incomplete write")
        assert s.read_records(truncated, tolerant=True) == [first], \
            ("tolerant=True drops the unterminated final line and keeps every complete record: "
             "got %r" % (s.read_records(truncated, tolerant=True),))

        terminated = os.path.join(work, "terminated.jsonl")
        with open(terminated, "w", encoding="utf-8") as handle:
            handle.write(good_line)
            handle.write("not json\n")
        assert _refused(s.read_records, terminated, tolerant=True) is not None, \
            ("tolerant=True drops only an UNTERMINATED final line: a final line that ends in a "
             "newline was written as a complete record, so it is corruption and still raises")

        unterminated = os.path.join(work, "unterminated.jsonl")
        with open(unterminated, "w", encoding="utf-8") as handle:
            handle.write(good_line)
            handle.write(s.canonical(second))               # a complete record, no final newline
        assert s.read_records(unterminated) == [first, second], \
            ("a complete record is read even without its terminator: the strict reader keeps every "
             "line of the file; got %r" % (s.read_records(unterminated),))
        assert s.read_records(unterminated, tolerant=True) == [first, second], \
            ("tolerant=True drops the final line only when it is an incomplete write, and this one "
             "is a whole record; got %r" % (s.read_records(unterminated, tolerant=True),))

    from lab import ConfigError                    # noqa: F401  (the refusal type)
    import stage_07 as s

    work = tempfile.mkdtemp(prefix="f2-stage07-")
    try:
        _check_canonical(s, work)
        _check_log(s, work)
        _check_reader(s, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("check_07: sorted keys, rounding that kills float drift, ASCII escapes, no "
          "default=str, a flush a reader can see, exactly one terminator, a created "
          "directory, and a reader that names a bad line while forgiving only an "
          "unterminated final one — all asserted")

def check_8():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """The refusal message when a call is refused, or None when it is not.

        A refusal that arrives as anything but `ConfigError` is reported as a WRONG
        TYPE line rather than escaping, so a caller can tell "refused" from "crashed"
        and name the mistake instead of printing a traceback.
        """
        from lab import ConfigError
        try:
            fn(*args, **kwargs)
        except ConfigError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    from lab import ConfigError
    from stage_05 import MAX_SPREAD, MIN_N
    import stage_08 as s

    # ---------------------------------------------------------------- surface ---
    assert s.GATE_KEYS == ("metric", "min_mean", "max_mean"), (
        "a gate carries the metric and the two possible bounds, under exactly "
        "these names: a gate read as `{\"metric\": ..., \"min\": ...}` is a gate "
        "whose bound nobody enforces, got %r" % (s.GATE_KEYS,))
    assert (s.EXIT_OK, s.EXIT_GATE_FAILED, s.EXIT_RUN_INVALID, s.EXIT_CONFIG) == (0, 1, 2, 3), (
        "the exit statuses are the contract's four distinct numbers in this order "
        "— 0 ok, 1 a gate refused a valid run, 2 the run is not a valid measurement, "
        "3 the run never happened. A caller (CI, the CLI, the resume) reads the "
        "number, so a config error reported as 1 and a gate failure reported as 0 "
        "are both silent lies, got %r"
        % ((s.EXIT_OK, s.EXIT_GATE_FAILED, s.EXIT_RUN_INVALID, s.EXIT_CONFIG),))
    assert (MIN_N, MAX_SPREAD) == (3, 0.35), (
        "stage 5's frozen constants are MIN_N = 3 and MAX_SPREAD = 0.35; the gate "
        "reads them, so a check that measured the boundary against anything else "
        "would be measuring the wrong gate, got %r" % ((MIN_N, MAX_SPREAD),))

    # ------------------------------------------------------------- fixtures ----
    def _entry(n, mean, spread=0.0, stable=True):
        """One metric's row in a stage 5 aggregate, built by hand."""
        return {"n": n, "mean": mean, "min": mean, "max": mean, "spread": spread,
                "stable": stable}

    def _agg(metrics):
        """A stage 5 aggregate whose only interesting part is `metrics`."""
        return {"records": 4, "cases": 2, "case_errors": 0,
                "status_counts": {status: 0 for status in
                                  ("ok", "no_answer", "solver_error", "timeout",
                                   "case_error")},
                "metrics": metrics}

    # The one healthy metric: five cases (>= MIN_N), a mean of 0.75, a spread of
    # 0.1 (<= MAX_SPREAD), stable.
    healthy = _agg({"em": _entry(5, 0.75, spread=0.10, stable=True),
                    "tokens": _entry(4, 12.0, spread=0.0, stable=True)})
    min_gate = s.parse_gate({"metric": "em", "min_mean": 0.5})
    max_gate = s.parse_gate({"metric": "em", "max_mean": 0.5})

    # ------------------------------------------------------------ parse_gate ---
    parsed = s.parse_gate({"metric": "em", "min_mean": 0.5})
    assert parsed == {"metric": "em", "min_mean": 0.5}, (
        "a parsed gate is the metric plus its ONE bound under the contract's key, "
        "got %r" % (parsed,))
    parsed_upper = s.parse_gate({"metric": "tokens", "max_mean": 20})
    assert (parsed_upper["metric"], parsed_upper["max_mean"]) == ("tokens", 20.0), (
        "a lower-is-better gate keeps `max_mean` (as a real number), got %r"
        % (parsed_upper,))

    refusals = (
        ({"metric": "em", "min_mean": 0.5, "minimum": 0.4},
         "a typo'd key (`minimum`) instead of `min_mean`"),
        ({"metric": "em", "min_mean": 0.5, "weight": 1.0},
         "an unknown key (`weight`) in a gate"),
        ({"metric": "em"}, "a gate with no bound at all (it cannot fail)"),
        ({"metric": "em", "min_mean": 0.5, "max_mean": 0.5},
         "a gate with BOTH bounds (which way is better?)"),
        ({"min_mean": 0.5}, "a gate with no metric"),
        ({"metric": "", "min_mean": 0.5}, "an empty metric name"),
        ({"metric": 7, "min_mean": 0.5}, "a numeric metric name"),
        ({"metric": True, "min_mean": 0.5}, "a boolean metric name"),
        ({"metric": "em", "min_mean": "0.5"}, "a bound written as a string"),
        ({"metric": "em", "min_mean": True}, "a boolean bound (True == 1)"),
        ({"metric": "em", "min_mean": float("nan")},
         "a nan bound (every comparison against it is False)"),
        ({"metric": "em", "min_mean": float("inf")}, "an infinite bound"),
        (["metric", "em"], "a gate that is not a mapping"),
    )
    for spec, why in refusals:
        message = _refused(s.parse_gate, spec)
        assert message is not None, (
            "%s is refused, not silently ignored: a gate nobody validated is a gate "
            "that means something other than what its author wrote" % (why,))
        assert not message.startswith("WRONG TYPE"), (
            "%s is refused with the framework's own ConfigError, not with a crash "
            "from inside: %s" % (why, message))
    message = _refused(s.parse_gate, {"metric": "em", "min_mean": 0.5, "minimum": 0.4})
    assert "minimum" in message, (
        "the refusal NAMES the offending key: an unknown key silently dropped would "
        "leave a gate whose only remembered bound is not the one that was typed, "
        "got %r" % (message,))

    # --------------------------------------------------------- evaluate_gate ---
    verdict = s.evaluate_gate(min_gate, healthy)
    assert set(verdict) == {"ok", "value", "reason"}, (
        "a verdict is exactly {ok, value, reason}, got %r" % (sorted(verdict),))
    assert (verdict["ok"], verdict["value"], verdict["reason"]) == (True, 0.75, "ok"), (
        "a mean of 0.75 clears min_mean 0.5, and `value` is the METRIC'S mean "
        "(0.75) rather than the bound it was compared against (0.5): got %r"
        % (verdict,))
    at_min = s.evaluate_gate(min_gate, _agg({"em": _entry(5, 0.5, spread=0.10, stable=True)}))
    assert (at_min["ok"], at_min["reason"]) == (True, "ok"), (
        "the bound is INCLUSIVE: a mean of exactly 0.5 clears min_mean 0.5, because "
        "a threshold is the value its author wrote down (a `>` would refuse it), got "
        "%r" % (at_min,))
    below = s.evaluate_gate(min_gate, _agg({"em": _entry(5, 0.49, spread=0.10, stable=True)}))
    assert (below["ok"], below["value"], below["reason"]) == (False, 0.49, "below"), (
        "a mean of 0.49 against min_mean 0.5 is `below`, and the verdict still "
        "reports the mean it judged (0.49), got %r" % (below,))

    over = s.evaluate_gate(max_gate, healthy)
    assert (over["ok"], over["value"], over["reason"]) == (False, 0.75, "above"), (
        "a lower-is-better gate refuses a mean ABOVE its max_mean: an implementation "
        "that only knows how to check a minimum would read 0.75 against max_mean 0.5 "
        "as a pass, got %r" % (over,))
    under = s.evaluate_gate(max_gate, _agg({"em": _entry(5, 0.25, spread=0.10, stable=True)}))
    assert (under["ok"], under["reason"]) == (True, "ok"), (
        "0.25 is at most max_mean 0.5: a higher-is-better comparison read backwards "
        "would call it `above`, got %r" % (under,))
    at_max = s.evaluate_gate(max_gate, _agg({"em": _entry(5, 0.5, spread=0.10, stable=True)}))
    assert (at_max["ok"], at_max["reason"]) == (True, "ok"), (
        "the bound is inclusive at the top too: a mean of exactly max_mean 0.5 "
        "passes, got %r" % (at_max,))

    absent = s.evaluate_gate(min_gate, _agg({"tokens": _entry(4, 12.0)}))
    assert (absent["ok"], absent["value"], absent["reason"]) == (False, None, "missing"), (
        "a metric the aggregate never measured is a `missing` verdict with value "
        "None — not a KeyError and not a pass: got %r" % (absent,))
    empty = s.evaluate_gate(min_gate, _agg({"em": _entry(0, None, spread=None, stable=False)}))
    assert (empty["ok"], empty["value"], empty["reason"]) == (False, None, "missing"), (
        "a metric with n == 0 has no mean to judge: `missing`, never a pass and "
        "never `thin` (a metric with no data is not a small sample): got %r" % (empty,))

    thin = s.evaluate_gate(min_gate,
                           _agg({"em": _entry(MIN_N - 1, 0.75, spread=0.10, stable=False)}))
    assert (thin["ok"], thin["value"], thin["reason"]) == (False, 0.75, "thin"), (
        "a mean over %d cases (MIN_N is %d) does not clear a gate: `thin`, and the "
        "verdict still reports the mean it refused: got %r" % (MIN_N - 1, MIN_N, thin))
    thin_smug = s.evaluate_gate(min_gate,
                                _agg({"em": _entry(MIN_N - 1, 0.75, spread=0.10, stable=True)}))
    assert (thin_smug["ok"], thin_smug["reason"]) == (False, "thin"), (
        "the COUNT is judged before the spread and the flag: a thin metric cannot "
        "gate even when its entry calls itself stable, got %r" % (thin_smug,))

    noisy = s.evaluate_gate(min_gate,
                            _agg({"em": _entry(5, 0.75, spread=MAX_SPREAD + 0.01,
                                               stable=False)}))
    assert (noisy["ok"], noisy["value"], noisy["reason"]) == (False, 0.75, "noisy"), (
        "a metric whose cases spread further than MAX_SPREAD (%r) is not one number: "
        "`noisy`, not a bound comparison, got %r" % (MAX_SPREAD, noisy))
    edge = s.evaluate_gate(min_gate,
                           _agg({"em": _entry(5, 0.75, spread=MAX_SPREAD, stable=True)}))
    assert (edge["ok"], edge["reason"]) == (True, "ok"), (
        "the spread bound is inclusive like the mean bound: a spread of exactly "
        "MAX_SPREAD (%r) is not noise, got %r" % (MAX_SPREAD, edge))
    noisy_smug = s.evaluate_gate(min_gate,
                                 _agg({"em": _entry(5, 0.75, spread=MAX_SPREAD + 0.01,
                                                    stable=True)}))
    assert (noisy_smug["ok"], noisy_smug["reason"]) == (False, "noisy"), (
        "the spread is judged before the entry's own flag: a wide metric cannot gate "
        "by calling itself stable, got %r" % (noisy_smug,))

    unstable = s.evaluate_gate(min_gate,
                               _agg({"em": _entry(5, 0.75, spread=0.10, stable=False)}))
    assert (unstable["ok"], unstable["value"], unstable["reason"]) == (False, 0.75, "unstable"), (
        "an entry that is neither thin nor noisy on its own numbers but whose "
        "`stable` is falsy does not gate, and the verdict still reports the mean: "
        "got %r" % (unstable,))

    assert _refused(s.evaluate_gate, {"metric": "em"}, healthy) is not None, (
        "a gate that carries no bound cannot fail, so it cannot be evaluated either: "
        "comparing against a bound that is not there must be a refusal rather than a "
        "pass")

    # -------------------------------------------------------- evaluate_gates ---
    none_at_all = s.evaluate_gates([], healthy)
    assert none_at_all == {"ok": False, "gates": (), "reason": "no_gates"}, (
        "an empty gate list is NOT a pass: 'nothing was checked' is not the same "
        "sentence as 'everything passed', and a config that drops the gates must not "
        "be the cheapest road to a green run, got %r" % (none_at_all,))
    assert s.evaluate_gates((), healthy)["ok"] is False, (
        "an empty TUPLE of gates is exactly as empty as an empty list")

    passing = [s.parse_gate({"metric": "em", "min_mean": 0.5}),
               s.parse_gate({"metric": "tokens", "max_mean": 20.0})]
    green = s.evaluate_gates(passing, healthy)
    assert set(green) == {"ok", "gates"}, (
        "a gate result is exactly {ok, gates} — the reason for a refusal lives in "
        "each verdict, got %r" % (sorted(green),))
    assert green["ok"] is True, (
        "every gate cleared: 0.75 >= 0.5 and 12.0 <= 20.0, got %r" % (green,))
    assert isinstance(green["gates"], tuple) and len(green["gates"]) == 2, (
        "one verdict per gate, in the declared order, as a tuple: got %r"
        % (green["gates"],))

    mixed = s.evaluate_gates([passing[0], s.parse_gate({"metric": "em", "max_mean": 0.5})],
                             healthy)
    assert mixed["ok"] is False, (
        "ONE failing gate fails the run: 0.75 against max_mean 0.5 is `above` even "
        "though the first gate passed, got %r" % (mixed,))
    assert (mixed["gates"][0]["ok"], mixed["gates"][1]["reason"]) == (True, "above"), (
        "the verdicts keep the declared order and each carries its own reason, got %r"
        % (mixed["gates"],))
    unknown = s.evaluate_gates([s.parse_gate({"metric": "bleu", "min_mean": 0.0})], healthy)
    assert (unknown["ok"], unknown["gates"][0]["reason"]) == (False, "missing"), (
        "a gate over a metric the aggregate never measured fails as `missing` rather "
        "than blowing up the run, got %r" % (unknown,))

    # ---------------------------------------------------------------- run_exit ---
    def _summary(stopped=None, case_errors=0, metric_errors=0, records=2):
        """Stage 4's run SUMMARY, built by hand: `records` and `metric_errors` are
        COUNTS, never logs. This is the shape stage 4 hands to `run_exit`."""
        counts = {status: 0 for status in
                  ("ok", "no_answer", "solver_error", "timeout", "case_error")}
        counts["case_error"] = case_errors
        counts["ok"] = max(records - case_errors, 0)
        return {"suite": "toy", "cases": 2, "records": records,
                "status_counts": counts, "metric_errors": metric_errors,
                "ticks": 0, "calls": records, "stopped": stopped}

    red = s.evaluate_gates([passing[0], s.parse_gate({"metric": "em", "max_mean": 0.5})],
                           healthy)
    clean = _summary()
    assert isinstance(clean["records"], int) and isinstance(clean["metric_errors"], int), (
        "the fixture must be what stage 4 produces: a summary COUNTS its records and "
        "its metric failures, it does not carry the log, got %r" % (clean,))
    assert s.run_exit(None, green) == s.EXIT_CONFIG, (
        "a run that never happened is EXIT_CONFIG — not a gate failure, and certainly "
        "not a green run, got %r" % (s.run_exit(None, green),))
    assert s.run_exit({}, green) == s.EXIT_CONFIG, (
        "an empty dict is not a run either: EXIT_CONFIG")
    for missing in ("stopped", "metric_errors"):
        truncated = _summary()
        truncated.pop(missing)
        assert s.run_exit(truncated, green) == s.EXIT_CONFIG, (
            "a run summary that lacks even one of its keys (%r) is a run that never "
            "happened: EXIT_CONFIG, got %r" % (missing, s.run_exit(truncated, green)))

    assert s.run_exit(clean, green) == s.EXIT_OK, (
        "a valid run that cleared every gate is the only EXIT_OK there is, got %r"
        % (s.run_exit(clean, green),))
    assert s.run_exit(clean, red) == s.EXIT_GATE_FAILED, (
        "a valid run whose gate refused it is EXIT_GATE_FAILED, got %r"
        % (s.run_exit(clean, red),))
    assert s.run_exit(clean, s.evaluate_gates([], healthy)) == s.EXIT_GATE_FAILED, (
        "an unevaluated gate list (no_gates) is not a green light: a suite with no "
        "gates must not exit 0, got %r"
        % (s.run_exit(clean, s.evaluate_gates([], healthy)),))

    for stopped in ("calls", "ticks"):
        halted = _summary(stopped=stopped)
        assert s.run_exit(halted, green) == s.EXIT_RUN_INVALID, (
            "a run that stopped on its %s budget is not a valid measurement, however "
            "green its gate: EXIT_RUN_INVALID, never EXIT_OK and never a mere gate "
            "failure, got %r" % (stopped, s.run_exit(halted, green)))

    injured = _summary(case_errors=1)
    assert s.run_exit(injured, green) == s.EXIT_RUN_INVALID, (
        "a counted case_error is OUR bug, not the model's: the greenest gate must "
        "not publish a run that has one, got %r" % (s.run_exit(injured, green),))
    unmeasured = _summary(metric_errors=1)
    assert s.run_exit(unmeasured, green) == s.EXIT_RUN_INVALID, (
        "a counted metric failure means a record carries no measurement: a green "
        "gate over that run is exactly the accident the ordering exists to prevent, "
        "got %r" % (s.run_exit(unmeasured, green),))
    assert s.run_exit(_summary(metric_errors=3), green) == s.EXIT_RUN_INVALID, (
        "the count is a count: three metric failures invalidate the run exactly as "
        "one does, got %r" % (s.run_exit(_summary(metric_errors=3), green),))

    print("check_08: the gate (missing/thin/noisy/unstable judged before any bound, "
          "inclusive bounds in both directions), an empty gate list that is not a "
          "pass, and the exit status ordered config -> invalid -> gate — all asserted "
          "(%d gate specs refused, every verdict and every run classified by hand)"
          % (len(refusals),))

def check_9():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    STATUS_NAMES = ("ok", "no_answer", "solver_error", "timeout", "case_error")

    ROW_KEYS = {"base", "cand", "delta", "noise", "verdict"}

    def _metric(mean, spread, *, n=3, stable=True):
        """One metric entry of a stage 5 aggregation, hand-built in the frozen shape.

        `mean` and `spread` are binary fractions in every fixture below, so the
        differences the check asserts are exact and do not depend on float luck.
        """
        return {"n": n, "mean": mean, "min": mean - spread / 2.0, "max": mean + spread / 2.0,
                "spread": spread, "stable": stable}

    def _no_data():
        """A metric entry that never produced a value: `n == 0`, not a zero."""
        return {"n": 0, "mean": None, "min": None, "max": None, "spread": None, "stable": False}

    def _agg(metrics):
        """A stage 5 aggregation, hand-built: the five keys, the unit being the case."""
        return {"records": 9, "cases": 3,
                "status_counts": {name: 0 for name in STATUS_NAMES},
                "metrics": metrics, "case_errors": 0}

    import stage_09 as s

    # --- the slack is the resolution of the numbers -------------------------
    assert s.EPS == 10 ** -6, (
        "EPS is the resolution of the rounded metric values, 10 ** -METRIC_DP = 1e-6, "
        "not %r" % (s.EPS,))

    # --- a real gain and a real loss ---------------------------------------
    base = _agg({"em": _metric(0.5, 0.25), "f1": _metric(0.875, 0.125)})
    cand = _agg({"em": _metric(1.0, 0.25), "f1": _metric(0.5, 0.125)})
    diff = s.diff_metrics(base, cand)
    assert set(diff) == {"em", "f1"}, \
        "the diff covers every metric either side reports, got %r" % (sorted(diff),)
    row = diff["em"]
    assert set(row) == ROW_KEYS, (
        "a diff row carries exactly base/cand/delta/noise/verdict, no more and no less, "
        "got %r" % (sorted(row),))
    assert (row["base"], row["cand"]) == (0.5, 1.0), (
        "base and cand are the two means, got %r" % ((row["base"], row["cand"]),))
    assert row["delta"] == 0.5, (
        "delta is cand - base, so a gain is positive, got %r" % (row["delta"],))
    assert row["noise"] == 0.25, (
        "the noise is the LARGER of the two spreads (0.25 here), got %r" % (row["noise"],))
    assert row["verdict"] == "improvement", (
        "a gain bigger than the noise is an improvement, not a regression and not a "
        "stable reading, got %r" % (row["verdict"],))
    loss = diff["f1"]
    assert (loss["base"], loss["cand"]) == (0.875, 0.5), \
        "base is the baseline's mean and cand the candidate's, got %r" % ((loss["base"], loss["cand"]),)
    assert loss["delta"] == -0.375, (
        "delta is cand - base, so a loss is negative: the sign is not symmetric and not "
        "whatever makes the report read well, got %r" % (loss["delta"],))
    assert loss["noise"] == 0.125, \
        "the noise reads both sides' spreads, got %r" % (loss["noise"],)
    assert loss["verdict"] == "regression", (
        "a loss bigger than the noise is a regression, got %r" % (loss["verdict"],))
    assert s.regressions(diff) == ("f1",), (
        "regressions() is exactly the regression verdicts, sorted, got %r"
        % (s.regressions(diff),))
    assert isinstance(s.regressions(diff), tuple), \
        "regressions() returns a tuple, got %r" % (type(s.regressions(diff)).__name__,)

    # --- a difference the noise already explains is not a difference -------
    quiet = _agg({"em": _metric(0.5, 0.25)})
    nudged = _agg({"em": _metric(0.625, 0.25)})
    row = s.diff_metrics(quiet, nudged)["em"]
    assert (row["delta"], row["noise"]) == (0.125, 0.25), \
        "the fixture is a 0.125 move under a 0.25 noise, got %r" % (row,)
    assert row["verdict"] == "stable", (
        "a difference smaller than the noise is the noise, not an improvement: every run "
        "moves a little, and a report that always fires is a report nobody reads, got %r"
        % (row["verdict"],))

    # --- the boundary is strict, and the slack is real ---------------------
    slack = 2 ** -20                     # an exact binary eps, so the boundary is exact
    flat = _agg({"em": _metric(1.0, 0.25)})
    exactly = _agg({"em": _metric(1.0 + 0.25 + slack, 0.125)})
    row = s.diff_metrics(flat, exactly, eps=slack)["em"]
    assert (row["delta"], row["noise"]) == (0.25 + slack, 0.25), \
        "the fixture sits exactly at noise + eps, got %r" % (row,)
    assert row["verdict"] == "stable", (
        "the comparison is strict — a difference exactly at noise + eps is not BIGGER "
        "than the noise, got %r" % (row["verdict"],))
    past = _agg({"em": _metric(1.0 + 0.25 + 2 * slack, 0.125)})
    row = s.diff_metrics(flat, past, eps=slack)["em"]
    assert row["verdict"] == "improvement", (
        "carrying the slack must not swallow a difference one step past the boundary, got %r"
        % (row["verdict"],))

    # --- the noise is a spread, and the larger of the two ------------------
    jitter = _agg({"wide": _metric(0.25, 0.0), "mid": _metric(0.5, 0.0)})
    moved = _agg({"wide": _metric(0.875, 0.25), "mid": _metric(0.6875, 0.25)})
    diff = s.diff_metrics(jitter, moved)
    row = diff["wide"]
    assert row["noise"] == 0.25, \
        "the noise is the spread of the data, not the size of the means: got %r" % (row["noise"],)
    assert row["verdict"] == "improvement", (
        "a 0.625 move over a 0.25 spread is a gain: the noise must not be read off the "
        "means, which here are 0.25 and 0.875, got %r" % (row["verdict"],))
    row = diff["mid"]
    assert row["noise"] == 0.25, (
        "the noise is the LARGER spread of the two sides — 0.25 here, not the 0.0 of the "
        "quiet side and not the two sides' mean 0.125, got %r" % (row["noise"],))
    assert row["verdict"] == "stable", (
        "a 0.1875 move inside the jittery side's 0.25 spread is not a result: the noise "
        "taken from one side only, or averaged, invents an improvement, got %r"
        % (row["verdict"],))

    # --- a metric the candidate added is 'added', not a fabricated gain ----
    added = s.diff_metrics(_agg({}), _agg({"new": _metric(0.5, 0.125)}))
    assert set(added) == {"new"}, \
        "the diff walks both sides: a metric only the candidate reports is still news, got %r" \
        % (sorted(added),)
    new = added["new"]
    assert new["base"] is None and new["cand"] == 0.5, (
        "a side with no data is None, never a 0.0 that turns 'not measured' into 'measured "
        "zero', got %r" % (new,))
    assert new["delta"] is None, (
        "there is no delta without two numbers: a missing base must not be subtracted as "
        "0.0, which would fabricate a gain, got %r" % (new["delta"],))
    assert new["verdict"] == "added", (
        "a metric only the candidate measured is 'added' — not a regression, and not an "
        "improvement against a zero nobody measured, got %r" % (new["verdict"],))
    assert new["noise"] == 0.125, (
        "the noise comes from the sides that have data (0.125 here), got %r" % (new["noise"],))
    assert s.regressions(added) == (), (
        "a metric nobody measured on the baseline side is never a regression, got %r"
        % (s.regressions(added),))

    # --- a metric the candidate dropped is 'removed', not a regression ----
    removed = s.diff_metrics(_agg({"gone": _metric(0.75, 0.25)}), _agg({}))
    assert set(removed) == {"gone"}, \
        "a metric only the baseline reports is still news, got %r" % (sorted(removed),)
    gone = removed["gone"]
    assert gone["base"] == 0.75 and gone["cand"] is None, (
        "the absent candidate side is None, got %r" % (gone,))
    assert gone["delta"] is None, (
        "there is no delta without two numbers: a metric that disappeared has no delta, got %r"
        % (gone["delta"],))
    assert gone["verdict"] == "removed", (
        "a metric the candidate stopped measuring is 'removed'; only a measurement can "
        "regress, got %r" % (gone["verdict"],))
    assert gone["noise"] == 0.25, (
        "the noise comes from the sides that have data (0.25 here), got %r" % (gone["noise"],))
    assert s.regressions(removed) == (), (
        "a metric nobody measured on the candidate side is never a regression, got %r"
        % (s.regressions(removed),))

    # --- an unstable side refuses the verdict ------------------------------
    shaky = _agg({"thin": _metric(0.5, 0.0, n=1, stable=False)})
    shakier = _agg({"thin": _metric(1.0, 0.0, n=1, stable=False)})
    diff = s.diff_metrics(shaky, shakier)
    row = diff["thin"]
    assert row["delta"] == 0.5, \
        "a delta exists whenever both sides have a number, got %r" % (row["delta"],)
    assert row["verdict"] == "unstable", (
        "both sides have data but neither is stable: the diff refuses a verdict instead of "
        "reporting the 0.5 as a gain, got %r" % (row["verdict"],))
    assert s.regressions(diff) == (), (
        "an unstable comparison is not a regression, got %r" % (s.regressions(diff),))

    # --- a side that never produced a value is not a side with a value -----
    hollow = s.diff_metrics(_agg({"empty": _no_data()}), _agg({"empty": _metric(0.5, 0.25)}))
    row = hollow["empty"]
    assert row["base"] is None, (
        "an entry with n == 0 has no mean to compare: a side with no value is not a stable "
        "side with a value, got %r" % (row["base"],))
    assert row["delta"] is None, \
        "no number on the base side means no delta, got %r" % (row["delta"],)
    assert row["verdict"] == "unstable", (
        "the comparison is not 'added' just because the base mean is None: the metric WAS "
        "declared, and a side that never produced a value cannot support a claim, got %r"
        % (row["verdict"],))

    # --- regressions() is a sorted filter, and nothing else ----------------
    hand = {
        "zeta": {"base": 1.0, "cand": 0.5, "delta": -0.5, "noise": 0.1,
                 "verdict": "regression"},
        "alpha": {"base": 0.5, "cand": 1.0, "delta": 0.5, "noise": 0.1,
                  "verdict": "improvement"},
        "mu": {"base": 0.5, "cand": 0.25, "delta": -0.25, "noise": 0.0,
               "verdict": "regression"},
        "beta": {"base": 0.5, "cand": 0.6, "delta": 0.1, "noise": 0.3,
                 "verdict": "stable"},
        "gamma": {"base": None, "cand": 0.5, "delta": None, "noise": 0.0,
                  "verdict": "added"},
    }
    got = s.regressions(hand)
    assert isinstance(got, tuple), \
        "regressions() returns a tuple, got %r" % (type(got).__name__,)
    assert got == ("mu", "zeta"), (
        "regressions() is the regression verdicts ONLY — not the improvements, not the "
        "unstable or one-sided rows — SORTED by metric name: got %r" % (got,))
    assert s.regressions({}) == (), "a diff with no rows has no regressions: %r" % (s.regressions({}),)
    assert s.diff_metrics(_agg({}), _agg({})) == {}, \
        "two empty aggregations differ in nothing"

    print("check_09: the sign of delta, the strict noise + eps boundary, the noise being "
          "the larger spread of both sides, a missing side that stays None, one-sided "
          "metrics that are added/removed, unstable sides that refuse a verdict, and a "
          "sorted regressions() — all asserted")

def check_10():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _identity(case, answer):
        return 1.0 if answer is not None and answer.strip() == case.answer.strip() else 0.0

    class _Registry:
        def __init__(self, bound=(("identity", _identity),)):
            self.binds = []
            self._bound = bound

        def bind(self, names):
            self.binds.append(tuple(names))
            return self._bound

    def _spec(case_ids, *, metrics=("identity",), max_ticks=1000, max_calls=1000,
              max_judge_calls=500, notes=""):
        return {"id": "toy", "cases": case_ids, "metrics": list(metrics),
                "max_ticks": max_ticks, "max_calls": max_calls,
                "max_judge_calls": max_judge_calls, "notes": notes}

    def _case_spec(case_id, *, repeats=1, weight=1.0, max_ticks=10):
        return {"id": case_id, "prompt": "What is 2 + 3?", "answer": "5",
                "repeats": repeats, "weight": weight, "max_ticks": max_ticks}

    import lab
    import stage_01
    import stage_07
    import stage_10 as s

    # --- the hash belongs to the effective config -------------------------
    minimal = stage_01.parse_suite(_spec([_case_spec("a")]))
    spelled_out = stage_01.parse_suite(_spec([
        {"id": "a", "prompt": "What is 2 + 3?", "answer": "5", "weight": 1.0,
         "max_ticks": 10, "repeats": 1, "tags": []}]))
    digest = s.suite_hash(minimal)
    assert isinstance(digest, str) and len(digest) == 16, \
        "the suite hash is 16 hex characters, got %r" % (digest,)
    assert all(character in "0123456789abcdef" for character in digest), \
        "the suite hash is hexadecimal, got %r" % (digest,)
    assert s.suite_hash(minimal) == digest, "the hash is deterministic, run to run"
    import hashlib
    assert digest == hashlib.sha256(
        stage_01.canonical_suite(minimal).encode("utf-8")).hexdigest()[:16], \
        ("the suite hash is the first 16 hex characters of sha256 over the canonical form — "
         "the log is compared across processes and machines, so it cannot be a Python hash "
         "(got %r)" % (digest,))
    assert s.suite_hash(spelled_out) == digest, \
        ("a default spelled out is not a different suite: the hash is over the effective "
         "config, so an explicit default must not invalidate a resume")
    assert s.suite_hash(stage_01.parse_suite(_spec([_case_spec("a")], notes="hello"))) != digest, \
        "a changed note is a changed suite"
    assert s.suite_hash(stage_01.parse_suite(_spec([_case_spec("a", weight=2.0)]))) != digest, \
        "a changed weight is a changed suite"
    assert s.suite_hash(stage_01.parse_suite(_spec([_case_spec("a")], metrics=()))) != digest, \
        "a suite that measures nothing is a different suite"
    assert s.suite_hash(stage_01.parse_suite(_spec([_case_spec("b")]))) != digest, \
        "a different case id is a different suite"

    # --- the checkpoint ----------------------------------------------------
    root = tempfile.mkdtemp(prefix="f2-resume-")
    state_path = os.path.join(root, "nested", "run.state")
    log_path = os.path.join(root, "nested", "run.jsonl")
    written = s.write_checkpoint(state_path, suite=minimal)
    assert written == {"hash": digest, "suite": "toy"}, \
        "write_checkpoint returns and records {\"hash\", \"suite\"}: %r" % (written,)
    assert os.path.isfile(state_path), "the checkpoint's parent directory is created"
    read = s.read_checkpoint(state_path)
    assert read == written, "the checkpoint round-trips: %r" % (read,)
    assert s.read_checkpoint(os.path.join(root, "nope.state")) is None, \
        "a missing checkpoint is None, not an error: that is a run that never started"
    bad_path = os.path.join(root, "nested", "bad.state")
    for content, why in (("{not json", "a checkpoint that is not JSON"),
                         ("[1, 2]", "a checkpoint that is a list"),
                         ('{"suite": "toy"}', "a checkpoint without a hash")):
        with open(bad_path, "w") as handle:
            handle.write(content)
        try:
            s.read_checkpoint(bad_path)
            raise AssertionError("%s must be refused: %r" % (why, content))
        except lab.ConfigError as exc:
            if "not JSON" in why:
                assert "JSON" in str(exc), \
                    ("a checkpoint that is not JSON is refused for that reason, not as a "
                     "malformed object: %r" % (str(exc),))
            assert "bad.state" in str(exc), \
                "the refusal names the file: %r" % (str(exc),)
    assert s.read_checkpoint(state_path) == written, \
        "probing the malformed cases does not disturb a good checkpoint" 

    # --- a fresh run, and the bytes it produces ----------------------------
    os.remove(state_path)          # the probes above wrote checkpoints for another suite
    suite = stage_01.parse_suite(_spec([_case_spec("a", repeats=2), _case_spec("b")]))
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    fresh = s.resume_run(suite, solver, clock=clock, registry=_Registry(), state_path=state_path,
                         log_path=log_path)
    assert fresh["resumed"] is False and fresh["reused"] == 0, \
        "a run without a checkpoint says it is not a resume: %r" % (fresh,)
    assert fresh["records"] == 3 and fresh["cases"] == 2, \
        "and it ran every unit of the suite: %r" % (fresh,)
    assert fresh["status_counts"] == {"ok": 3, "no_answer": 0, "solver_error": 0,
                                      "timeout": 0, "case_error": 0}, \
        "the statuses of the whole run are in the summary: %r" % (fresh["status_counts"],)
    assert solver.calls == 3, "three units, three calls: %r" % (solver.calls,)
    with open(log_path, "rb") as handle:
        whole_log = handle.read()
    assert len(stage_07.read_records(log_path)) == 3, \
        "the log has one line per record: %r" % (stage_07.read_records(log_path),)

    # --- the same run through the plain runner is the same bytes ----------
    other_log = os.path.join(root, "uninterrupted.jsonl")
    clock = lab.Ticker()
    runner = lab.perfect(clock=clock)
    import stage_04
    import stage_07 as log_module
    stage_04.run_suite(suite, runner, clock=clock, registry=_Registry(),
                       sink=log_module.RunLog(other_log).append)
    with open(other_log, "rb") as handle:
        assert handle.read() == whole_log, \
            ("the resume's fresh path produces the same bytes as the plain runner: the "
             "resume may not tweak the records it writes")

    # --- a resume in the middle of a case --------------------------------
    with open(log_path, "wb") as handle:
        handle.write(b"".join(whole_log.splitlines(keepends=True)[:2]))
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    seen = []
    partial = s.resume_run(suite, solver, clock=clock, registry=_Registry(),
                           sink=seen.append, state_path=state_path, log_path=log_path)
    assert partial["suite"] == "toy", \
        "the summary names the suite it resumed: %r" % (partial["suite"],)
    assert partial["resumed"] is True and partial["reused"] == 2, \
        "the resume reports what it reused: %r" % (partial,)
    assert [(r["case"], r["repeat"]) for r in seen] == [("b", 0)], \
        ("the sink sees exactly the records this resume produced, not the ones it reused: %r"
         % ([(r["case"], r["repeat"]) for r in seen],))
    assert partial["status_counts"] == {"ok": 3, "no_answer": 0, "solver_error": 0,
                                        "timeout": 0, "case_error": 0}, \
        "the status counts cover the merged log, not only the new records: %r" \
        % (partial["status_counts"],)
    assert solver.calls == 1, \
        ("the case in flight is not re-run from its start: one unit was missing, so the "
         "solver was called once (%r)" % (solver.calls,))
    assert partial["records"] == 3 and partial["cases"] == 2, \
        "the totals cover the merged log: %r" % (partial,)
    records = stage_07.read_records(log_path)
    assert [(r["case"], r["repeat"]) for r in records] == [("a", 0), ("a", 1), ("b", 0)], \
        "the merged log holds every unit exactly once, in order: %r" \
        % ([(r["case"], r["repeat"]) for r in records],)
    with open(log_path, "rb") as handle:
        assert handle.read() == whole_log, \
            ("the resumed log is byte for byte the log of an uninterrupted run — that is the "
             "property the whole stage is about")
    again = s.resume_run(suite, lab.perfect(clock=lab.Ticker()), clock=lab.Ticker(),
                         registry=_Registry(), state_path=state_path, log_path=log_path)
    assert again["records"] == 3 and again["reused"] == 3 and again["stopped"] is None, \
        "a finished log resumes into nothing: %r" % (again,)
    with open(log_path, "rb") as handle:
        assert handle.read() == whole_log, "and it does not touch the bytes"

    # --- a truncated last line is a crash, not corruption -----------------
    cut = whole_log.splitlines(keepends=True)
    with open(log_path, "wb") as handle:
        handle.write(b"".join(cut[:2]) + cut[2][:40])
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    repaired = s.resume_run(suite, solver, clock=clock, registry=_Registry(bound=(("identity", _identity),)),
                            state_path=state_path, log_path=log_path)
    assert solver.calls == 1 and repaired["reused"] == 2, \
        "a half-written final line is re-run, not trusted: %r" % (repaired,)
    with open(log_path, "rb") as handle:
        assert handle.read() == whole_log, \
            "and the repaired log is again the uninterrupted run's bytes"
    # a crash in the middle of a repeated case: the rest of THAT case continues
    with open(log_path, "wb") as handle:
        handle.write(cut[0])
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    midway = s.resume_run(suite, solver, clock=clock, registry=_Registry(),
                          state_path=state_path, log_path=log_path)
    assert solver.calls == 2 and midway["reused"] == 1, \
        ("a case that was seen but not finished is not done: one record of 'a' is on disk, "
         "so the remaining repeat and 'b' both run (%r)" % (midway,))
    assert [(r["case"], r["repeat"]) for r in stage_07.read_records(log_path)] \
        == [("a", 0), ("a", 1), ("b", 0)], \
        "and no unit is recorded twice: %r" % (midway,)
    with open(log_path, "rb") as handle:
        assert handle.read() == whole_log, "the bytes are the uninterrupted run's"

    # a record that was written but never terminated: kept, and given its newline
    with open(log_path, "wb") as handle:
        handle.write(b"".join(cut[:2]) + cut[2].rstrip(b"\n"))
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    terminated = s.resume_run(suite, solver, clock=clock, registry=_Registry(),
                              state_path=state_path, log_path=log_path)
    assert solver.calls == 0 and terminated["reused"] == 3, \
        ("a complete record whose terminator was eaten by a crash is not re-run: three "
         "records are on disk, so nothing is left to do (%r)" % (terminated,))
    with open(log_path, "rb") as handle:
        assert handle.read() == whole_log, \
            "and the resume puts back the terminator: the bytes are the uninterrupted run's"

    # ... but a broken line in the middle is corruption, and it is refused
    with open(log_path, "wb") as handle:
        handle.write(cut[0] + b"{oops\n" + b"".join(cut[2:]))
    try:
        s.resume_run(suite, lab.perfect(clock=lab.Ticker()), clock=lab.Ticker(),
                     registry=_Registry(), state_path=state_path, log_path=log_path)
        raise AssertionError("a malformed line inside the log must be refused, not skipped")
    except lab.ConfigError:
        pass

    # --- a different suite may not reuse the log --------------------------
    other_suite = stage_01.parse_suite(_spec([_case_spec("a", repeats=2), _case_spec("b")],
                                             notes="changed"))
    with open(log_path, "wb") as handle:
        handle.write(b"".join(cut[:2]))
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    try:
        s.resume_run(other_suite, solver, clock=clock, registry=_Registry(),
                     state_path=state_path, log_path=log_path)
        raise AssertionError("a resume for a different suite must be refused")
    except lab.ConfigError as exc:
        assert "toy" in str(exc), "the refusal names the suites: %r" % (str(exc),)
    assert solver.calls == 0, "and it costs nothing: the config is checked first"
    with open(log_path, "rb") as handle:
        assert handle.read() == b"".join(cut[:2]), "and the log is left alone"

    # --- the budgets carry over ------------------------------------------
    budget_state = os.path.join(root, "budget.state")
    budget_log = os.path.join(root, "budget.jsonl")
    tight = stage_01.parse_suite(_spec([_case_spec("a"), _case_spec("b"), _case_spec("c")],
                                       max_calls=2))
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    stopped = s.resume_run(tight, solver, clock=clock, registry=_Registry(),
                           state_path=budget_state, log_path=budget_log)
    assert stopped["stopped"] == "calls" and stopped["records"] == 2 and solver.calls == 2, \
        "a run that ran out of calls stops where the budget says: %r" % (stopped,)
    clock = lab.Ticker()
    solver = lab.perfect(clock=clock)
    retried = s.resume_run(tight, solver, clock=clock, registry=_Registry(),
                           state_path=budget_state, log_path=budget_log)
    assert solver.calls == 0 and retried["records"] == 2 and retried["stopped"] == "calls", \
        ("the budget belongs to the run, not to the process: resuming a run that spent its "
         "calls buys nothing back, and the solver is never called: %r" % (retried,))
    assert retried["calls"] == 2 and retried["ticks"] == 0, \
        "the counters are the merged log's sums: %r" % (retried,)

    # --- the clock budget carries over as well ----------------------------
    tick_state = os.path.join(root, "tick.state")
    tick_log = os.path.join(root, "tick.jsonl")
    ticking = stage_01.parse_suite(_spec([_case_spec("a"), _case_spec("b"), _case_spec("c")],
                                         max_ticks=3))
    clock = lab.Ticker()
    solver = lab.slow(2, clock=clock)
    timed = s.resume_run(ticking, solver, clock=clock, registry=_Registry(),
                         state_path=tick_state, log_path=tick_log)
    assert timed["stopped"] == "ticks" and timed["records"] == 2 and solver.calls == 2, \
        "a run that spent its clock stops where the budget says: %r" % (timed,)
    clock = lab.Ticker()
    solver = lab.slow(2, clock=clock)
    retimed = s.resume_run(ticking, solver, clock=clock, registry=_Registry(),
                           state_path=tick_state, log_path=tick_log)
    assert solver.calls == 0 and retimed["stopped"] == "ticks" and retimed["records"] == 2, \
        ("the clock already spent is part of the run: resuming a run at its tick budget makes "
         "no further calls, and the same budget is named: %r" % (retimed,))
    assert retimed["ticks"] == 4, "and the totals are the merged log's: %r" % (retimed,)

    # --- a fresh run starts the log over ---------------------------------
    stale_log = os.path.join(root, "stale.jsonl")
    with open(stale_log, "w") as handle:
        handle.write('{"case": "old", "repeat": 0, "status": "ok", "answer": "x",\n')
    os.remove(budget_state)
    clock = lab.Ticker()
    fresh_again = s.resume_run(tight, lab.perfect(clock=clock), clock=clock,
                               registry=_Registry(), state_path=budget_state,
                               log_path=stale_log)
    assert fresh_again["resumed"] is False and fresh_again["reused"] == 0, \
        "no checkpoint means a new run: %r" % (fresh_again,)
    assert all(record["case"] != "old" for record in stage_07.read_records(stale_log)), \
        ("a new run does not append to a log that belongs to no checkpoint: two runs spliced "
         "into one file is the failure the checkpoint prevents")

    print("check_10: the hash, the checkpoint, the prefix, the carried budget and the bytes "
          "of a resumed run — %d bytes of log compared" % (len(whole_log),))
    shutil.rmtree(root, ignore_errors=True)

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The suite config, and the case that is not a case",
        tags=["suite-config", "validation"],
        action="Write `SUITE_KEYS`, `CASE_KEYS`, `Case`, `Suite`, `parse_suite` and "
               "`canonical_suite` in stage_01.py.",
        predict="What a spec with `\"max_ticks\": true` does, what two specs that "
                "differ only in spelling a default out hash to, and what a "
                "duplicated case id costs downstream.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The metric plugins, and the metric that cannot say no",
        tags=["plugins", "metrics"],
        action="Write `MetricRegistry` and `apply_metrics` in stage_02.py.",
        predict="What `bind` does before the first case runs, what a metric that "
                "returns `None` means for the denominator, and where a metric "
                "that raises files its message.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="One case, one record, and the clock that is not a stopwatch",
        tags=["records", "budgets"],
        action="Write `STATUSES`, `CASE_RECORD_KEYS`, `METRIC_DP`, `round_metrics` "
               "and `run_case` in stage_03.py.",
        predict="What `ticks` holds for a solver that raised on its second tick, "
                "what happens to the answer of a call that ran past its deadline, "
                "and which status a case object with a string `max_ticks` gets.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The run: a budget checked before the call, not a receipt after it",
        tags=["run-loop", "budgets"],
        action="Write `RUN_KEYS` and `run_suite` in stage_04.py.",
        predict="How many records a suite of three cases leaves with `max_calls=2`, "
                "what the log holds for a case that was never reached, and which "
                "budget is named when both are spent.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Aggregation whose unit is the case, not the line",
        tags=["aggregation", "stability"],
        action="Write `MIN_N`, `MAX_SPREAD`, `case_values`, `aggregate` and "
               "`stability_verdict` in stage_05.py.",
        predict="What a metric's `n` counts when a case ran three times, what a "
                "case's `None` does to the denominator, and which verdict a metric "
                "with two cases and one wild value gets.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The judge protocol: cached, budgeted, and blind to the order you asked",
        tags=["judge", "caching"],
        action="Write `JUDGE_VERDICTS`, `judge_score`, `check_verdict`, "
               "`JudgeSession`, `judge_metric` and `pairwise_metric` in stage_06.py.",
        predict="What a cache hit costs against `max_calls`, what a judge that "
                "raises scores, and what an order-sensitive judge is worth to a "
                "pairwise metric that asks both ways.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Records whose bytes two runs share",
        tags=["canonical-json", "logging"],
        action="Write `canonical`, `record_line`, `RunLog` and `read_records` in "
               "stage_07.py.",
        predict="What a metric of 0.1 + 0.2 looks like next to 0.3 in the log, what "
                "`tolerant=True` drops, and what a record with a set in it does.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The gate that refuses to pass what it cannot evaluate",
        tags=["gate", "exit-status"],
        action="Write `GATE_KEYS`, the four `EXIT_*` codes, `parse_gate`, "
               "`evaluate_gate`, `evaluate_gates` and `run_exit` in stage_08.py.",
        predict="What an empty gate list returns, what a run with one `case_error` "
                "exits with when every gate passes, and which bound is inclusive.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The baseline diff: a regression has to beat the noise",
        tags=["regression", "diff"],
        action="Write `EPS`, `diff_metrics` and `regressions` in stage_09.py.",
        predict="What a metric that lost 0.01 with a spread of 0.2 is called, what "
                "a metric that exists only in the candidate is called, and what an "
                "unstable comparison is called.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The resume, and the hash that decides whether it is allowed",
        tags=["resume", "checkpoint"],
        action="Write `suite_hash`, `write_checkpoint`, `read_checkpoint` and "
               "`resume_run` in stage_10.py.",
        predict="What happens to a run resumed with a suite whose only change is a "
                "note, how many calls a resume of a budget-stopped run makes, and "
                "how the resumed log compares to an uninterrupted one.",
        check=check_10,
    ),
]
