"""Evals From Scratch — stage 13: the score that moves when the prompt's clothes move

Format sensitivity: hold the task and the model fixed, vary only the surface
of the prompt (separators, casing, option order), and measure how far the
score travels. A mean that looks fine can hide a collapse on one formatting.

Cite: Sclar et al., "Quantifying Language Models' Sensitivity to Spurious
Features in Prompt Design" (arxiv 2310.11324). Related product practice from
Hamel's field guide: when you change the prompt wrapper, re-run the eval —
the number is not invariant.

DESIGN DECISION — report the range, not only the mean.
    The mean across formats is what a dashboard shows. The range (and the
    identity of the worst format) is what tells you the result was about the
    task rather than about a semicolon. A check that only pins the mean
    greenlights a system that scores 0.9 / 0.9 / 0.2.

DESIGN DECISION — criteria identity is part of comparability.
    Shankar et al. (EvalGen) document criteria drift: the rubric moves as
    humans iterate, and yesterday's score is no longer about today's question.
    `criteria_id` is a stable fingerprint; `comparable` refuses to treat two
    runs as a delta when the fingerprint differs. The hash is over the sorted
    normalised criterion strings — order of declaration must not matter.
"""

from __future__ import annotations

import hashlib
import math
import re


def format_spread(scores_by_format):
    """Summary of a dict {format_name: score}.

    Returns {"n", "mean", "min", "max", "range", "std", "worst", "best"}.
    `worst` / `best` are the format names (ties → lexicographically first).
    Empty input raises ValueError: a spread over no formats is not 0, it is
    undefined.
    """
    if not isinstance(scores_by_format, dict):
        raise ValueError("scores_by_format must be a dict")
    if not scores_by_format:
        raise ValueError("no formats: a spread over nothing is undefined")
    items = [(name, float(score)) for name, score in scores_by_format.items()]
    values = [s for _, s in items]
    n = len(values)
    mean = sum(values) / n
    lo = min(values)
    hi = max(values)
    var = sum((v - mean) ** 2 for v in values) / n  # population std
    std = math.sqrt(var)
    # ties: lexicographically first among those at the extreme
    worst = sorted(name for name, s in items if s == lo)[0]
    best = sorted(name for name, s in items if s == hi)[0]
    return {
        "n": n,
        "mean": mean,
        "min": lo,
        "max": hi,
        "range": hi - lo,
        "std": std,
        "worst": worst,
        "best": best,
    }


def holds_under_formats(scores_by_format, margin):
    """True iff max(score) - min(score) <= margin."""
    if margin < 0:
        raise ValueError("margin must be >= 0")
    spread = format_spread(scores_by_format)
    return spread["range"] <= margin


def _normalise_criterion(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def criteria_id(criteria):
    """Stable fingerprint of an iterable of criterion strings.

    Order-independent: sorted after normalisation. Empty criteria are allowed
    and hash to a defined value (the empty set is a rubric — a bad one).
    """
    parts = sorted(_normalise_criterion(c) for c in criteria)
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def comparable(run_a, run_b):
    """True iff both runs carry the same criteria_id.

    Each run is a dict that must contain "criteria_id". Missing key →
    ValueError (silent False would let an unversioned run compare equal to
    another unversioned run and hide the drift).
    """
    if "criteria_id" not in run_a:
        raise ValueError("run_a has no criteria_id")
    if "criteria_id" not in run_b:
        raise ValueError("run_b has no criteria_id")
    return run_a["criteria_id"] == run_b["criteria_id"]


if __name__ == "__main__":
    scores = {"colon": 0.91, "newline": 0.88, "bullet": 0.40}
    print(format_spread(scores))
    print("holds@0.1:", holds_under_formats(scores, 0.1))
    c1 = criteria_id(["Must cite page", "Amount is a number"])
    c2 = criteria_id(["amount is a number", "must cite page"])
    print("same criteria:", c1 == c2)
    print("comparable:", comparable({"criteria_id": c1}, {"criteria_id": c2}))
