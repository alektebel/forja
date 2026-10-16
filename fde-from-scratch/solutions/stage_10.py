"""stage_10.py — the solution for stage 10: shadow traffic and a verdict."""

import estate

CASE_KEYS = ("id", "team", "text", "expected", "class")

SHADOW_KEYS = ("id", "incumbent", "candidate", "user_sees", "same")

GRADE_KEYS = ("model", "correct", "total", "accuracy_bp")

AGREEMENT_KEYS = ("agree", "disagree", "agreement_bp")

VERDICTS = ("ship", "hold", "reject")

VERDICT_REASONS = ("below-target", "judge-unreliable", "sample-too-small",
                   "candidate-worse")

MIN_SAMPLE = 30

MIN_AGREEMENT_BP = 8000

_MODELS = ("incumbent", "candidate")


class EvalError(estate.EstateError):
    """An eval this course cannot run: a shape that is not the shape it takes."""


def _record(value, keys, what):
    """`value` as a mapping carrying exactly `keys`, or a refusal naming the offender."""
    if not isinstance(value, dict):
        raise EvalError("%s is a mapping of %r, not a %s"
                        % (what, keys, type(value).__name__))
    for key in keys:
        if key not in value:
            raise EvalError("%s has no %r, and it carries %r"
                            % (what, key, sorted(value)))
    extra = tuple(key for key in value if key not in keys)
    if extra:
        raise EvalError("%s carries %r, which is not of %r" % (what, extra, keys))
    return value


def _tuple(value, what):
    """`value` as a tuple, or a refusal naming what arrived in its place."""
    if not isinstance(value, tuple):
        raise EvalError("%s is a tuple, and it is a %s"
                        % (what, type(value).__name__))
    return value


def _text(value, what):
    """`value` as a string, or a refusal naming what arrived in its place."""
    if not isinstance(value, str):
        raise EvalError("%s is text, and it is a %s" % (what, type(value).__name__))
    return value


def _int(value, what):
    """`value` as an int count, or a refusal naming what arrived in its place."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise EvalError("%s is an int count, and it is a %s"
                        % (what, type(value).__name__))
    return value


def shadow(cases, incumbent, candidate, replay):
    """Two models on the customer's own cases, and what the user actually saw.

    `cases` is a tuple of `CASE_KEYS` records; `incumbent`, `candidate` and
    `replay` are callables taking a case's `text` and answering a string, or
    `None` for a model that did not answer that case. The row's `incumbent` and
    `candidate` are those two answers, `user_sees` is `replay`'s and never the
    candidate's, and `same` says whether the two models gave the same answer.
    """
    _tuple(cases, "cases")
    rows = []
    for case in cases:
        _record(case, CASE_KEYS, "a case")
        text = _text(case["text"], "the case %r's text" % (case["id"],))
        first = incumbent(text)
        second = candidate(text)
        seen = replay(text)
        rows.append({"id": case["id"], "incumbent": first, "candidate": second,
                     "user_sees": seen, "same": first == second})
    return tuple(rows)


def grade(rows, cases):
    """The two models' marks on the customer's cases, sorted by model.

    The denominator is what a model *answered*: a case whose answer is `None`
    is not in that model's `total`, and a model that answered nothing is
    `total` 0 and `accuracy_bp` 0 rather than a division by nothing.
    """
    _tuple(rows, "rows")
    _tuple(cases, "cases")
    wanted = {}
    for case in cases:
        _record(case, CASE_KEYS, "a case")
        wanted[case["id"]] = case["expected"]
    graded = []
    for model in _MODELS:
        correct = 0
        total = 0
        for row in rows:
            _record(row, SHADOW_KEYS, "a shadow row")
            if row["id"] not in wanted:
                raise EvalError("a shadow row answers the case %r, which the "
                                "labelled sample does not hold" % (row["id"],))
            answer = row[model]
            if answer is None:
                continue
            total += 1
            if answer == wanted[row["id"]]:
                correct += 1
        graded.append({"model": model, "correct": correct, "total": total,
                       "accuracy_bp": 0 if total == 0 else correct * 10000 // total})
    return tuple(sorted(graded, key=lambda record: record["model"]))


def calibrate(judge, labelled):
    """How far the judge can be trusted, against a sample a human labelled.

    `judge` is a callable taking a case's `text` and answering the label it
    believes; `labelled` is a tuple of `CASE_KEYS` records whose `expected` is
    the human's own label, and there is nothing to agree with a case that
    carries no label. A verdict the judge did not give is not agreement.
    """
    _tuple(labelled, "labelled")
    agree = 0
    disagree = 0
    for case in labelled:
        _record(case, CASE_KEYS, "a labelled case")
        if case["expected"] is None:
            raise EvalError("the labelled case %r carries no label to agree with"
                            % (case["id"],))
        if judge(case["text"]) == case["expected"]:
            agree += 1
        else:
            disagree += 1
    total = agree + disagree
    return {"agree": agree, "disagree": disagree,
            "agreement_bp": 0 if total == 0 else agree * 10000 // total}


def verdict(grades, agreement, sample, target_bp):
    """The one-word answer, with the reason it is that word.

    The instrument is judged before the measurement: a judge below
    `MIN_AGREEMENT_BP` and a sample below `MIN_SAMPLE` each answer `hold`, in
    that order, and neither of them ever reaches the target. Only then is the
    candidate measured against `target_bp` — at the target it ships, below it
    it is `reject`, and which reason it carries depends on whether the
    incumbent was at the target the candidate missed.
    """
    _tuple(grades, "grades")
    _record(agreement, AGREEMENT_KEYS, "the agreement")
    _int(sample, "sample")
    _int(target_bp, "target_bp")
    scored = {}
    for record in grades:
        _record(record, GRADE_KEYS, "a grade")
        if record["model"] not in _MODELS:
            raise EvalError("%r is not a model this verdict decides about: %r"
                            % (record["model"], _MODELS))
        if record["model"] in scored:
            raise EvalError("the model %r is graded twice" % (record["model"],))
        scored[record["model"]] = record
    for model in _MODELS:
        if model not in scored:
            raise EvalError("there is no grade for the %s, so nothing is decided"
                            % (model,))
    if agreement["agreement_bp"] < MIN_AGREEMENT_BP:
        return ("hold", "judge-unreliable")
    if sample < MIN_SAMPLE:
        return ("hold", "sample-too-small")
    candidate = scored["candidate"]["accuracy_bp"]
    incumbent = scored["incumbent"]["accuracy_bp"]
    if candidate < target_bp:
        if incumbent >= target_bp:
            return ("reject", "candidate-worse")
        return ("reject", "below-target")
    return ("ship", None)


def user_visible(rows):
    """`(case id, answer)` per case, in the cases' own order: what the user saw.

    The answer is the shadow row's `user_sees` — the replay's, never the
    candidate's: the whole point of shadow traffic is that the candidate's
    answer is measured and discarded, not served.
    """
    _tuple(rows, "rows")
    seen = []
    for row in rows:
        _record(row, SHADOW_KEYS, "a shadow row")
        seen.append((row["id"], row["user_sees"]))
    return tuple(seen)
