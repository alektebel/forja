"""Collections Workout From Scratch — stage 5: Cure rate and re-default.

The bank's own forbearance grants produce cures when the borrower clears the
default during probation. A cure that arrives before the probation ends does
not count (the default stays), and a re-default within `REDEFAULT_MONTHS` of
a cure is the borrower re-defaulting, not a fresh default.

This stage cohorts the cures by quarter, counts how many stayed cured and how
many re-defaulted, and answers the cure rate in basis points. A cohort of one
or two loans is an anecdote — the desk refuses to publish one, and this stage
does the same, raising `MeasureError` when the cohort is too small.

    MeasureError             the refusal this stage raises
    COHORT_KEYS              the seven fields of one cohort row, in order
    cures(book)              -> the cohort table: per-quarter cure stats

DESIGN DECISION — why cohort by quarter?
Because the desk's own reporting is quarterly, and a cure rate over a partial
quarter would not be comparable.

DESIGN DECISION — why does a re-default within `REDEFAULT_MONTHS` count as
re-default rather than a fresh default?
Because the policy's own `REDEFAULT_MONTHS` is the gap that distinguishes the
same loan's relapse from a new borrower's first default.

TODO: implement `MeasureError`, `COHORT_KEYS` and `cures` in this file:
the quarterly cohorts, cure counts, re-default counts, and the cure rate.

    A refusal happens when the cohort is too small.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules

COHORT_KEYS = ("quarter", "probations_started", "cures_observed", "re_defaults",
               "cure_rate_bp", "cohort_size")


class MeasureError(ValueError):
    """The refusal this stage raises: a cohort too small to publish.

    It names the offender — the quarter with too few loans — because a cure rate
    over one or two loans is an anecdote, and the desk refuses anecdotes.
    """


def cures(book):
    """The cure rate table: one row per quarter of the bank's forbearance activity.

    Cohorts are computed from `workout.py`'s GRANTS table: for each quarter,
    the number of forbearance grants (probations started), the number of cures
    observed (defaults that validly cured during the probation), the number of
    re-defaults (defaults signalled within `REDEFAULT_MONTHS` of a cure), and
    the cure rate in basis points: `cures * 10000 // (cures + re_defaults)`,
    truncated. A cohort of fewer than `col.MIN_COHORT` loans raises
    `MeasureError` naming the quarter.

    `REDEFAULT_MONTHS` from the collections world is the divider: a default
    within that many months of a cure is a re-default, not a fresh default.
    """
    grants = col.GRANTS
    if not grants:
        return ()

    # Group grants by quarter
    quarters = {}
    for grant in grants:
        q = _quarter(grant["granted_on"])
        if q not in quarters:
            quarters[q] = {"probations": 0, "cures": 0, "re_defaults": 0, "loans": set()}
        quarters[q]["probations"] += 1
        quarters[q]["loans"].add(grant["loan"])

    # Count cures from defaults
    defaults = book.defaults()
    for default in defaults:
        if default["cured_on"] is not None:
            q = _quarter(default["cured_on"])
            if q in quarters:
                quarters[q]["cures"] += 1

    # Count re-defaults: defaults signalled within REDEFAULT_MONTHS after a cure
    for default in defaults:
        if default["cured_on"] is not None:
            # Find if this loan had a later default within REDEFAULT_MONTHS of cure
            prob_until = dates.add_months(default["cured_on"], col.REDEFAULT_MONTHS)
            for other in defaults:
                if other["loan"] == default["loan"] and other["signalled_on"] > default["cured_on"]:
                    if other["signalled_on"] <= prob_until:
                        q = _quarter(other["signalled_on"])
                        if q in quarters:
                            quarters[q]["re_defaults"] += 1
                        break

    rows = []
    for q in sorted(quarters.keys()):
        data = quarters[q]
        cohort_size = data["probations"]
        if cohort_size < col.MIN_COHORT:
            raise MeasureError(
                "the quarter %s has %d loans, fewer than %d"
                % (q, cohort_size, col.MIN_COHORT))
        cures_observed = data["cures"]
        re_defaults = data["re_defaults"]
        if cures_observed + re_defaults > 0:
            cure_rate_bp = cures_observed * rules.DISCOUNT_SCALE // (cures_observed + re_defaults)
        else:
            cure_rate_bp = rules.DISCOUNT_SCALE  # 100% if no failures
        rows.append({
            "quarter": q,
            "probations_started": data["probations"],
            "cures_observed": cures_observed,
            "re_defaults": re_defaults,
            "cure_rate_bp": cure_rate_bp,
            "cohort_size": cohort_size,
        })
    return tuple(rows)


def _quarter(date):
    """The quarter string for a date: YYYY-Qn."""
    year, month, _day = dates.parse(date)
    q = (month - 1) // 3 + 1
    return "%d-Q%d" % (year, q)


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 5 — cure rates")
    try:
        cohort_table = cures(book)
        print("  quarter  probations  cures  re-defaults  rate_bp  size")
        for row in cohort_table:
            print("  %-7s %-10d %-5d %-11d %-7d %d"
                  % (row["quarter"], row["probations_started"], row["cures_observed"],
                     row["re_defaults"], row["cure_rate_bp"], row["cohort_size"]))
    except MeasureError as error:
        print("  refused: %s" % (error,))