"""Credit Lifecycle From Scratch — stage 3: The migration matrix, the term structure and the lifetime PD.

Two dates of the book, and the grades the bank recorded for the loans in between. This
stage turns that movement into the three things every later stage asks for: a
**migration matrix** whose rows are the grades the portfolio sat in and whose columns
are the grades it reached, a **term structure** that walks that matrix one month at a
time, and a **lifetime PD** — the probability that a loan which is sound today is in
default by the end of a horizon. Nothing here is fitted. The matrix is what the book's
own grade records did, and a stage that smooths, floors or re-rates it has invented a
policy the world does not have.

The unit is the basis point and the arithmetic is the integer arithmetic of this course.
A row of the matrix is a distribution over the grades, so it sums to exactly 10000,
which is why the `default` column is not one more division but the remainder of the
row's other divisions: `10000` is the law, and a row that sums to `9999` has leaked a
basis point of probability. `default` is absorbing, because a defaulted loan does not
walk back out of the column in this model; and the term structure is a survival
computation, not a multiplication, because the loan that defaulted in month two is not
at risk in month three.

    MATRIX_KEYS                                  the six fields of a migration matrix, in order
    PD_KEYS                                      the four fields of one PD term, in order
    GRADES                                       the rating scale, `default` last and absorbing
    migration(book, start, end)                  -> MATRIX_KEYS, from the grades the book recorded
    rates(matrix)                                -> the rows of the matrix in basis points
    term_structure(matrix, grade, months)        -> one PD_KEYS row per month walked
    lifetime_pd(matrix, grade, months)           -> the cumulative PD at the last month

DESIGN DECISION — why is the matrix recomputed from the book's grade records instead of
read off the book's own `migrations`?
Because the book records what a bank recorded and this stage records what the arithmetic
says, and the whole point of a check is that the two are computed independently and then
compared. So `migration` walks the book's loans, asks `book.grade(loan, date)` for the
grade the bank itself put on each one at each date, counts the movements, and answers a
matrix of its own. A stage that passed the book's own record through would be asserting
nothing at all: it would agree with the book by construction, and a reader could not tell
the difference between a computation and a lookup.

DESIGN DECISION — why does the row's remainder go to the `default` column rather than
being dropped, spread or rounded away?
Because a row of the matrix is a probability distribution and `10000` is 100%: the
columns are a partition of the loan population, so a truncated row that sums to `9999`
is not a rounding artefact but a leak. Truncating every cell is what the contract pins,
and the one cell that can carry the residue of seven truncations without distorting the
others is the terminal one — `default` is the absorbing state, so the basis points the
other divisions lost belong to the state every surviving path eventually has to reach.
Rounding each cell half-up instead would make a row sum to 10001 about as often as
10000, and neither the generator nor the reader would know which.

DESIGN DECISION — why is the `default` row absorbing, and why does the term structure
walk a distribution instead of multiplying one marginal?
Because a default is where a loan's risk story stops: the bank's own grade record is a
fact about a reporting date, and a cure inside the window shows up in the counts as a
loan that left the `default` column — but a PD term structure measures the chance that a
loan which is sound today ends up defaulted, and a loan that has already defaulted has
arrived. So the walk carries the mass of the loans that are still alive, the mass that
lands in `default` is counted in the marginal and then dropped, and the column only ever
receives. That is what keeps the two invariants the contract pins: the cumulative never
falls, and it never passes `10000` — a walk that carried the `default` column's mass
back out would pump the cumulative past the scale in exactly the window where the book
recorded a cure.

DESIGN DECISION — why does a grade the portfolio never sat in still get a row and a
column?
Because the grid is the rating scale, not the observed subset of it: a row per grade in
`GRADES` means a reader can compare two windows, two segments or two runs line by line,
and a row with no loans is answered by the rule the contract pins rather than by
omission — `default` gets `10000` and every other column zero, which is the same
absorb-the-rest rule that rounds every other row. A matrix printed from the observed
pairs alone would silently change its shape between windows, and a check could not tell
a grade that moved the wrong way from a grade that was dropped.

DESIGN DECISION — why is a bad horizon or an unknown grade a refusal rather than an
answer?
Because a term structure is a fact about a row of the matrix, and there is no honest
number to return for a grade the scale does not hold: `0` would read as "this grade
never defaults" and `10000` as "this grade is already defaulted", and both are verdicts
the stage has no business issuing. `months = 0` is different and is answered: no step was
walked, so nothing has defaulted yet and the empty answer is the honest one. The
refusals name the offender — the grade or the date the book does not cover — and they
are raised before any record is read, so a refused call leaves the bank's ledger of what
it was asked exactly where it was.

TODO: implement `MATRIX_KEYS`, `PD_KEYS`, `migration`, `rates`, `term_structure` and
`lifetime_pd` in this file: the matrix the book's own grade movements build, the rows
that have to sum to exactly `10000`, and the survival walk that turns the one into the
other.
"""

import rules
from book import BookError

MATRIX_KEYS = ("from_date", "to_date", "grades", "counts", "rates_bp", "row_totals")

PD_KEYS = ("grade", "horizon_months", "marginal_bp", "cumulative_bp")

GRADES = rules.GRADES

_DEFAULT = "default"


def migration(book, start, end):
    """The grade movements the book itself observed between `start` and `end`.

    One row per grade in `GRADES` — a grade the portfolio never sat in still gets
    its row — and one column per grade it reached, so `counts` is keyed by the
    `(from_grade, to_grade)` pair and `row_totals` by the grade the row came from.
    Every loan of the book is counted, because the bank's grade record is total
    over the reporting dates: the pair is the grade at `start` against the grade at
    `end`, so a loan the bank had already defaulted at `start` counts in
    `("default", "default")` while it stays defaulted, and a pair like
    `("default", "B")` is a cure the book itself recorded.

    `rates_bp` is `rates` of what this function counted, in the same order as
    `grades`. A date outside `book.reporting_dates` raises `BookError` naming it,
    before the book is asked for a single record.
    """
    raise NotImplementedError("stage 3: implement migration()")


def rates(matrix):
    """The rows of `matrix` in basis points, one row per grade in `matrix["grades"]`.

    Each cell is `count * 10000 // row_total`, truncated, and the whole remainder
    of the row's other divisions is given to the `default` column, so every row
    sums to exactly `10000`. A row with no loans is the absorb-the-rest row: the
    `default` column gets `10000` and every other column zero. A matrix that is not
    a `MATRIX_KEYS` record, or whose grades are not grades of the scale or hold no
    `default` column to absorb the remainder, raises `BookError` naming the
    offender.
    """
    raise NotImplementedError("stage 3: implement rates()")


def term_structure(matrix, grade, months):
    """The PD term structure of `grade` over `months` monthly steps.

    One `PD_KEYS` row per step, `horizon_months` counting from 1: `marginal_bp`
    is the share of the distribution that is still alive which lands in `default`
    at that step and `cumulative_bp` is the probability of being defaulted by it —
    the running sum of the marginals, so it never falls and never passes `10000`.
    The mass that lands in `default` is counted and then dropped, because the
    column absorbs, and every product is truncated (`(a * b) // 10000`). A walk
    that starts in `default` has already defaulted: its cumulative is `10000` and
    nothing more lands in it.

    `months == 0` answers the empty case — no step walked, nothing defaulted yet,
    an empty tuple — and a grade outside `GRADES`, a grade the matrix has no row
    for or a negative horizon raises `BookError` naming the offender.
    """
    raise NotImplementedError("stage 3: implement term_structure()")


def lifetime_pd(matrix, grade, months):
    """The cumulative PD of `grade` at the last of `months` monthly steps.

    The lifetime probability is the term structure's cumulative at its final
    horizon and nothing else: `0` when no step was walked, because a loan that is
    sound today has not defaulted yet, and the same refusals `term_structure`
    makes for a grade the scale does not hold or a horizon below zero.
    """
    raise NotImplementedError("stage 3: implement lifetime_pd()")
