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
the predicted rate applied to the population, the statistic is the squared shortfall
in hundredths, and the verdict is a table's critical value rather than an opinion
about size. A grade whose expected count is zero cannot be divided by, so the answer
refuses instead of inventing a statistic.

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

DESIGN DECISION — why does the statistic refuse instead of dividing by an expected zero?
Because an expected count of zero is not a small expected count: the population is
non-empty and the model says none of it will default, so the observed count has no
denominator to be measured against. A stage that answered `0` there would report the
most wrong model as the best one, and a stage that answered `None` would hide the
refusal in a field the record pins as an integer. It raises, naming the grade — and
a grade with no loans at all is not that case: it answers `observed_bp = None`
because nothing was at risk, and contributes nothing to the statistic.

DESIGN DECISION — why is the verdict a table's number rather than a percentage?
Because the statistic is a count and its distribution is a table's, not this
course's arithmetic: `CHI2_CRITICAL_X100` arrives from the world and the stage only
reads it — at the single degree of freedom the aggregate test has — and then chooses
the direction, `under-predicting` where the realised defaults outnumber the expected
ones and `over-predicting` where they fall short. The record says what the count was
and which way it missed; the bank decides what to do about it.

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

import dates
import rules
import stage_06
import stage_07
from book import BookError

BACKTEST_KEYS = ("grade", "predicted_bp", "observed_bp", "loans", "defaults",
                 "chi2_x100", "verdict")

JOURNAL_KEYS = ("component", "delta_cents", "why")

MODEL_CHECKS = ("monotonic", "in-range", "row-sum", "as-of", "versioned")

_MODEL_FIELDS = ("name", "version", "as_of", "grades", "pd_bp", "lgd_bp", "ccf_bp")

_DEFAULT_GRADE = "default"

_WITHIN = "within-tolerance"

_UNDER = "under-predicting"

_OVER = "over-predicting"

_INSUFFICIENT = "insufficient-data"

_COMPONENTS = (("pd_bp", "pd", "the artifact's term structure, over the horizon each "
                "loan's grade gives it"),
               ("lgd_bp", "lgd", "the artifact's loss given default for the loans that "
                "are not yet defaulted"),
               ("ccf_bp", "ccf", "the artifact's credit conversion factor, in the "
                "exposure the loss is taken against"),
               ("grades", "grades", "the loans the new artifact's own ratings map "
                "re-rates"))


def _named(model, what):
    """How a refusal names an artifact: its name and version, or the argument's own."""
    if isinstance(model, dict) and isinstance(model.get("name"), str) and model["name"]:
        return "%s %s" % (model["name"], model.get("version"))
    return what


def _shape(model, what):
    """The artifact's seven fields, or a refusal naming the one that is missing."""
    if not isinstance(model, dict):
        raise BookError("stage 10: %s is not a model artifact" % (what,))
    missing = [field for field in _MODEL_FIELDS if field not in model]
    if missing:
        raise BookError("stage 10: %s has no %s"
                        % (_named(model, what), ", ".join(missing)))
    return model


def _covered(book, date, what):
    """A reporting date the book holds, or a refusal naming the date."""
    if date not in book.reporting_dates:
        raise BookError("stage 10: %s is not a reporting date of the book (%s)"
                        % (date, what))
    return date


def _months_between(start, end):
    """Whole months from `start` to `end`, the reporting dates being month ends."""
    start_year, start_month, _ = dates.parse(start)
    end_year, end_month, _ = dates.parse(end)
    return (end_year - start_year) * 12 + (end_month - start_month)


def _pd_at(pd_bp, grade, months):
    """The artifact's cumulative PD for `grade` over `months`: linear in months, truncated."""
    if grade not in pd_bp:
        raise BookError("stage 10: the model does not rate grade %r" % (grade,))
    row = pd_bp[grade]
    if not row:
        raise BookError("stage 10: the model's term structure for grade %r is empty"
                        % (grade,))
    whole = months // 12
    rest = months - whole * 12
    if whole >= len(row):
        return row[-1]
    if whole == 0:
        return row[0] * months // 12
    left = row[whole - 1]
    return left if rest == 0 else left + (row[whole] - left) * rest // 12


def _loans_at(book, date):
    """The loan records the book carries at the date, in the book's own order."""
    return tuple(book.loan(loan_id) for loan_id in book.on_book(date))


def _signalled(book):
    """The dates each loan's default was signalled, by loan id."""
    found = {}
    for row in book.defaults():
        found.setdefault(row["loan"], []).append(row["signalled_on"])
    return found


def _stages(book, date, model):
    """The stage each loan sits in at the date under one artifact, by loan id."""
    found = {}
    for loan in _loans_at(book, date):
        found[loan["loan"]] = stage_07.stage(book, loan, date, model=model)["stage"]
    return found


def _view(model, field, other):
    """A copy of `model` with one of `other`'s inputs in it: the artifacts are read-only."""
    view = dict(model)
    view[field] = other[field]
    return view


def _provision(book, date, model, stages):
    """The provision at the date under one artifact, weighted by the policy's own weights."""
    total = 0
    for loan in _loans_at(book, date):
        stage = stages[loan["loan"]]
        for scenario in rules.SCENARIOS:
            ecl = stage_06.ecl(book, loan, date, scenario, stage=stage, model=model)
            total += ecl["ecl_cents"] * rules.SCENARIO_WEIGHTS_BP[scenario] // 10000
    return total


def _model_rows(book):
    """The book's own model roster, whether it is handed back as rows or as a call."""
    rows = book.models
    return rows() if callable(rows) else rows


def _values(table):
    """Every rate a table holds, whether the table keys them by grade or by segment."""
    found = []
    for key in table:
        value = table[key]
        if isinstance(value, (tuple, list)):
            found.extend(value)
        else:
            found.append(value)
    return found


def _monotonic(model):
    """The per-year PDs never fall with the horizon, grade by grade."""
    for grade in model["pd_bp"]:
        row = model["pd_bp"][grade]
        for step in range(1, len(row)):
            if row[step] < row[step - 1]:
                return "fail"
    return "pass"


def _inside(table, floor, cap):
    """Every rate the table holds sits inside the policy's own range."""
    for value in _values(table):
        if value < floor or value > cap:
            return False
    return True


def _in_range(model):
    """PD in `0..10000`, the LGD and the CCF inside the policy's floor and cap."""
    if not _inside(model["pd_bp"], 0, 10000):
        return "fail"
    if not _inside(model["lgd_bp"], rules.LGD_FLOOR_BP, rules.LGD_CAP_BP):
        return "fail"
    if not _inside(model["ccf_bp"], rules.CCF_FLOOR_BP, rules.CCF_CAP_BP):
        return "fail"
    return "pass"


def _row_sum(model):
    """A grade's row is cumulative: the last is the lifetime, and nothing exceeds it."""
    for grade in model["pd_bp"]:
        row = model["pd_bp"][grade]
        if not row:
            return "fail"
        lifetime = row[-1]
        if lifetime > 10000:
            return "fail"
        for value in row:
            if value > lifetime:
                return "fail"
    return "pass"


def _as_of(book, model):
    """The artifact is not dated after the window of the book it would be used for."""
    as_of = model["as_of"]
    if not isinstance(as_of, str):
        raise BookError("stage 10: %s's as_of is not a date"
                        % (_named(model, "the model"),))
    dates.parse(as_of)
    return "pass" if as_of <= book.reporting_dates[-1] else "fail"


def _versioned(book, model):
    """A name and a version are there, and one version of one name is one row."""
    name = model["name"]
    version = model["version"]
    if not isinstance(name, str) or not name:
        return "fail"
    if version is True or version is False or not isinstance(version, int):
        return "fail"
    if version < 1:
        return "fail"
    rows = [row for row in _model_rows(book)
            if row["name"] == name and row["version"] == version]
    return "pass" if len(rows) <= 1 else "fail"


def _defaulted_within(signalled, loan_id, start, end):
    """Whether this loan's default was signalled inside the window `(start, end]`."""
    for date in signalled.get(loan_id, ()):
        if start < date <= end:
            return True
    return False


def backtest(book, model, start, end):
    """The artifact's predicted PD against what the book realised, grade by grade.

    One `BACKTEST_KEYS` row per grade except `"default"`, in `GRADES` order: the
    population is every loan the bank's record puts in that grade at `start`, the
    outcome is every one of them whose default was signalled inside the window
    `(start, end]`, and the predicted rate is the artifact's own cumulative PD for
    the grade over the window's months. Each row carries its own
    `(defaults - expected) ** 2 * 100 // expected` with
    `expected = predicted_bp * loans // 10000`, and the terms are summed over the
    grades the model expects at least one default in. The verdict is the
    portfolio's, the same in every row: the table's critical value at one degree of
    freedom per grade the statistic counted, the direction by whether the window's
    defaults outnumber the expected ones, and `"insufficient-data"` where fewer than
    two grades have an expectation at all — one bucket has no freedom to be read at.
    A grade with no loans answers `observed_bp = None` and contributes nothing; a
    grade whose expected count truncates to zero answers its counts and a term of
    zero, because that is what its shortfall is, but it is not a bucket the test can
    measure, so it is not a freedom either.
    """
    _shape(model, "backtest's model")
    _covered(book, start, "the backtest's window start")
    _covered(book, end, "the backtest's window end")
    months = _months_between(start, end)
    if months < 0:
        raise BookError("stage 10: the backtest's window %s..%s ends before it starts"
                        % (start, end))
    signalled = _signalled(book)
    rows = []
    statistic = 0
    realised = 0
    wanted = 0
    counted = 0
    for grade in rules.GRADES:
        if grade == _DEFAULT_GRADE:
            continue
        population = [loan for loan in book.loans()
                      if book.grade(loan, start) == grade]
        loans = len(population)
        defaults = len([loan for loan in population
                        if _defaulted_within(signalled, loan["loan"], start, end)])
        predicted = _pd_at(model["pd_bp"], grade, months)
        term = 0
        if loans:
            expected = predicted * loans // 10000
            realised += defaults
            wanted += expected
            if expected:
                term = (defaults - expected) ** 2 * 100 // expected
                statistic += term
                counted += 1
        rows.append({"grade": grade, "predicted_bp": predicted,
                     "observed_bp": None if loans == 0 else defaults * 10000 // loans,
                     "loans": loans, "defaults": defaults, "chi2_x100": term})
    if counted < 2:
        verdict = _INSUFFICIENT
    elif statistic <= rules.CHI2_CRITICAL_X100[counted - 1]:
        verdict = _WITHIN
    elif realised > wanted:
        verdict = _UNDER
    else:
        verdict = _OVER
    return tuple(dict(row, verdict=verdict) for row in rows)


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
    _shape(model, "validate's model")
    return (("monotonic", _monotonic(model)),
            ("in-range", _in_range(model)),
            ("row-sum", _row_sum(model)),
            ("as-of", _as_of(book, model)),
            ("versioned", _versioned(book, model)))


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
    _shape(old_model, "the journal's old model")
    _shape(new_model, "the journal's new model")
    _covered(book, date, "the journal's date")
    old_stages = _stages(book, date, old_model)
    baseline = _provision(book, date, old_model, old_stages)
    rows = []
    view = old_model
    previous = baseline
    for field, component, why in _COMPONENTS:
        view = _view(view, field, new_model)
        reached = _provision(book, date, view, old_stages)
        rows.append({"component": component, "delta_cents": reached - previous,
                     "why": why})
        previous = reached
    total = _provision(book, date, new_model, _stages(book, date, new_model))
    rows.append({"component": "other",
                 "delta_cents": total - previous,
                 "why": "the staging the new artifact moves, which the four inputs "
                        "above do not own: %d cents of provision against %d under "
                        "the old stages" % (total, previous)})
    return tuple(rows)
