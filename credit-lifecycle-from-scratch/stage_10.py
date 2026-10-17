"""Credit Lifecycle From Scratch — stage 10: The backtest, the model artifact and the journal of the delta.

The model arrives as an artifact — a name, a version, an `as_of`, the grades it
rates, and its per-year PDs, its LGDs and its CCFs — and this stage does the two
things a bank does with an artifact it did not fit: it holds the model against what
actually happened, and it explains the provision that moved when the artifact was
replaced.

The backtest is a cohort study. Each graded rating has a population — the loans the
bank's own record puts in that grade at the window's start — and within that
population some loans defaulted inside the window. Observed is the realised rate over
the population, predicted is the artifact's own cumulative PD over the window's
months, and the two are held together by the count of defaults: the expected count is
the predicted rate applied to the population, the statistic is the squared shortfall in
hundredths summed over the grades the model expects a default in, and the verdict is
a table's critical value rather than an opinion about size — read at one degree of
freedom per grade the statistic counted. A grade whose expected count truncates to
zero answers its counts and a term of zero, because that is what its shortfall is,
but it is not a bucket the test can measure; a window in which fewer than two grades
have an expectation is `insufficient-data` rather than a tolerance, because one
bucket has no freedom to be read at.

`validate` reads the artifact the way a model validator would: the PDs must not fall
with the horizon, every rate must sit inside its policy's range, a grade's row must
be cumulative, the artifact must not be dated after the window it would be used for,
and a version must name one row and no two. Every answer is `"pass"` or `"fail"` —
the checks are returned, the shape is raised.

The journal is the delta. The provision at the date is recomputed with the old
artifact, and then one of the new artifact's inputs at a time — its term structure,
its LGD table, its CCF table, the loans its own `grades` map re-rates — with the
provision recomputed through stage 6's own expected loss every time, so the journal
attributes the movement of the number the bank books rather than the movement of a
second implementation of it. What the four do not each own is not absorbed into a
neighbour: it is `other`, its own row, in cents.

    BACKTEST_KEYS                     the seven fields of a backtest row, in order
    JOURNAL_KEYS                      the three fields of a journal row, in order
    MODEL_CHECKS                      the five checks `validate` returns, in order
    backtest(book, model, start, end) -> one BACKTEST_KEYS row per graded rating
    validate(book, model)             -> one (check, verdict) per name in MODEL_CHECKS
    journal(book, old_model, new_model, date) -> one JOURNAL_KEYS row per component

DESIGN DECISION — why is the cohort the bank's own grade at the window's start?
Because a backtest that selects its population with the thing it is testing is
circular. The bank's record already carries the grade it held at every reporting
date, so the cohort is `book.grade(loan, start)` and the outcome is the loan's own
signalled default inside the window — the two facts the book's
`observed_default_rate` is built from, so a row's counts and rate can be held
against the bank's own answer and disagreeing with it is wrong rather than lucky.

DESIGN DECISION — why is an expected count of zero a zero term rather than a refusal?
Because refusing would make the whole study unrunnable on the portfolios a bank
actually models: a cohort of three loans and a ten-basis-point PD expects 0.03
defaults, truncates to zero, and the rest of the table is perfectly readable. The
grade's own shortfall there is still known — it realised whatever it realised and
expected nothing — so its term is zero, and a bucket whose expectation is zero is not
one the test can measure: it is not a freedom either. A grade with no loans at all is
not even that case: it answers `observed_bp = None` because nothing was at risk, and
is not counted at all. And a test with fewer than two buckets that expect something
has no degrees of freedom for the table to be read at, so it is `insufficient-data`
rather than a tolerance: there is nothing yet to compare.

DESIGN DECISION — why is the verdict a table's number rather than a percentage?
Because the statistic is a count and its distribution is a table's, not this
course's arithmetic: `CHI2_CRITICAL_X100` arrives from the world and the stage only
reads it — at one degree of freedom per grade the statistic counted, so a table of
six cohorts is read at five — and then chooses the direction, `under-predicting`
where the window's defaults outnumber the expected ones and `over-predicting` where
they fall short. The record says what the count was and which way it missed; the
bank decides what to do about it.

DESIGN DECISION — why does the journal recompute through stage 6 instead of here?
Because the provision is a number the course already knows how to compute, and a
journal that computed it a second time would be explaining the movement of its own
arithmetic rather than the movement of the bank's. So every step of the journal
sums `stage_06.weighted_ecl` over the book's loans with an artifact handed in, and
the artifact in force at the date is what the unqualified call means. Stage 6 takes
the model as an override precisely so that a swapped artifact — one table at a time
— is the bank's own expected loss recomputed, not a second one.

DESIGN DECISION — why is `other` a row rather than a rounding adjustment?
Because a journal whose components always add up to the total by construction is a
journal that has hidden something: two inputs moving together leave an interaction
the four components do not each own, and the honest place for it is its own line in
cents. The deltas are recomputed one input at a time against the old artifact's
provision — which is what makes each one the effect of that input — and the residual
between their sum and the total movement is reported, never folded into a neighbour.

TODO: implement `backtest`, `validate` and `journal` in this file: the cohort study
that holds the artifact against the realised defaults, the five checks a validator
returns, and the journal that recomputes the provision one model input at a time.
"""

BACKTEST_KEYS = ("grade", "predicted_bp", "observed_bp", "loans", "defaults",
                 "chi2_x100", "verdict")

JOURNAL_KEYS = ("component", "delta_cents", "why")

MODEL_CHECKS = ("monotonic", "in-range", "row-sum", "as-of", "versioned")


def backtest(book, model, start, end):
    """The artifact's predicted PD against what the book realised, grade by grade.

    One `BACKTEST_KEYS` row per grade except `"default"`, in `GRADES` order: the
    population is every loan the bank's record puts in that grade at `start`, the
    outcome is every one of them whose default was signalled inside the window
    `(start, end]`, and the predicted rate is the artifact's own cumulative PD for
    the grade over the window's months. Each row carries its own
    `(defaults - expected) ** 2 * 100 // expected` with
    `expected = predicted_bp * loans // 10000`, and the terms are summed over the
    grades the model expects at least one default in. The verdict is the portfolio's,
    the same in every row: the table's critical value at one degree of freedom per
    grade the statistic counted, the direction by whether the window's defaults
    outnumber the expected ones, and `"insufficient-data"` where fewer than two
    grades have an expectation. A grade with no loans answers `observed_bp = None`
    and contributes nothing; a grade whose expected count truncates to zero answers
    its counts and a term of zero, because that is what its shortfall is, but it is
    not a bucket the test can measure, so it is not a freedom either.
    """
    raise NotImplementedError("stage 10: implement backtest()")


def validate(book, model):
    """One `(check, verdict)` per name in `MODEL_CHECKS`, in that order.

    `monotonic`: the per-year PDs never fall with the horizon. `in-range`: every PD
    in `0..10000` and the LGD and the CCF inside the policy's floor and cap.
    `row-sum`: a grade's row is cumulative, so its last entry is the lifetime and
    nothing in the row exceeds it. `as-of`: the artifact is not dated after the
    window of the book it would be used for. `versioned`: a name and a version are
    there, and the book carries one row per version of a name. Every verdict is
    `"pass"` or `"fail"`.
    """
    raise NotImplementedError("stage 10: implement validate()")


def journal(book, old_model, new_model, date):
    """One `JOURNAL_KEYS` row per component: what moved the provision, in cents.

    The provision at `date` is recomputed with the old artifact, and then the new
    artifact's inputs are swapped in one at a time — its term structure, its LGD
    table, its CCF table, its own ratings — each step summed through stage 6's own
    expected loss over the loans the book carries, at the stage the old artifact
    left each loan in. The last two steps are the total: the provision under the new
    artifact at the old stages, and the same at the new stages, whose difference is
    `other` — the staging the new artifact moves, reported rather than absorbed.
    """
    raise NotImplementedError("stage 10: implement journal()")
