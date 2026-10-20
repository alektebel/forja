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
    raise NotImplementedError("stage 53: implement cures()")







































































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