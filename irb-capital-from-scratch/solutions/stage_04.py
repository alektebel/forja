"""IRB and Regulatory Capital — stage 4: The capital requirement K, the exact series.

The IRB formula is not evaluated in closed form here. It is one **integer
series** over the loan's remaining term: for each whole year the loan is
expected to run, the marginal default probability of that year — the difference
of two consecutive cumulative rows on the through-the-cycle grade's own PD
term structure — times the loan's downturn loss given default, discounted by
one more step per year at the loan's own contract rate. The series is summed
with its pinned truncation, and the sum is the answer.

A requirement that arrived as one closed form would hide where the money is
won and lost: a reviewer of a capital pack is handed the year-by-year walk, the
year the marginals go quiet (the artifact's cumulative row ends), the share of
the loss each year discounts to. So the stage returns the whole series — the
marginals in basis points, the discounted contribution each year carries, and
the sum — and every division in the walk is pinned: the LGD share first
(`marginal * lgd_bp // 10000`), then that share discounted
(`share * factor // 10000`), the factor stepping
`factor = factor * 10000 // (10000 + rate_bp)` with the loan's own annual
contract rate, once per year.

One year of term is the series' degenerate but honest case — a single
marginal, a single step — and a grade whose cumulative row is all zeros
answers a series of zeros: a capital of nothing is an answer, not a refusal.
The one thing the stage refuses is a loan that stands past its remaining term,
or is not on the book at all: no term, no series.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import dates
import irb
import rules
from book import BookError
from irb import PolicyError

#: The asset classes the multiplier is keyed on, in their own order.
CLASSES = irb.CLASSES

#: The clamps an effective maturity lives between, in whole years.
M_MIN = irb.M_MIN

M_MAX = irb.M_MAX

#: The scale every rate, pd and LGD basis point is held at.
BP_SCALE = 10000


class KError(PolicyError):
    """The refusal this stage raises: something that cannot be a capital series.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the loan past its remaining term, the artifact that carries
    no grade or no PD row for the loan, the artifact field that is not there —
    because a capital the formula cannot stand behind must say what it was
    asked for rather than answer a series the reviewer cannot walk.
    """


def _loan_id(loan):
    """The identity a loan arrives under, as the book's records name it."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


def _live(keyed, loan, at):
    """The loan's record, refused by name when it is not live on the book."""
    loan_id = _loan_id(loan)
    try:
        live = keyed.on_book(at)
    except BookError as refused:
        raise KError("the estate at %s is not there to read (%s)" % (at, refused))
    if loan_id not in live:
        raise KError("loan %r is not on the book at %s" % (loan_id, at))
    try:
        return keyed.loan(loan_id), loan_id
    except BookError as refused:
        raise KError("the book does not hold loan %r (%s)" % (loan_id, refused))


def _in_force(book, at, artifact):
    """The artifact to price with — the one handed in, or the one in force."""
    if artifact is not None:
        if not isinstance(artifact, dict):
            raise KError("the artifact %r is not a record" % (artifact,))
        for field in ("name", "version", "grades", "pd_bp", "lgd_bp"):
            if field not in artifact:
                raise KError("the artifact %r carries no %r field"
                             % (artifact, field))
        return artifact
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise KError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise KError("no regulatory artifact is in force at %s" % (at,))
    return model


def _months_between(start, end):
    """The whole months from `start` to `end`, counted with `dates.add_months`."""
    months = 0
    while dates.add_months(start, months + 1) <= end:
        months += 1
    return months


def _discount(amount_cents, periods, annual_rate_bp):
    """`amount_cents` discounted `periods` years at the annual rate, stepped."""
    factor = BP_SCALE
    for _ in range(periods):
        factor = factor * BP_SCALE // (BP_SCALE + annual_rate_bp)
    return amount_cents * factor // BP_SCALE


def _downturn_lgd(book, loan_id, held, at, model):
    """The loan's downturn LGD at `at`: recoveries when defaulted, the artifact else.

    The same arithmetic stage 5 pins — the haircut first, the discount with it,
    the best estimate clamped, and then the class's multiplier applied to the
    finished estimate unless the booking is refrigerate — recomputed here so
    the series stands on it without reading any stage of this course.
    """
    defaulted = [row["signalled_on"] for row in book.defaults()
                 if row["loan"] == loan_id and row["signalled_on"] <= at
                 and (row.get("cured_on") is None or row["cured_on"] > at)]
    if defaulted:
        period_bp = rules.period_rate(held["rate_bp"], rules.DEFAULT_BASIS)
        balance = held["principal_cents"]
        paid_by_due = {}
        for payment in book.payments(held):
            if payment["kind"] == "instalment" and payment["paid_on"] <= defaulted[0]:
                paid_by_due[payment["due"]] = paid_by_due.get(payment["due"], 0) \
                    + payment["amount_cents"]
        prepaid = 0
        for flow in book.schedule(held)["flows"]:
            due = flow["date"]
            if due > defaulted[0]:
                break
            interest = balance * period_bp // BP_SCALE
            paid = paid_by_due.get(due, 0)
            balance -= min(balance, max(0, paid - interest))
        for payment in book.payments(held):
            if payment["kind"] == "prepayment" and payment["paid_on"] <= defaulted[0]:
                prepaid += payment["amount_cents"]
        balance = max(0, balance - prepaid)
        recovered = 0
        haircut = irb.COLLATERAL_HAIRCUT_BP[held["collateral_kind"]]
        for row in book.recoveries(held):
            amount = row["amount_cents"]
            if row["source"] == "collateral":
                amount = amount * (BP_SCALE - haircut) // BP_SCALE
            factor = BP_SCALE
            for _ in range(_months_between(defaulted[0], row["date"])):
                factor = factor * BP_SCALE // (BP_SCALE + period_bp)
            recovered += amount * factor // BP_SCALE
        recovered = min(recovered, balance)
        be = BP_SCALE - recovered * BP_SCALE // balance
        be = min(max(be, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)
        asset_class, treatment = irb.ASSET_CLASS_OF[held["segment"]]
        if treatment == "refrigerate":
            return be
        multiplied = be * irb.DOWNTURN_MULTIPLIER_BP[asset_class] // BP_SCALE
        return min(max(multiplied, irb.DOWNTURN_FLOOR_BP), irb.DOWNTURN_CAP_BP)
    grade = _grade(model, loan_id, at)
    return model["lgd_bp"][grade]


def _grade(model, loan_id, at):
    """The through-the-cycle grade the artifact carries, or a refusal naming both."""
    try:
        return model["grades"][loan_id]
    except KeyError:
        raise KError("the artifact %r v%d in force at %s carries no grade for loan "
                     "%r" % (model["name"], model["version"], at, loan_id))


def k_requirement(book, loan, at, artifact=None):
    """The exact series: the year-by-year IRB capital of `loan` at `at`.

    `artifact` names the artifact to price with — the check's own fixtures hand
    one; a stage reading the bank prices with `model_in_force` when `artifact`
    is left at `None`. The record carries the grade, the downturn LGD the
    series is priced with, the whole years the loan has left (clamped by
    `irb.M_MIN..irb.M_MAX`), the marginal PD of each year — the difference of
    two consecutive rows of the grade's cumulative PD series, read off the
    through-the-cycle grade, everything past the series' end being zero — and
    the discounted share each year carries:
    `(marginal * lgd_bp // 10000) * factor // 10000`, with the factor stepping
    `factor = factor * 10000 // (10000 + rate_bp)` at the loan's own annual
    contract rate, once per year. `k_bp` is the series summed.

    A loan not on the book at `at`, one past its remaining term, an artifact
    that carries no grade or no PD row for the loan, or a date the book does
    not cover is refused by name.
    """
    held, loan_id = _live(book, loan, at)
    model = _in_force(book, at, artifact)
    grade = _grade(model, loan_id, at)
    lgd_bp = _downturn_lgd(book, loan_id, held, at, model)
    series = model["pd_bp"].get(grade)
    if not isinstance(series, tuple) or not series:
        raise KError("the artifact %r v%d carries no cumulative PD row for grade %r"
                     % (model["name"], model["version"], grade))
    flows = book.schedule(held)["flows"]
    if not flows:
        raise KError("loan %r has no flow to time" % (loan_id,))
    last = flows[-1]["date"]
    months = _months_between(at, last)
    if months <= 0:
        raise KError("loan %r stands past its remaining term at %s (the last flow "
                     "is %s)" % (loan_id, at, last))
    term_years = min(M_MAX, max(M_MIN, (months + 11) // 12))
    rate_bp = held["rate_bp"]
    marginals = []
    for year in range(1, term_years + 1):
        if year == 1:
            marginal = series[0]
        elif year <= len(series):
            marginal = series[year - 1] - series[year - 2]
        else:
            marginal = 0
        marginals.append(marginal)
    factor = BP_SCALE
    discounted = []
    for marginal in marginals:
        factor = factor * BP_SCALE // (BP_SCALE + rate_bp)
        share = marginal * lgd_bp // BP_SCALE
        discounted.append(share * factor // BP_SCALE)
    return {"loan": loan_id,
            "grade": grade,
            "lgd_bp": lgd_bp,
            "term_years": term_years,
            "marginals_bp": tuple(marginals),
            "discounted_bp": tuple(discounted),
            "k_bp": sum(discounted)}


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    print("loan | at          | grade    | lgd  | yrs | K")
    for at in (led.reporting_dates[0], led.reporting_dates[13], led.reporting_dates[24]):
        for held in led.loans():
            try:
                record = k_requirement(led, held["loan"], at)
            except KError as refused:
                print("%-5s | %s | refused: %s"
                      % (held["loan"], at, str(refused)[:78]))
                continue
            print("%-5s | %s | %-8s | %d | %d | %d"
                  % (record["loan"], at, record["grade"], record["lgd_bp"],
                     record["term_years"], record["k_bp"]))
    zero = {"name": "synthetic", "version": 0,
            "grades": dict((held["loan"], "A") for held in led.loans()),
            "pd_bp": {"A": (0, 0, 0, 0, 0)},
            "lgd_bp": {"A": 5000}, "ccf_bp": {}}
    for held in led.loans():
        if held["loan"] != "L-01":
            continue
        record = k_requirement(led, held["loan"], led.reporting_dates[0],
                               artifact=zero)
        print("%-5s zero-grade artifact: marginals %r -> k_bp %d"
              % (held["loan"], record["marginals_bp"], record["k_bp"]))
