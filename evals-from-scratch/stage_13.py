"""Evals From Scratch — stage 13: the score that moves when the prompt's clothes move

DESIGN DECISION — report the range, not only the mean.
    The mean across prompt formats is what a dashboard shows. The range (and
    the worst format's name) is what tells you the result was about the task
    rather than about a semicolon.

DESIGN DECISION — criteria identity is part of comparability.
    When the rubric drifts, yesterday's score is no longer about today's
    question. criteria_id fingerprints the normalised, sorted criteria;
    comparable refuses a delta across different fingerprints.

TODO: implement

    format_spread(scores_by_format) -> dict
        scores_by_format: {format_name: score}.
        Returns {n, mean, min, max, range, std, worst, best}.
        worst/best are format names; ties → lexicographically first.
        Empty dict → ValueError. std is the population stdev.

    holds_under_formats(scores_by_format, margin) -> bool
        True iff max - min <= margin. margin < 0 → ValueError.

    criteria_id(criteria) -> str
        SHA-256 hex over sorted whitespace-normalised lowercased strings.
        Order of declaration must not matter.

    comparable(run_a, run_b) -> bool
        True iff both dicts share the same criteria_id.
        Missing criteria_id → ValueError (not False).
"""


def format_spread(scores_by_format):
    raise NotImplementedError("stage 13: implement format_spread()")


def holds_under_formats(scores_by_format, margin):
    raise NotImplementedError("stage 13: implement holds_under_formats()")


def criteria_id(criteria):
    raise NotImplementedError("stage 13: implement criteria_id()")


def comparable(run_a, run_b):
    raise NotImplementedError("stage 13: implement comparable()")
