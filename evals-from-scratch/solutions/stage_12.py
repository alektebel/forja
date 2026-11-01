"""Evals From Scratch — stage 12: confidence that earns its name

Expected Calibration Error and the review threshold. Stage 7 swept a judge's
ordinal score for F1; this stage asks whether a *probability* the system
emits (field confidence, pass probability) means what it says on the tin.

Cite: Naeini et al. / Guo et al. on ECE; Anyformat's field-level calibrated
confidence (threshold → auto-approve vs human review). Hamel's field guide:
the confidence number is only useful if you measured calibration on labels.

DESIGN DECISION — weight bins by count, not by bin.
    Unweighted mean of |acc - conf| over bins lets an empty-ish bin of three
    overconfident rows cancel a well-calibrated mass of three thousand.
    ECE is Σ (n_b / N) |acc_b - conf_b|.

DESIGN DECISION — equal-width bins on [0, 1], last bin closed.
    Bin i is [i/B, (i+1)/B) for i < B-1, and [1-1/B, 1] for the last. A
    confidence of exactly 1.0 must land somewhere; half the buggy ECEs drop it.

DESIGN DECISION — the review threshold maximises auto-approve coverage
    under a precision floor.
    Sweep confidences as candidate cuts; keep rows with conf >= t as
    auto-approved; require precision of that subset >= min_precision; pick
    the lowest such t (most coverage). Ties on precision go to more coverage.
"""

from __future__ import annotations


def reliability_bins(confidences, correct, n_bins=10):
    """Equal-width reliability diagram bins.

    `confidences` are floats in [0, 1]; `correct` are booleans, same length.
    Returns a list of n_bins dicts:
        {"lo", "hi", "count", "mean_conf", "accuracy"}
    Empty bins have count 0, mean_conf/accuracy 0.0.
    """
    confidences = list(confidences)
    correct = list(correct)
    if len(confidences) != len(correct):
        raise ValueError(
            f"{len(confidences)} confidences against {len(correct)} labels")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    for c in confidences:
        if not (0.0 <= c <= 1.0):
            raise ValueError(f"confidence {c!r} is outside [0, 1]")

    bins = [{"lo": i / n_bins,
             "hi": (i + 1) / n_bins,
             "count": 0,
             "mean_conf": 0.0,
             "accuracy": 0.0,
             "_sum_conf": 0.0,
             "_sum_correct": 0} for i in range(n_bins)]

    for conf, ok in zip(confidences, correct):
        if conf == 1.0:
            idx = n_bins - 1
        else:
            idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx]["count"] += 1
        bins[idx]["_sum_conf"] += conf
        bins[idx]["_sum_correct"] += int(bool(ok))

    out = []
    for b in bins:
        n = b["count"]
        out.append({
            "lo": b["lo"], "hi": b["hi"], "count": n,
            "mean_conf": (b["_sum_conf"] / n) if n else 0.0,
            "accuracy": (b["_sum_correct"] / n) if n else 0.0,
        })
    return out


def ece(confidences, correct, n_bins=10):
    """Expected Calibration Error: Σ (n_b / N) |acc_b - conf_b|.

    Returns 0.0 on an empty input (no evidence of miscalibration, and no
    evidence of calibration either — callers with no labels should not be
    here).
    """
    confidences = list(confidences)
    correct = list(correct)
    if not confidences:
        return 0.0
    bins = reliability_bins(confidences, correct, n_bins=n_bins)
    n = len(confidences)
    return sum(
        (b["count"] / n) * abs(b["accuracy"] - b["mean_conf"])
        for b in bins
    )


def auto_approve_threshold(confidences, correct, min_precision=0.99):
    """Lowest confidence cut whose auto-approved subset meets min_precision.

    Auto-approve = rows with confidence >= threshold. Precision = fraction
    correct among them. Among cuts that meet the floor, pick the lowest
    threshold (largest coverage). If none meet it — including the full set —
    return None (everything goes to review).

    Candidate thresholds are the unique confidence values, plus 0.0 so a
    well-calibrated set can approve everything.
    """
    confidences = list(confidences)
    correct = [bool(x) for x in correct]
    if len(confidences) != len(correct):
        raise ValueError(
            f"{len(confidences)} confidences against {len(correct)} labels")
    if not confidences:
        raise ValueError("no labelled rows to choose a threshold from")
    if not (0.0 < min_precision <= 1.0):
        raise ValueError("min_precision must be in (0, 1]")

    candidates = sorted(set([0.0] + confidences))
    best_t = None
    best_coverage = -1
    n = len(confidences)
    for t in candidates:
        approved = [(c, ok) for c, ok in zip(confidences, correct) if c >= t]
        if not approved:
            continue
        precision = sum(ok for _, ok in approved) / len(approved)
        if precision + 1e-15 < min_precision:
            continue
        coverage = len(approved) / n
        if best_t is None or coverage > best_coverage or (
                abs(coverage - best_coverage) < 1e-15 and t < best_t):
            best_t = t
            best_coverage = coverage
    return best_t


if __name__ == "__main__":
    # Perfectly calibrated: conf 0.1 .. with 10% accuracy in that mass
    conf = [0.1] * 10 + [0.9] * 10
    ok = [True] + [False] * 9 + [True] * 9 + [False]
    print("ece (should be ~0):", round(ece(conf, ok, n_bins=10), 6))
    # Overconfident
    conf2 = [0.9] * 10
    ok2 = [True] * 5 + [False] * 5
    print("ece overconfident:", round(ece(conf2, ok2, n_bins=10), 6))
    print("threshold@0.99:", auto_approve_threshold(
        [0.5, 0.8, 0.95, 0.99], [False, False, True, True], 0.99))
