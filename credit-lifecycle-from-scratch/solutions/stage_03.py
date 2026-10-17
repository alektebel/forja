"""Credit Lifecycle From Scratch — stage 3: The migration matrix, the term structure and the lifetime PD.

Two dates of the book, the grades the bank recorded for its loans in between, and the
three answers every later stage asks this one for: the migration matrix, the term
structure it walks, and the cumulative PD the walk ends on. The matrix is rebuilt from
`book.grade` — one ask per loan per date — so it is a computation and not a lookup;
every row sums to exactly `10000`, because the `default` column carries the remainder
of the row's other divisions; and the walk is survival arithmetic, so the mass that
defaulted in month two is not at risk in month three.
"""

import rules
from book import BookError

MATRIX_KEYS = ("from_date", "to_date", "grades", "counts", "rates_bp", "row_totals")

PD_KEYS = ("grade", "horizon_months", "marginal_bp", "cumulative_bp")

GRADES = rules.GRADES

_DEFAULT = "default"


def _covered(dates, date):
    """Refuse a date the book does not cover, naming it, before a single loan is asked for."""
    if date not in dates:
        raise BookError("stage 3: %r is not a reporting date of the book" % (date,))


def _known(grade, what):
    """Refuse a grade the scale does not hold, naming the grade and where it came from."""
    if grade not in GRADES:
        raise BookError("stage 3: %r is not a grade of the scale, in %s" % (grade, what))
    return grade


def _matrix_of(matrix):
    """The grades, counts and row totals `matrix` holds, or the refusal naming what is wrong.

    A matrix is a `MATRIX_KEYS` record over grades of the scale, and it has to hold
    a `default` column — the column the remainder of every row is given to.
    """
    if not isinstance(matrix, dict):
        raise BookError("stage 3: a migration matrix is a mapping, and %r is not"
                        % (matrix,))
    for key in MATRIX_KEYS:
        if key not in matrix:
            raise BookError("stage 3: the matrix has no %r field" % (key,))
    grades = tuple(matrix["grades"])
    if not grades:
        raise BookError("stage 3: the matrix holds no grades")
    for grade in grades:
        _known(grade, "the matrix's grades")
    if _DEFAULT not in grades:
        raise BookError("stage 3: the matrix has no %r column to absorb the remainder"
                        % (_DEFAULT,))
    counts = matrix["counts"]
    for pair in counts:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise BookError("stage 3: the matrix counts the pair %r" % (pair,))
        if pair[0] not in grades or pair[1] not in grades:
            raise BookError("stage 3: the matrix counts the pair %r, which its grades "
                            "do not hold" % (pair,))
    return grades, counts, matrix["row_totals"]


def migration(book, start, end):
    """The grade movements the book itself observed between `start` and `end`.

    One row per grade in `GRADES` and one column per grade reached: `counts` is
    keyed by the `(from_grade, to_grade)` pair, only for the pairs a loan actually
    made, and `row_totals` holds every row's total, including the rows of grades no
    loan sat in. Every loan of the book is counted — the bank's grade record is
    total over the reporting dates, origination and write-off included — and the
    pair is the grade at `start` against the grade at `end`, so a loan the bank had
    already defaulted at `start` counts in `("default", "default")` while it stays
    defaulted and leaves the column only if the book re-rated it.
    """
    dates = tuple(book.reporting_dates)
    _covered(dates, start)
    _covered(dates, end)
    totals = {}
    for grade in GRADES:
        totals[grade] = 0
    counts = {}
    for loan in book.loans:
        came = _known(book.grade(loan, start), "the book's record at %s" % (start,))
        went = _known(book.grade(loan, end), "the book's record at %s" % (end,))
        pair = (came, went)
        counts[pair] = counts.get(pair, 0) + 1
        totals[came] = totals[came] + 1
    matrix = {"from_date": start, "to_date": end, "grades": GRADES,
              "counts": counts, "rates_bp": (), "row_totals": totals}
    matrix["rates_bp"] = rates(matrix)
    return matrix


def rates(matrix):
    """The rows of `matrix` in basis points, one row per grade in `matrix["grades"]`.

    Every cell is `count * 10000 // row_total`, truncated, and the `default` column
    is what the row's other divisions left: `10000` less their sum, so the row sums
    to exactly `10000`. A row with no loans is the same absorb-the-rest row with no
    divisions in it at all — `default` gets `10000` and every other column zero.
    """
    grades, counts, totals = _matrix_of(matrix)
    place = grades.index(_DEFAULT)
    rows = []
    for came in grades:
        total = totals.get(came, 0)
        if total <= 0:
            row = [0] * len(grades)
            row[place] = 10000
            rows.append(tuple(row))
            continue
        row = []
        spent = 0
        for grade in grades:
            if grade == _DEFAULT:
                row.append(0)
                continue
            bp = counts.get((came, grade), 0) * 10000 // total
            spent = spent + bp
            row.append(bp)
        row[place] = 10000 - spent
        rows.append(tuple(row))
    return tuple(rows)


def term_structure(matrix, grade, months):
    """The PD term structure of `grade` over `months` monthly steps.

    One `PD_KEYS` row per step, `horizon_months` counting from 1. The walk carries
    the distribution of the loans that are still alive and every product is
    truncated (`(a * b) // 10000`); the mass that reaches `default` is counted in
    the marginal and never carried forward, because `default` absorbs. So
    `marginal_bp` is the flow *into* `default` at that step — what landed there
    from the grades that are still alive, not what was already there — and
    `cumulative_bp` is the running sum of those marginals, which never falls and
    never passes `10000`. A walk that starts in `default` has already defaulted:
    its cumulative is `10000` and nothing more lands.
    """
    grades, counts, totals = _matrix_of(matrix)
    if grade not in GRADES:
        raise BookError("stage 3: %r is not a grade of the scale" % (grade,))
    if grade not in grades:
        raise BookError("stage 3: the matrix has no %r row" % (grade,))
    if isinstance(months, bool) or not isinstance(months, int) or months < 0:
        raise BookError("stage 3: %r is not a horizon in months" % (months,))
    rows = rates(matrix)
    place = grades.index(_DEFAULT)
    start = grades.index(grade)
    alive = [0] * len(grades)
    cumulative = 0
    if start == place:
        cumulative = 10000
    else:
        alive[start] = 10000
    answer = []
    for step in range(1, months + 1):
        moved = [0] * len(grades)
        landed = 0
        for here_at, here in enumerate(alive):
            if here == 0 or here_at == place:
                continue
            share = rows[here_at]
            for there in range(len(grades)):
                if there != place and share[there]:
                    moved[there] = moved[there] + here * share[there] // 10000
            landed = landed + here * share[place] // 10000
        cumulative = cumulative + landed
        alive = moved
        answer.append({"grade": grade, "horizon_months": step,
                       "marginal_bp": landed, "cumulative_bp": cumulative})
    return tuple(answer)


def lifetime_pd(matrix, grade, months):
    """The cumulative PD of `grade` at the last of `months` monthly steps.

    The term structure is walked once and its last row is read; a horizon of zero
    walks no step, so nothing has defaulted yet and the answer is `0`.
    """
    rows = term_structure(matrix, grade, months)
    if not rows:
        return 0
    return rows[-1]["cumulative_bp"]
