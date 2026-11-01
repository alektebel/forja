"""Evals From Scratch — course manifest.

Thirteen graded stages that build an evaluation harness for text-output and
structured-extraction systems, and the statistics that decide whether a
difference is real: the split that must not leak, the metrics that are not
about quality, deterministic assertions, EM and F1, ranking metrics, a judge
and its biases, judge calibration, paired significance, multiple comparisons,
the gate you put in CI, field-level extraction metrics, confidence ECE, and
format sensitivity with criteria identity.

    python3 codecraft/cli.py run evals-from-scratch
"""

import math
import random
import re

from codecraft.api import stage

TITLE = "Evals From Scratch"
DESCRIPTION = ("An evaluation harness from the parts up: honest splits, "
               "operational metrics, deterministic assertions, EM/F1, ranking "
               "metrics, an LLM judge with its biases, calibration, paired "
               "significance, multiple comparisons, a regression gate, "
               "structured field metrics, confidence ECE, and format "
               "sensitivity.")
LEVEL = "intermediate"
ORDER = 10


# --- helpers shared by the checks ------------------------------------------

def _close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def _rows(n, prefix="r", groups=1):
    return [{"id": f"{prefix}{i}", "group": f"g{i % groups}"} for i in range(n)]


def _run(n, rate, seed, slice_rates=None, key="tenant", slices=("A", "B", "C")):
    """n rows with a pass rate; per-slice rates when asked."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        name = slices[i % len(slices)]
        p = rate if slice_rates is None else slice_rates[name]
        rows.append({"id": f"i{i}", key: name, "passed": rng.random() < p,
                     "latency_ms": 100 + (i % 7) * 10})
    return rows


def _flip(rows, ids, to=False):
    touched = set(ids)
    return [dict(r, passed=(to if r["id"] in touched else r["passed"]))
            for r in rows]


def _flagged(rows, ids, value=True):
    touched = set(ids)
    return [dict(r, passed=(value if r["id"] in touched else r["passed"]))
            for r in rows]


# --- 1. the eval set, and the split that must not leak ---------------------

def check_1():
    import stage_01 as s

    rows = _rows(30, groups=10)     # 10 groups of 3 rows each
    loaded = s.load(rows)
    assert len(loaded) == 30, f"every row survives load(): {len(loaded)}"
    assert loaded[0]["id"] == "r0" and loaded[0]["group"] == "g0"
    loaded[0]["id"] = "tampered"
    assert rows[0]["id"] == "r0", (
        "load() handed back the caller's own dicts: one edit anywhere then "
        "rewrites the eval set, and the set is the only thing that makes two "
        "runs comparable")

    parts = s.split(loaded, seed=7)
    assert set(parts) == {"train", "dev", "test"}, f"keys: {sorted(parts)}"
    assert sum(len(v) for v in parts.values()) == 30, "every row lands in one split"
    assert len({r["id"] for v in parts.values() for r in v}) == 30, (
        "a row appears in two splits, or twice in one")

    seen = {}
    for name, items in parts.items():
        for row in items:
            group = row["group"]
            assert seen.get(group, name) == name, (
                f"group {group} is in {name} and in {seen[group]}: rows from "
                f"one source (five phrasings of one ticket, a template, the "
                f"same document twice) sit on both sides, so the test score "
                f"measures recall of the train set")
            seen[group] = name

    assert s.split(loaded, seed=7) == parts, (
        "the same seed must produce the same split, or every comparison "
        "against a previous run is between two different test sets")
    assert len(parts["train"]) == 18 and len(parts["dev"]) == 6 and len(parts["test"]) == 6, (
        f"10 uniform groups of 3 can hit 0.6/0.2/0.2 exactly; got "
        f"{[len(v) for v in (parts['train'], parts['dev'], parts['test'])]}")

    assert s.overlap(parts["train"], parts["test"]) == set()
    assert s.overlap(parts["dev"], parts["test"]) == set()
    assert s.overlap(parts["train"], parts["train"]) == {
        r["group"] for r in parts["train"]}
    assert len(s.overlap(parts["train"], parts["train"])) == 6

    for bad, why in (
            ([{"id": "x"}], "a row with no group cannot be split without leaking"),
            ([{"id": "x", "group": ""}], "an empty group key groups nothing"),
            ([{"id": "x", "group": "g"}, {"id": "x", "group": "h"}],
             "two rows with the same id are two rows pretending to be one")):
        try:
            s.load(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"load() accepted {why}: {bad}")

    for bad_ratios in ((0.5, 0.5, 0.5), (0.6, 0.6), (1.0,)):
        try:
            s.split(loaded, ratios=bad_ratios, seed=0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"ratios {bad_ratios} do not describe three splits")
    try:
        s.split([{"id": "a", "group": "g"}], seed=0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "one group cannot fill train, dev and test without leaking itself")


# --- 2. the numbers that are not about quality -----------------------------

def _ops_rows():
    rows = []
    for i in range(20):
        row = {"id": f"r{i}", "latency_ms": (i + 1) * 10,
               "prompt_tokens": 5, "output_tokens": 2, "output": "a real answer"}
        if i in (1, 5, 9):
            row["output"] = ""
        elif i == 3:
            row["output"] = "I cannot help with that."
        elif i in (2, 6, 11, 15):
            row["output"] = "I cannot reach the service"
            row["error"] = "timeout"
        rows.append(row)
    return rows


def check_2():
    import stage_02 as s

    rows = _ops_rows()
    n = len(rows)
    errors = [r for r in rows if r.get("error")]
    assert len(errors) == 4, f"fixture: {len(errors)} errors"

    assert _close(s.rate(rows, lambda r: r.get("error") is not None), 4 / n)
    assert _close(s.rate(rows, lambda r: r["id"] in {"r0", "r1"}), 2 / n)
    assert s.rate([], lambda r: True) == 0.0, "an empty run has no rate, not a crash"

    refusals = [r for r in rows if not r.get("error")
                and (not r["output"] or "cannot" in r["output"].lower())]
    assert len(refusals) == 3 + 1, f"fixture: {len(refusals)} refusals among the live rows"
    got = s.refusal_rate(rows)
    assert _close(got, 4 / (n - 4)), (
        f"got {got}: the denominator is the non-errored rows (16), not all 20. "
        f"Four timeouts whose output is empty are not four refusals — folding "
        f"them in makes a flaky endpoint look like a cautious model")
    assert s.refusal_rate([]) == 0.0

    lat = s.latency_summary(rows)
    assert lat["n"] == 20 and _close(lat["mean"], 105.0), f"{lat}"
    assert _close(lat["max"], 200.0)
    assert _close(lat["p50"], 100.0), f"p50 nearest-rank is the 10th of 20: {lat['p50']}"
    assert _close(lat["p95"], 190.0), (
        f"got {lat['p95']}. p95 is the 19th sorted sample (ceil(0.95*20) = 19), "
        f"not the mean of the top 5% and not an interpolation: a percentile is "
        f"a request somebody actually made")

    tok = s.token_summary(rows)
    assert tok == {"prompt": 100, "output": 40}, f"got {tok}"
    missing = s.token_summary([{"id": "x", "output": "hi"}])
    assert missing == {"prompt": 0, "output": 0}, (
        f"a row that never reported tokens counts 0, it does not make the "
        f"total NaN: {missing}")

    rep = s.operational_report(rows)
    assert set(rep) == {"n", "error_rate", "refusal_rate", "latency", "tokens"}, f"{sorted(rep)}"
    assert rep["n"] == 20
    assert _close(rep["error_rate"], 0.2), f"{rep['error_rate']}"
    assert _close(rep["refusal_rate"], 4 / 16), f"{rep['refusal_rate']}"
    assert rep["latency"] == lat and rep["tokens"] == tok


# --- 3. deterministic assertions -------------------------------------------

def check_3():
    import stage_03 as s

    def ok(record):
        return True, "looks fine"

    def bad(record):
        return False, "no json object at all"

    def boom(record):
        raise ZeroDivisionError("division by zero")

    def sloppy(record):
        return True          # not a (passed, detail) pair

    cases = {"ok": ok, "bad": bad, "boom": boom, "sloppy": sloppy}
    records = [{"id": "a"}, {"id": "b"}]
    checks = [s.check(name, fn) for name, fn in cases.items()]
    assert all(c["name"] in cases and callable(c["fn"]) for c in checks), f"{checks}"

    results = s.run_checks(records, checks)
    assert len(results) == len(records) * len(checks), f"{len(results)} rows"
    by = {(r["id"], r["check"]): r for r in results}
    assert by[("a", "ok")]["state"] == "passed"
    assert by[("a", "bad")]["state"] == "failed"
    assert by[("b", "bad")]["detail"], "a failure must carry its reason"
    assert by[("a", "boom")]["state"] == "errored", (
        f"a check that raises is an error, not a pass and not a crash: got "
        f"{by[('a', 'boom')]['state']}")
    assert "ZeroDivisionError" in by[("a", "boom")]["detail"], (
        f"the error state must name what went wrong: {by[('a', 'boom')]['detail']}")
    assert by[("b", "boom")]["state"] == "errored", (
        "the runner must carry on to the next record after a check raises")
    assert by[("b", "sloppy")]["state"] == "errored", (
        f"got {by[('b', 'sloppy')]['state']} for a predicate returning a bare "
        f"True. A truthy non-tuple is not a pass — the harness has no reason "
        f"to show, and the next person reading the report has no idea what "
        f"was verified")

    summary = s.summarise(results)
    assert summary["n_records"] == 2 and summary["checks"] == 4, f"{summary}"
    assert summary["passed"] == 2, f"{summary}"
    assert summary["failed"] == 2
    assert summary["errored"] == 4
    assert _close(summary["pass_rate"], 2 / 8), (
        f"got {summary['pass_rate']}: the denominator is every (record, check) "
        f"pair that ran. An errored pair did not pass, and calling it one is "
        f"how a harness reports 100% while half its checks never executed")
    assert summary["failures_by_check"] == {"bad": 2}, (
        f"the report must say which check failed: {summary['failures_by_check']}")

    fences = {"fenced": {"id": "f", "output": '```json\n{"a": 1}\n```'},
              "prose": {"id": "p", "output": 'Sure! {"a": 1}'},
              "clean": {"id": "c", "output": '  {"a": 1}  '},
              "broken": {"id": "b", "output": '{"a": 1'},
              "empty": {"id": "e", "output": "   "},
              "list": {"id": "l", "output": '[1, 2]'}}
    for name, record in fences.items():
        passed, detail = s.json_valid(record)
        assert passed == (name == "clean"), (
            f"json_valid said {passed} for the {name!r} output. Only whitespace "
            f"around a JSON value is legal; a fence or a sentence in front is "
            f"the shape your prompt has drifted into, and accepting it hides "
            f"the drift until a consumer breaks")
        assert isinstance(detail, str) and detail, f"{name}: no detail"

    has = s.has_fields("a", "b")
    assert has({"id": "1", "output": '{"a": 1, "b": 2}'})[0] is True
    passed, detail = has({"id": "2", "output": '{"a": 1}'})
    assert passed is False and "b" in detail, (
        f"the detail must name the missing field: {detail}")
    assert has({"id": "3", "output": '{"a": 1, "b": null}'})[0] is False, (
        "a present but null field is missing in every sense that matters")
    assert has({"id": "4", "output": '{"a": 1, "b": 2, "extra": 3}'})[0] is True, (
        "an extra field is not a failure — failing on it makes every honest "
        "addition look like a regression")
    assert has({"id": "5", "output": "not json"})[0] is False


# --- 4. exact match and token F1 -------------------------------------------

def check_4():
    import stage_04 as s

    assert s.normalize("The Cat, sat!") == "cat sat", f"{s.normalize('The Cat, sat!')!r}"
    assert s.normalize("A   DOG.") == "dog", f"{s.normalize('A   DOG.')!r}"
    assert s.normalize("an APPLE") == "apple"
    assert s.normalize("") == ""

    assert s.exact_match("The Cat.", "cat") is True
    assert s.exact_match("cat sat", "cat") is False
    assert s.exact_match("", "") is True, "two empty answers are the same answer"

    assert _close(s.token_f1("cat sat", "cat"), 2 / 3), (
        f"got {s.token_f1('cat sat', 'cat')}: precision 1/2, recall 1, F1 2/3")
    assert _close(s.token_f1("The Cat, sat!", "the cat sat"), 1.0), (
        "normalise BOTH sides. Applying it to the gold only means a model is "
        "punished for the test set's capitalisation")
    assert _close(s.token_f1("cat cat", "cat"), 2 / 3), (
        f"got {s.token_f1('cat cat', 'cat')}: overlap is a MULTISET count "
        f"(Counter), not a set union — otherwise a repeated word scores a "
        f"perfect answer and rewards verbosity")
    assert s.token_f1("", "cat") == 0.0
    assert s.token_f1("cat", "") == 0.0
    assert s.token_f1("", "") == 0.0, (
        "0/0 is not a perfect answer. Returning 1.0 here makes an empty "
        "prediction the best possible response on an empty gold")

    pairs = [("cat sat", "cat"), ("dog", "dog")]
    assert _close(s.mean_f1(pairs), (2 / 3 + 1.0) / 2), f"{s.mean_f1(pairs)}"
    pooled = s.corpus_f1(pairs)
    assert _close(pooled, 0.8), (
        f"got {pooled}. Pooled F1 pools the counts first: overlap 2, predicted "
        f"tokens 3, gold tokens 2 -> p 2/3, r 1, F1 0.8. It is not the mean of "
        f"the per-pair F1s (0.833), and the two answer different questions")
    assert s.corpus_f1([]) == 0.0, "no pairs, no division by zero"
    assert s.corpus_f1([("", "")]) == 0.0


# --- 5. ranking metrics ----------------------------------------------------

def check_5():
    import stage_05 as s

    assert _close(s.recall_at_k(["a", "b"], ["a", "x", "b"], 2), 0.5), (
        "the denominator is the number of relevant documents, and the top-2 "
        "of that list holds one of them")
    assert _close(s.recall_at_k(["a"], ["a"], 5), 1.0)
    assert s.recall_at_k([], ["a"], 3) == 0.0, (
        "a query with no relevant documents cannot be satisfied; 0.0 keeps it "
        "visible in the mean instead of quietly inflating it")

    queries = [{"retrieved": ["x", "a"], "relevant": ["a"]},
               {"retrieved": ["b"], "relevant": ["a"]},
               {"retrieved": ["a"], "relevant": ["a"]}]
    assert _close(s.mrr(queries), (0.5 + 0.0 + 1.0) / 3), f"{s.mrr(queries)}"
    assert _close(s.mrr([{"retrieved": ["x"], "relevant": ["a"]}]), 0.0)
    assert s.mrr([]) == 0.0

    assert _close(s.dcg([3, 2]), 7.0 / math.log2(2) + 3.0 / math.log2(3)), f"{s.dcg([3, 2])}"
    assert s.dcg([]) == 0.0
    assert s.dcg([0, 0]) == 0.0

    relevance = {"a": 1, "b": 1, "c": 3}
    assert _close(s.ndcg(["c", "a", "b"], relevance, k=2), 1.0), (
        f"got {s.ndcg(['c', 'a', 'b'], relevance, k=2)}: retrieving the two "
        f"best gains first IS the ideal ranking")
    partial = s.ndcg(["a", "b"], relevance, k=2)
    assert partial < 0.5, (
        f"got {partial}. A system that retrieves only the two mediocre "
        f"documents is not 1.0 — the ideal denominator is the best ordering of "
        f"ALL the judged documents ({sorted(relevance.values(), reverse=True)}), "
        f"not of the ones that were retrieved. Computing IDCG from the "
        f"retrieved pool inflates the worst systems the most")
    assert s.ndcg([], relevance) == 0.0
    assert s.ndcg(["a"], {"a": 0, "b": 0}) == 0.0, "no positive gain, no score"
    assert _close(s.ndcg(["a", "x"], {"a": 2}, k=2), 1.0), (
        "a key the relevance map does not contain has gain 0, it does not "
        "break the metric")


# --- 6. the judge, and the order you showed it in --------------------------

def _pairs(n=12):
    out = []
    for i in range(n):
        left = "A: answer " + "detail " * (i + 1)   # always the longer one
        right = "B: no"
        out.append({"id": f"p{i}", "a": left, "b": right})
    return out


def check_6():
    import stage_06 as s

    def prefers_a(first, second):
        return "first" if first.startswith("A") else "second"

    def prefers_longer(first, second):
        return "first" if len(first) >= len(second) else "second"

    def always_first(first, second):
        return "first"

    def always_ties(first, second):
        return "tie"

    pairs = _pairs()

    out = s.run_pairwise(always_first, pairs)
    assert out["n"] == len(pairs)
    assert out["flips"] == len(pairs), (
        f"a judge that answers 'first' every time flipped on {out['flips']} of "
        f"{len(pairs)} pairs — that is what position bias looks like in the data")
    assert _close(out["position_bias"], 1.0) and _close(out["agreement"], 0.0), f"{out}"
    assert _close(out["win_rate_a"], 0.5), (
        f"got {out['win_rate_a']}: the debiased counts give each order half a "
        f"win, so a pure layout preference cannot crown a winner")
    assert _close(out["a_wins"], out["b_wins"])

    naive = s.run_pairwise(always_first, pairs, swap=False)
    assert _close(naive["win_rate_a"], 1.0), (
        "one order only: the answer shown first wins everything, and the "
        "report says A is better. This is the number that ships")

    content = s.run_pairwise(prefers_a, pairs)
    assert _close(content["win_rate_a"], 1.0), f"{content}"
    assert content["flips"] == 0 and _close(content["position_bias"], 0.0), (
        f"a judge that prefers the same answer in BOTH orders has no position "
        f"bias — it has a preference. Got bias {content['position_bias']}: "
        f"counting every order-sensitive disagreement as bias would call this "
        f"one biased too, and the corruption is different")

    longer = s.run_pairwise(prefers_longer, pairs)
    assert _close(longer["win_rate_a"], 1.0) and _close(longer["position_bias"], 0.0), (
        f"{longer}: verbosity preference survives the swap, so the swap is not "
        f"a universal fix — it isolates one bias at a time")

    ties = s.run_pairwise(always_ties, pairs)
    assert ties["ties"] == len(pairs) * 2 or ties["a_wins"] == 0, "ties are not wins"
    assert _close(ties["win_rate_a"], 0.5), (
        f"got {ties['win_rate_a']}: a judge with no opinion leaves the rate at "
        f"one half rather than handing the win to A")
    assert _close(ties["position_bias"], 0.0)

    rng = random.Random(3)

    def coin(first, second):
        return rng.choice(["first", "second", "tie"])

    noisy = s.run_pairwise(coin, _pairs(200))
    assert 0.3 < noisy["win_rate_a"] < 0.7, f"{noisy}"
    assert 0.15 < noisy["position_bias"] < 0.4, f"{noisy}"


# --- 7. what the judge is worth --------------------------------------------

def check_7():
    import stage_07 as s

    labels = [True] * 40 + [False] * 60
    constant = [True] * 100
    conf = s.confusion(constant, labels)
    assert conf == {"tp": 40, "fp": 60, "tn": 0, "fn": 0}, f"{conf}"
    assert _close(s.agreement(constant, labels), 0.4), f"{s.agreement(constant, labels)}"

    skewed_labels = [True] * 85 + [False] * 15
    kappa = s.cohen_kappa([True] * 100, skewed_labels)
    assert abs(kappa) < 1e-9, (
        f"got {kappa}. A judge that always says pass agrees with 85% of an "
        f"85%-positive label set and knows nothing; kappa is 0.0 exactly, "
        f"which is the number that exposes it")

    perfect = s.cohen_kappa(labels, labels)
    assert _close(perfect, 1.0), f"{perfect}"
    mixed_j = [True] * 50 + [False] * 50
    mixed_l = [True] * 50 + [False] * 50
    assert _close(s.cohen_kappa(mixed_j, mixed_l), 1.0), f"{s.cohen_kappa(mixed_j, mixed_l)}"

    j = [True] * 40 + [False] * 10 + [False] * 40 + [True] * 10
    l = [True] * 50 + [False] * 50
    assert _close(s.cohen_kappa(j, l), 0.6), (
        f"got {s.cohen_kappa(j, l)}: observed agreement 0.8 against a chance "
        f"agreement of 0.5 — (0.8 - 0.5) / (1 - 0.5)")
    assert s.cohen_kappa([not x for x in l], l) < 0.0, (
        "a judge that inverts every label must score below zero, or the metric "
        "cannot tell worse-than-chance from chance")
    assert s.cohen_kappa([], []) == 0.0
    assert _close(s.cohen_kappa([True] * 5, [True] * 5), 1.0), (
        "two raters who never disagreed and never could: 1.0, not a division "
        "by zero")

    scores = [1, 2, 3, 4, 5] * 20
    truth = [q >= 4 for q in scores]
    best = s.threshold_for(scores, truth)
    assert _close(best["threshold"], 3.5), (
        f"got {best['threshold']}: with the labels drawn from >= 4, the cut "
        f"that separates them is 3.5 (score >= 3.5 means 4 or 5)")
    assert _close(best["f1"], 1.0), f"{best}"
    assert len(best["sweep"]) == 4, f"one row per candidate threshold: {best['sweep']}"
    assert _close(best["confusion"]["tp"], 40) and best["confusion"]["fp"] == 0, f"{best}"
    by_threshold = {row["threshold"]: row["f1"] for row in best["sweep"]}
    assert by_threshold[2.5] < 0.9 and by_threshold[4.5] < 0.9, (
        f"the sweep has to be shown, not just used: {by_threshold}. A fixed "
        f"midpoint cut is 0.80 here and 0.67 there, and neither number is "
        f"visible if you never compute the sweep")

    lower = [q >= 3 for q in scores]
    best = s.threshold_for(scores, lower)
    assert _close(best["threshold"], 2.5), (
        f"got {best['threshold']}: the optimal cut follows the labels. A "
        f"hard-coded midpoint is right by luck on one distribution and wrong "
        f"on this one")

    tied = s.threshold_for([3] * 10, [True] * 10)
    assert _close(tied["threshold"], 1.5), (
        f"got {tied['threshold']}: two thresholds score a perfect F1 here, and "
        f"the tie goes to the smallest — the rule has to be written down, or "
        f"the same data reports a different cut on a different day")
    assert sum(1 for row in tied["sweep"] if _close(row["f1"], 1.0)) == 2, (
        f"the fixture is a two-way tie: {[r['f1'] for r in tied['sweep']]}")

    perfect_but_thin = s.threshold_for([5, 5], [True, True])
    assert _close(perfect_but_thin["threshold"], 1.5) and _close(perfect_but_thin["f1"], 1.0)

    try:
        s.threshold_for([], [])
    except ValueError:
        pass
    else:
        raise AssertionError(
            "an empty calibration set produced a threshold: a sweep over no "
            "labels is a perfect score over no data")
    try:
        s.threshold_for([1, 2], [True])
    except ValueError:
        pass
    else:
        raise AssertionError("2 scores against 1 label is not a comparison")


# --- 8. is the difference real? --------------------------------------------

def _paired_case(flips_up, flips_down, n=400, seed=0):
    rng = random.Random(seed)
    b = [rng.random() < 0.5 for _ in range(n)]
    a = list(b)
    up = [i for i, v in enumerate(b) if not v][:flips_up]
    down = [i for i, v in enumerate(b) if v][:flips_down]
    for i in up:
        a[i] = True
    for i in down:
        a[i] = False
    return a, b


def check_8():
    import stage_08 as s

    assert _close(s.binom_two_sided(0, 0), 1.0), "no trials, no evidence"
    assert _close(s.binom_two_sided(3, 10), 0.34375), (
        f"got {s.binom_two_sided(3, 10)}: 2 * P(X <= 3) for X ~ Bin(10, 1/2) "
        f"= 2 * 176/1024, capped at 1")
    assert _close(s.binom_two_sided(10, 10), 2 / 1024), f"{s.binom_two_sided(10, 10)}"
    assert _close(s.binom_two_sided(5, 10), 1.0), (
        "the two-sided p-value is capped at 1.0; a dead heat cannot be less "
        "than certain")

    a, b = _paired_case(40, 0)
    m = s.mcnemar(a, b)
    assert m["a_only"] == 40 and m["b_only"] == 0, f"{m}"
    assert m["p"] < 1e-9, f"40 discordant pairs all one way: {m['p']}"
    same = s.mcnemar(b, b)
    assert same["p"] == 1.0 and same["a_only"] == 0, (
        f"{same}: identical systems on the same items produce no evidence")

    assert s.decide(a, b) == "a", f"a consistent improvement: {s.decide(a, b)}"
    assert s.decide(b, a) == "b"
    assert s.decide(b, b) == "inconclusive", (
        "nothing changed, so the data says nothing — not 'a' and not 'b'")
    small_a, small_b = _paired_case(3, 1)
    assert s.decide(small_a, small_b) == "inconclusive", (
        f"4 discordant pairs is not evidence: {s.paired_bootstrap(small_a, small_b)}")

    paired = s.paired_bootstrap(a, b)
    assert _close(paired["mean_diff"], 0.1), f"{paired}"
    assert paired["lo"] > 0, f"{paired}"
    assert paired["n"] == 400
    again = s.paired_bootstrap(a, b)
    assert again == paired, "the same seed must return the same interval"

    indep = s.independent_ci(a, b)
    assert indep["hi"] - indep["lo"] > paired["hi"] - paired["lo"], (
        f"paired interval width {paired['hi'] - paired['lo']:.3f} vs "
        f"independent {indep['hi'] - indep['lo']:.3f}. Resampling the two "
        f"sides separately throws away the shared difficulty of the items, "
        f"which is the only reason a few hundred rows can detect a 10-point "
        f"difference at all")

    ties = s.mcnemar([True] * 50 + [False] * 50, [True] * 50 + [False] * 50)
    assert ties["p"] == 1.0, f"{ties}"


# --- 9. ten configs, one winner, no correction ------------------------------

def check_9():
    import stage_09 as s

    assert _close(s.holm([0.04])[0], 0.04), (
        "a family of one is uncorrected — 0.04 stays 0.04")

    family = [0.04, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    adjusted = s.holm(family)
    assert len(adjusted) == len(family)
    assert all(ad >= raw - 1e-12 for ad, raw in zip(adjusted, family)), f"{adjusted}"
    assert _close(adjusted[0], 0.4), (
        f"got {adjusted[0]}: the best of ten tests at p=0.04 is not evidence "
        f"about any of them. Holm multiplies the smallest by m (10), and it is "
        f"the number that stops 'best of ten' from shipping")
    assert adjusted == sorted(adjusted), (
        f"the adjusted p-values must be monotone in the sorted raw ones: "
        f"{adjusted}")
    assert all(ad <= 1.0 for ad in adjusted)
    verdict = s.significant(family)
    assert verdict["rejected"] == [False] * 10, (
        f"none of those ten survives the correction: {verdict['rejected']}")
    assert all(_close(t, 0.05 / (10 - i)) for i, t in enumerate(verdict["thresholds"])), (
        f"the step-down thresholds are alpha/(m-i+1): {verdict['thresholds']}")

    worked = [0.001, 0.008, 0.039, 0.041, 0.042]
    adjusted = s.holm(worked)
    assert _close(adjusted[0], 0.005) and _close(adjusted[1], 0.032), f"{adjusted}"
    assert _close(adjusted[2], 0.117), f"{adjusted}"
    assert _close(adjusted[3], 0.117) and _close(adjusted[4], 0.117), (
        f"got {adjusted}. Without the running maximum the fourth value falls "
        f"to 0.082 — smaller than the third, which would make the fifth test "
        f"look stronger than the third, and Holm more lenient than it is. The "
        f"envelope is the step-down part")
    verdict = s.significant(worked)
    assert verdict["rejected"] == [True, True, False, False, False], (
        f"{verdict['rejected']}: the first two survive 0.05, the rest do not")

    assert s.significant([])["rejected"] == []
    single = s.significant([0.04])
    assert single["rejected"] == [True], (
        "the same p-value is significant alone and not significant in a family "
        "of ten — which is exactly why the family has to be decided before the "
        "numbers are read")

    stepped = s.significant([0.004, 0.02, 0.9])
    assert stepped["rejected"] == [True, True, False], (
        f"got {stepped['rejected']}. Bonferroni compares every p-value against "
        f"alpha/m and would reject only the first; Holm relaxes the threshold "
        f"as tests fall, so the second (0.02 against 0.05/2) survives too. "
        f"Bonferroni is strictly weaker and it is what gets written by "
        f"accident")
    assert _close(s.holm([0.004, 0.02, 0.9])[1], 0.04), (
        f"got {s.holm([0.004, 0.02, 0.9])}: the second smallest is multiplied "
        f"by the 2 tests still standing, not by all 3")


# --- 10. the gate, and the report you can diff ------------------------------

def _gate_case():
    baseline = _run(300, 0.8, seed=1,
                    slice_rates={"A": 0.85, "B": 0.8, "C": 0.75})
    ab = [r["id"] for r in baseline if r.get("tenant") != "C"]
    # 30 rows in A and B fall over: the interval moves, no floor does.
    worse = _flip(baseline, ab[:30], to=False)
    # every A/B failure repaired, 12 C rows broken: the aggregate is up and the
    # slice is under its floor. The mean is exactly what hides this.
    fixes = [r["id"] for r in baseline
             if r.get("tenant") != "C" and not r["passed"]]
    breaks = [r["id"] for r in baseline if r.get("tenant") == "C"][:12]
    slices = _flip(_flip(baseline, fixes, to=True), breaks, to=False)
    noise = _flip(baseline, ["i3", "i17", "i42"], to=True)
    return baseline, {"worse": worse, "slices": slices, "noise": noise}


def check_10():
    import stage_10 as s

    baseline, cases = _gate_case()
    floors = {"C": 0.7}
    out = s.gate(baseline, cases["worse"], floors=floors)
    assert out["decision"] == "regress", (
        f"the candidate is worse and its slices are all above their floors: "
        f"got {out['decision']} from {out['overall']}")
    assert out["overall"]["diff"] < 0 and out["overall"]["hi"] < 0, (
        f"{out['overall']}: 30 rows that used to pass now fail, in A and B "
        f"only, so the paired interval sits entirely below zero")
    assert out["n_paired"] == 300 and out["n_dropped"] == 0

    out = s.gate(baseline, cases["slices"], floors=floors)
    assert out["decision"] == "regress", (
        f"got {out['decision']}: the candidate is better overall "
        f"({out['overall']['diff']:+.3f}) and tenant C fell through its floor. "
        f"The aggregate is precisely the number that hides this")
    assert out["overall"]["diff"] > 0 and out["overall"]["lo"] > 0, (
        f"{out['overall']}: the fixture is built so the interval itself says "
        f"the candidate is better, which means the floor is the only thing "
        f"that can stop it")
    assert any("C" in reason for reason in out["reasons"]), (
        f"the reasons must name the breached slice: {out['reasons']}")
    assert out["slices"]["C"]["breach"] is True and out["slices"]["A"]["breach"] is False
    assert out["slices"]["C"]["candidate"] < floors["C"], f"{out['slices']['C']}"

    out = s.gate(baseline, cases["noise"], floors=floors)
    assert out["decision"] == "inconclusive", (
        f"got {out['decision']}: three flipped items is noise, and a gate that "
        f"calls it a win or a loss is a coin with a change log. {out['overall']}")
    assert any("zero" in reason.lower() for reason in out["reasons"]), (
        f"an inconclusive run has to say that the interval contains zero: "
        f"{out['reasons']}")

    shuffled = list(cases["noise"])
    random.Random(9).shuffle(shuffled)
    a = s.gate(baseline, cases["noise"], floors=floors)
    b = s.gate(baseline, shuffled, floors=floors)
    assert a["decision"] == b["decision"] and _close(a["overall"]["diff"], b["overall"]["diff"]), (
        f"{a['overall']} vs {b['overall']}: the rows are matched by id. Pairing "
        f"them by position compares one item against another and the whole "
        f"table becomes noise")

    gone = {"i5", "i6", "i7", "i8", "i9"}
    candidate = ([dict(r) for r in cases["noise"] if r["id"] not in gone]
                 + [{"id": f"x{i}", "tenant": "A", "passed": True,
                     "latency_ms": 100} for i in range(10)])
    out = s.gate(baseline, candidate, floors=floors)
    assert out["n_paired"] == 295 and out["n_dropped"] == 15, (
        f"paired {out['n_paired']}, dropped {out['n_dropped']}: five ids have no "
        f"partner and ten are new. The dropped count has to be in the report, "
        f"because 'the candidate ran on a different set' is the finding")
    assert _close(out["overall"]["n"] / 295, 1.0), (
        f"the rates are over the paired rows only: {out['overall']}")

    out = s.gate(baseline, cases["noise"][:1])       # no floors: isolate the rule
    assert out["decision"] == "inconclusive", (
        f"one paired row cannot support an interval: {out['overall']}")
    assert any("paired" in reason.lower() for reason in out["reasons"]), (
        f"{out['reasons']}")

    vanished = [r for r in cases["slices"] if r["tenant"] != "C"]
    out = s.gate(baseline, vanished, floors=floors)
    assert out["decision"] == "regress", (
        f"got {out['decision']}: tenant C is not in the candidate run at all. A "
        f"slice with a floor that stopped reporting has not met its floor, and "
        f"a gate that drops the row from the table and shrugs is how a "
        f"degraded tenant ships as a win")
    assert out["slices"]["C"]["breach"] is True

    result = s.gate(baseline, cases["noise"], floors=floors)
    text = s.report_json(result)
    assert text == s.report_json(result), "the report must be byte-identical between runs"
    decimals = [len(m.group(1)) for m in re.finditer(r"-?\d+\.(\d+)", text)]
    assert decimals and max(decimals) <= 4, (
        f"floats are rounded to 4 decimals so a CI diff shows change and not "
        f"float noise; found {max(decimals) if decimals else 0} decimals in: "
        f"{text[:300]}")
    assert "decision" in text and "inconclusive" in text


# --- 11. fields, not strings ------------------------------------------------

def check_11():
    import stage_11 as s

    schema = {
        "vendor": str,
        "amount": float,
        "line_items": [{"sku": str, "qty": int}],
    }
    gold = {"vendor": "Acme", "amount": 100.0,
            "line_items": [{"sku": "A", "qty": 2}, {"sku": "B", "qty": 1}]}

    # Typed coerce: a model-string amount must match a float gold.
    pred = {"vendor": "Acme", "amount": "100",
            "line_items": [{"sku": "A", "qty": 2}, {"sku": "B", "qty": 1}]}
    cells = s.compare_extraction(pred, gold, schema)
    assert all(c["status"] == "correct" for c in cells), (
        f"got {[(c['path'], c['status']) for c in cells]}: amount '100' under "
        f"a float schema is 100.0, not a string mismatch. Comparing with "
        f"Python equality before coerce is how every extraction harness "
        f"reports a false regression after json.loads on one side only")
    assert s.schema_valid(pred, schema), "coercible values are schema-valid"
    assert s.coerce("100", float) == 100.0
    assert s.coerce("2", int) == 2
    try:
        s.coerce(True, int)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "bool must not coerce to int: isinstance(True, int) is True in "
            "Python, and a model that sent true for a count would silently "
            "become 1")

    # Missing vs incorrect vs extra are three different statuses.
    pred_miss = {"vendor": "Acme", "amount": 100.0,
                 "line_items": [{"sku": "A", "qty": 2}, {"sku": "B"}]}
    cells = s.compare_extraction(pred_miss, gold, schema)
    by = {c["path"]: c["status"] for c in cells}
    assert by.get("line_items[1].qty") == "missing", (
        f"got {by}: a field the gold has and the pred omits is missing, not "
        f"incorrect — the fix is to emit it, not to edit a value")
    assert not s.schema_valid(pred_miss, schema), (
        "a missing required leaf is not schema-valid, even if the rest parses")

    pred_wrong = {"vendor": "Other", "amount": 100.0,
                  "line_items": [{"sku": "A", "qty": 2}, {"sku": "B", "qty": 1}],
                  "notes": "hallucinated"}
    cells = s.compare_extraction(pred_wrong, gold, schema)
    by = {c["path"]: c["status"] for c in cells}
    assert by.get("vendor") == "incorrect", f"{by}"
    assert by.get("notes") == "extra", (
        f"got {by}: a key the schema does not declare is extra. Ignoring "
        f"extras makes precision ignore hallucinations")
    micro = s.micro_scores(cells)
    # 5 correct (amount + 4 line fields), 1 incorrect vendor, 1 extra
    assert micro["tp"] == 5 and micro["fp"] == 2 and micro["fn"] == 1, (
        f"{micro}: incorrect counts as FP and FN; extra counts as FP only")
    assert _close(micro["precision"], 5 / 7) and _close(micro["recall"], 5 / 6), (
        f"{micro}")

    # Macro is dragged by a rare field; micro is not (many correct line cells).
    wide = {"vendor": str, "line_items": [{"sku": str}]}
    pairs = []
    for _ in range(2):
        g = {"vendor": "Acme",
             "line_items": [{"sku": f"S{j}"} for j in range(5)]}
        p = {"vendor": "WRONG",
             "line_items": [{"sku": f"S{j}"} for j in range(5)]}
        pairs.append((p, g))
    report = s.extraction_report(pairs, wide)
    assert report["n"] == 2
    assert report["macro_f1"] < report["micro"]["f1"] - 1e-9, (
        f"micro={report['micro']['f1']}, macro={report['macro_f1']}: with five "
        f"correct skus per doc and one wrong vendor, micro stays high and "
        f"macro averages the per-field F1s — vendor's 0 pulls it to 0.5. "
        f"Shipping micro alone is how a broken billing field hides")
    assert _close(report["macro_f1"], 0.5), f"{report['macro_f1']}"
    assert _close(report["schema_valid_rate"], 1.0), (
        f"{report['schema_valid_rate']}: wrong values can still be well-typed")

    # Empty pairs: defined, not a division by zero.
    empty = s.extraction_report([], schema)
    assert empty["n"] == 0 and _close(empty["macro_f1"], 1.0)

    try:
        s.compare_extraction({}, {}, ["not", "a", "dict"])
    except ValueError:
        pass
    else:
        raise AssertionError("a non-dict schema must raise")


# --- 12. confidence that earns its name ------------------------------------

def check_12():
    import stage_12 as s

    # Perfectly calibrated masses at 0.1 and 0.9.
    conf = [0.1] * 10 + [0.9] * 10
    ok = [True] + [False] * 9 + [True] * 9 + [False]
    assert _close(s.ece(conf, ok, n_bins=10), 0.0), (
        f"got {s.ece(conf, ok)}: ten rows at conf 0.1 with 10% accuracy and "
        f"ten at 0.9 with 90% accuracy is ECE 0. A non-zero here usually means "
        f"bins are unweighted (each bin counts as 1) or 1.0 fell off the end")

    # Overconfident: all say 0.9, half are right → ECE 0.4.
    conf2 = [0.9] * 10
    ok2 = [True] * 5 + [False] * 5
    assert _close(s.ece(conf2, ok2, n_bins=10), 0.4), (
        f"got {s.ece(conf2, ok2)}: |0.5 - 0.9| weighted by the whole mass is "
        f"0.4. Averaging |acc-conf| across all ten bins (nine of them empty) "
        f"gives 0.04 and green-lights a badly calibrated system")

    bins = s.reliability_bins([1.0, 1.0, 0.05], [True, False, False], n_bins=10)
    assert len(bins) == 10
    assert bins[-1]["count"] == 2 and _close(bins[-1]["accuracy"], 0.5), (
        f"{bins[-1]}: confidence 1.0 must land in the last bin. Half-open "
        f"[0.9, 1.0) drops it on the floor and silently shrinks N")
    assert bins[0]["count"] == 1 and _close(bins[0]["mean_conf"], 0.05)

    assert _close(s.ece([], [], n_bins=10), 0.0)
    try:
        s.ece([0.5, 1.5], [True, False])
    except ValueError:
        pass
    else:
        raise AssertionError("confidence outside [0,1] must raise")
    try:
        s.ece([0.5], [True, False])
    except ValueError:
        pass
    else:
        raise AssertionError("length mismatch must raise")

    # Review threshold: approve only the high-precision tail.
    conf3 = [0.5, 0.8, 0.95, 0.99]
    ok3 = [False, False, True, True]
    t = s.auto_approve_threshold(conf3, ok3, min_precision=0.99)
    assert _close(t, 0.95), (
        f"got {t}: at 0.95 the approved set is {{0.95, 0.99}} with precision "
        f"1.0; at 0.8 it includes two failures. The cut is the lowest "
        f"threshold that still meets the floor — so coverage is maximised")
    assert s.auto_approve_threshold(
        [0.9, 0.9], [True, False], min_precision=0.99) is None, (
        "when no cut meets the floor, return None — everything goes to review. "
        "Returning 1.0 and approving the empty set is a silent always-green")
    assert _close(s.auto_approve_threshold(
        [0.99, 0.99], [True, True], min_precision=0.99), 0.0), (
        "a fully correct set meets the floor at t=0.0: approve everything. "
        "Starting the sweep at the first confidence value would refuse to "
        "approve rows below that value for no reason")
    try:
        s.auto_approve_threshold([], [], min_precision=0.99)
    except ValueError:
        pass
    else:
        raise AssertionError("empty labelled set must raise")


# --- 13. the score that moves when the prompt's clothes move ----------------

def check_13():
    import stage_13 as s

    scores = {"colon": 0.91, "newline": 0.88, "bullet": 0.40}
    spread = s.format_spread(scores)
    assert spread["n"] == 3
    assert _close(spread["mean"], (0.91 + 0.88 + 0.40) / 3), f"{spread}"
    assert _close(spread["min"], 0.40) and _close(spread["max"], 0.91)
    assert _close(spread["range"], 0.51), (
        f"{spread}: the range is what the mean hides. A dashboard that only "
        f"shows 0.73 calls this system fine")
    assert spread["worst"] == "bullet" and spread["best"] == "colon", f"{spread}"
    assert not s.holds_under_formats(scores, 0.1), (
        "a 0.51 range does not hold under a 0.1 margin")
    assert s.holds_under_formats({"a": 0.5, "b": 0.5}, 0.0)

    # Ties pick the lexicographically first name — the rule has to be pinned.
    tied = s.format_spread({"b": 0.2, "a": 0.2, "c": 0.9})
    assert tied["worst"] == "a" and tied["best"] == "c", (
        f"{tied}: when two formats share the min, pick the lexicographically "
        f"first name, or the same data reports a different 'worst' tomorrow")

    try:
        s.format_spread({})
    except ValueError:
        pass
    else:
        raise AssertionError(
            "a spread over no formats must raise — returning zeros invents a "
            "measurement")

    # Criteria identity: order and casing must not change the fingerprint.
    a = s.criteria_id(["Must cite page", "Amount is a number"])
    b = s.criteria_id(["amount is a number", "must cite page"])
    c = s.criteria_id(["Must cite page", "Amount is a number", "extra"])
    assert a == b, (
        f"{a} vs {b}: criteria_id sorts and normalises, or declaring the same "
        f"rubric in a different order looks like criteria drift (EvalGen) and "
        f"blocks every comparison")
    assert a != c, "adding a criterion must change the id"
    assert s.comparable({"criteria_id": a, "score": 0.9},
                        {"criteria_id": b, "score": 0.4}) is True
    assert s.comparable({"criteria_id": a}, {"criteria_id": c}) is False
    try:
        s.comparable({"score": 1.0}, {"criteria_id": a})
    except ValueError:
        pass
    else:
        raise AssertionError(
            "a run without criteria_id must raise, not compare equal to "
            "another unversioned run — that is how drift stays invisible")


STAGES = [
    stage(
        1, file="stage_01.py", title="the eval set, and the split that must not leak",
        tags=["datasets", "leakage"],
        action=("Implement load() with validation and copies, and split() that "
                "keeps whole groups on one side of the split, seeded."),
        predict="10 groups of 3 rows, ratios 0.6/0.2/0.2: how many rows in train?",
        hints=["shuffle the GROUPS, then fill the splits to their target sizes",
               "a random row split puts five phrasings of one ticket on both "
               "sides of the line"],
        check=check_1, solution="solutions/stage_01.py: split"),
    stage(
        2, file="stage_02.py", title="the numbers that are not about quality",
        tags=["metrics", "operations"],
        action=("Implement refusal_rate, latency_summary (nearest-rank "
                "percentiles), token_summary and operational_report."),
        predict="20 latencies, 10..200: what is p95 by nearest rank?",
        hints=["an errored row is not a refusal — keep it out of that denominator",
               "p95 is the sample at ceil(0.95 * n) - 1, not an interpolation"],
        check=check_2, solution="solutions/stage_02.py: latency_summary"),
    stage(
        3, file="stage_03.py", title="deterministic assertions",
        tags=["assertions", "error-handling"],
        action=("Implement check/json_valid/has_fields/run_checks/summarise "
                "with three outcome states, and errors that never become passes."),
        predict="A predicate raises on record 1 of 2, with 4 checks: pass rate?",
        hints=["try/except: pass around the loop is how every broken check "
               "turns green",
               "a truthy non-tuple is not a pass — the report needs the reason"],
        check=check_3, solution="solutions/stage_03.py: run_checks"),
    stage(
        4, file="stage_04.py", title="exact match and token F1",
        tags=["metrics", "normalisation"],
        action=("Implement normalize (SQuAD-style), exact_match, token_f1 with "
                "a multiset overlap, corpus_f1 pooled and mean_f1 per pair."),
        predict="F1 of prediction 'cat sat' against gold 'cat'?",
        hints=["normalise both sides, always, in one place",
               "0/0 is not a perfect answer; empty scores 0.0"],
        check=check_4, solution="solutions/stage_04.py: corpus_f1"),
    stage(
        5, file="stage_05.py", title="ranking metrics, and the ideal that is not ideal",
        tags=["retrieval", "metrics"],
        action=("Implement recall_at_k, mrr, dcg and ndcg with the IDCG over "
                "every judged document, not over the retrieved pool."),
        predict="Retrieved gains [1,1] when a 3-gain document exists: nDCG?",
        hints=["IDCG sorts ALL keys in the relevance map by gain",
               "a key the map does not mention has gain 0"],
        check=check_5, solution="solutions/stage_05.py: ndcg"),
    stage(
        6, file="stage_06.py", title="the judge, and the order you showed it in",
        tags=["judge", "bias"],
        action=("Implement run_pairwise: judge every pair twice, in both "
                "orders, and report the debiased win rate and the flip rate."),
        predict="A judge that always answers 'first': what win rate does the "
                "swapped run report?",
        hints=["each judged order contributes half a win to each side",
               "a flip is the same answer winning in both orders"],
        check=check_6, solution="solutions/stage_06.py: run_pairwise"),
    stage(
        7, file="stage_07.py", title="what the judge is worth",
        tags=["calibration", "statistics"],
        action=("Implement confusion, agreement, cohen_kappa and threshold_for, "
                "sweeping the pass/fail cut by F1 on the labelled set."),
        predict="A judge that always says pass, on a set that is 85% passes: kappa?",
        hints=["kappa subtracts the agreement chance would give",
               "the threshold trades false passes against false failures"],
        check=check_7, solution="solutions/stage_07.py: cohen_kappa"),
    stage(
        8, file="stage_08.py", title="is the difference real?",
        tags=["statistics", "significance"],
        action=("Implement binom_two_sided, mcnemar, paired_bootstrap, "
                "independent_ci and decide — paired, with three outcomes."),
        predict="Same data, paired and independent intervals: which is narrower?",
        hints=["resample ITEMS, both systems together",
               "an interval containing zero is not a win"],
        check=check_8, solution="solutions/stage_08.py: paired_bootstrap"),
    stage(
        9, file="stage_09.py", title="ten configs, one winner, no correction",
        tags=["statistics", "multiple-comparisons"],
        action=("Implement holm (with the running maximum) and significant "
                "(step-down thresholds) over a family of p-values."),
        predict="p=0.04 as 1 test, and as the best of 10: significant?",
        hints=["adjusted_i = max(adjusted_{i-1}, p_i * (m - i + 1))",
               "the family is decided before the p-values are read"],
        check=check_9, solution="solutions/stage_09.py: holm"),
    stage(
        10, file="stage_10.py", title="the gate, and the report you can diff",
        tags=["regression", "decisions"],
        action=("Implement gate: match by id, per-slice floors, a paired "
                "interval, three decisions with reasons, and a stable JSON."),
        predict="Better overall, one tenant halved: what does the gate say?",
        hints=["a floor breach decides the run whatever the mean says",
               "rows without a partner are dropped and counted, never paired "
               "by position"],
        check=check_10, solution="solutions/stage_10.py: gate"),
    stage(
        11, file="stage_11.py", title="fields, not strings",
        tags=["extraction", "structured", "metrics"],
        action=("Implement coerce, compare_extraction (correct/incorrect/"
                "missing/extra), micro_scores, macro_f1, schema_valid and "
                "extraction_report over a typed schema."),
        predict="Five correct line-item cells and one wrong vendor: micro vs macro F1?",
        hints=["coerce through the schema before comparing — '100' is 100.0",
               "incorrect is both FP and FN; extra is FP only; missing is FN only",
               "macro averages per-field-name F1 with list indices collapsed to [*]"],
        check=check_11, solution="solutions/stage_11.py: compare_extraction"),
    stage(
        12, file="stage_12.py", title="confidence that earns its name",
        tags=["calibration", "ece", "confidence"],
        action=("Implement reliability_bins, ece (count-weighted) and "
                "auto_approve_threshold under a precision floor."),
        predict="All confidences 0.9, half correct, 10 bins: ECE?",
        hints=["ECE weights each bin by n_b/N — empty bins must not dilute it",
               "confidence 1.0 belongs in the last bin, not off the end",
               "the threshold is the lowest cut that still meets min_precision"],
        check=check_12, solution="solutions/stage_12.py: ece"),
    stage(
        13, file="stage_13.py",
        title="the score that moves when the prompt's clothes move",
        tags=["sensitivity", "criteria", "validity"],
        action=("Implement format_spread, holds_under_formats, criteria_id "
                "(order-independent) and comparable."),
        predict="Scores 0.91 / 0.88 / 0.40 across three formats: what does the mean hide?",
        hints=["report the range and the worst format, not only the mean",
               "criteria_id sorts and normalises, or declaration order looks like drift"],
        check=check_13, solution="solutions/stage_13.py: format_spread"),
]
