"""IRB and Regulatory Capital — stage 9: The two books, reconciled per grade.

The estate carries two books at one reporting date and they *must* be read side
by side, per grade. The accounting book groups its provisions by the
point-in-time grade — each on-book loan's status row carries the ecl the bank
recorded, and the IFRS 9 side of a grade is the sum of those — and the capital
book groups its risk weights by the through-the-cycle grade. Same grades as
labels, different books underneath: a loan the bank has signalled as defaulted
provisions on the `default` row and still prices on the letter its artifact
carries; a loan the bank upgraded provisions on the letter and prices on the
cycle grade it was rerated to. The world's own roll-forward total is the
closing anchor — `book.rollforward(at, at)` — and the IFRS 9 side must add to
it, or the provision column is not the bank's provisions at all. That anchor is
asserted here, not claimed.

`irreconcilable` then names the rows where the two cannot agree, and the reason
code is the contract's, not the stage's: `basis` when the two sides of a grade
hold different loan ids — the loan the two books disagree about *which* column
it belongs in — and `horizon` when both books hold the same loans but money
differs, because a provision over one reporting horizon is never the same
number as a capital over the whole life. A row where the two agree, in ids and
in cents, is not a disagreement and answers nothing at all: silence is the
reconciliation that holds.
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

#: The grades the reconciliation reads per, in the policy's own order.
GRADES = rules.GRADES

#: The two books the stage reads, in the order the rows name them.
KINDS = ("pit", "ttc")

#: The reason codes the contract pins, in their own order.
REASONS = ("basis", "horizon")

#: The fields of one side-by-side row, in order.
GRADE_KEYS = ("grade", "ifrs9_ids", "ifrs9_provision_cents", "irb_ids",
              "irb_capital_cents")

#: The fields of one disagreement row, in order.
RECONCILE_KEYS = ("grade", "reason", "ifrs9_ids", "irb_ids", "ifrs9_provision_cents",
                  "irb_capital_cents")

#: The scale every basis-point and rate measure is held at.
BP_SCALE = 10000


class ReconcileError(PolicyError):
    """The refusal this stage raises: something that cannot be a reconciliation.

    It names the offender — the date the book does not cover, the artifact the
    capital side needs and does not find, the grade outside `rules.GRADES` —
    because a reconciliation that cannot be built must say what it was asked
    for rather than reconcile two books one of which was never read.
    """


def _months_between(start, end):
    """The whole months from `start` to `end`, counted with `dates.add_months`."""
    months = 0
    while dates.add_months(start, months + 1) <= end:
        months += 1
    return months


def _period_bp(loan):
    """The loan's own contract rate as one period's rate, the world's basis."""
    return rules.period_rate(loan["rate_bp"], rules.DEFAULT_BASIS)


def _default_date_through(book, loan_id, at):
    """The loan's first signalled default day at or before `at`, uncured by `at`."""
    for row in book.defaults():
        if row["loan"] == loan_id and row["signalled_on"] <= at \
                and (row.get("cured_on") is None or row["cured_on"] > at):
            return row["signalled_on"]
    return None


def _downturn_lgd(book, loan_id, held, at, model):
    """The loan's downturn LGD — stage 5's order, recomputed locally."""
    default_date = _default_date_through(book, loan_id, at)
    asset_class, treatment = irb.ASSET_CLASS_OF[held["segment"]]
    if default_date is None:
        grade = model["grades"][loan_id]
        be = model["lgd_bp"][grade]
    else:
        period_bp = _period_bp(held)
        balance = held["principal_cents"]
        paid_by_due = {}
        for payment in book.payments(held):
            if payment["kind"] == "instalment" and payment["paid_on"] <= default_date:
                paid_by_due[payment["due"]] = paid_by_due.get(payment["due"], 0) \
                    + payment["amount_cents"]
        for flow in book.schedule(held)["flows"]:
            if flow["date"] > default_date:
                break
            interest = balance * period_bp // BP_SCALE
            paid = paid_by_due.get(flow["date"], 0)
            balance -= min(balance, max(0, paid - interest))
        prepaid = 0
        for payment in book.payments(held):
            if payment["kind"] == "prepayment" and payment["paid_on"] <= default_date:
                prepaid += payment["amount_cents"]
        balance = max(0, balance - prepaid)
        recovered = 0
        haircut = irb.COLLATERAL_HAIRCUT_BP[held["collateral_kind"]]
        for row in book.recoveries(held):
            amount = row["amount_cents"]
            if row["source"] == "collateral":
                amount = amount * (BP_SCALE - haircut) // BP_SCALE
            factor = BP_SCALE
            for _ in range(_months_between(default_date, row["date"])):
                factor = factor * BP_SCALE // (BP_SCALE + period_bp)
            recovered += amount * factor // BP_SCALE
        recovered = min(recovered, balance)
        be = BP_SCALE - recovered * BP_SCALE // balance
        be = min(max(be, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)
    if treatment == "refrigerate":
        return be
    multiplied = be * irb.DOWNTURN_MULTIPLIER_BP[asset_class] // BP_SCALE
    return min(max(multiplied, irb.DOWNTURN_FLOOR_BP), irb.DOWNTURN_CAP_BP)


def _k_rwa(book, held, at, model):
    """The loan's risk-weighted amount — stage 7's rows, recomputed locally."""
    loan_id = held["loan"]
    grade = model["grades"][loan_id]
    lgd_bp = _downturn_lgd(book, loan_id, held, at, model)
    flows = book.schedule(held)["flows"]
    months = _months_between(at, flows[-1]["date"])
    series = model["pd_bp"][grade]
    term_years = min(irb.M_MAX, max(irb.M_MIN, (months + 11) // 12))
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
    total = 0
    for marginal in marginals:
        factor = factor * BP_SCALE // (BP_SCALE + held["rate_bp"])
        total += (marginal * lgd_bp // BP_SCALE) * factor // BP_SCALE
    band = None
    for start in sorted(irb.CORPORATE_SLOPE_BP):
        if start <= series[0]:
            band = start
    asset_class, _treatment = irb.ASSET_CLASS_OF[held["segment"]]
    if asset_class == "corporate":
        b = irb.CORPORATE_SLOPE_BP[band]
    else:
        b = irb.RETAIL_SLOPE_BP[asset_class]
    mf = 10000 + (2 * term_years - 5) * b // 2
    rw_bp = total * mf * irb.CAPITAL_SCALING_BP // (BP_SCALE * BP_SCALE)
    drawn = 0
    for payment in book.payments(held):
        if payment["paid_on"] > at:
            continue
        if payment["kind"] == "instalment":
            drawn += payment["amount_cents"]
        elif payment["kind"] == "prepayment":
            drawn -= payment["amount_cents"]
    drawn = max(0, drawn)
    plan = 0
    for flow in flows:
        if flow["date"] <= at:
            plan += flow["amount_cents"]
    undrawn = max(0, held["undrawn_limit_cents"] - max(0, drawn - plan))
    ead_cents = drawn + undrawn * irb.CCF_BY_PRODUCT_BP[held["segment"]] // BP_SCALE
    return rw_bp * ead_cents // BP_SCALE


def _artifacts(book, at):
    """The estate and the artifact at `at`, refused by name when not both there."""
    try:
        live = book.on_book(at)
    except BookError as refused:
        raise ReconcileError("the estate at %s is not there to read (%s)"
                             % (at, refused))
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise ReconcileError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise ReconcileError("no regulatory artifact is in force at %s, so the "
                             "capital side has no through-the-cycle grade to "
                             "group by" % (at,))
    return live, model


def per_grade(book, at):
    """Both books, per grade: the provision against the capital, side by side.

    The `ifrs9` side groups each on-book loan's own status row — its ecl, the
    provision the bank recorded — by the *point-in-time* grade the bank asserts
    at `at`; the capital side groups each loan's risk-weighted amount — stage
    7's rows, recomputed — by the *through-the-cycle* grade the artifact in
    force carries. Every grade of `rules.GRADES` is answered, an empty one as
    an empty pair of columns, so a reader sees the grade nobody sits in rather
    than missing it; within a grade the loan ids come in estate order and the
    identity of the two sides is what `irreconcilable` reads. The IFRS 9
    column adds to the world's own roll-forward closing amount — the bank's
    own books, not this stage's sum — or `ReconcileError` is raised rather
    than reconciled.

    A date the book does not cover, and an artifact the capital side cannot
    find, are refused by name.
    """
    live, model = _artifacts(book, at)
    ifrs_ids = {}
    ifrs_cents = {}
    irb_ids = {}
    irb_cents = {}
    for loan_id in live:
        pit = book.grade(loan_id, at)
        ifrs_ids.setdefault(pit, []).append(loan_id)
        ifrs_cents[pit] = ifrs_cents.get(pit, 0) + book.status(loan_id, at)["ecl_cents"]
        ttc = model["grades"][loan_id]
        irb_ids.setdefault(ttc, []).append(loan_id)
        irb_cents[ttc] = irb_cents.get(ttc, 0) + _k_rwa(book, book.loan(loan_id), at,
                                                        model)
    closing = book.rollforward(at, at)["closing_cents"]
    provisioned = sum(ifrs_cents.values())
    if provisioned != closing:
        raise ReconcileError("the IFRS 9 provision column of %s sums to %d and the "
                             "bank's own roll-forward closes at %d, so it is not the "
                             "provisions the bank recorded"
                             % (at, provisioned, closing))
    rows = []
    for grade in GRADES:
        rows.append({"grade": grade,
                     "ifrs9_ids": tuple(ifrs_ids.get(grade, ())),
                     "ifrs9_provision_cents": ifrs_cents.get(grade, 0),
                     "irb_ids": tuple(irb_ids.get(grade, ())),
                     "irb_capital_cents": irb_cents.get(grade, 0)})
    return tuple(rows)


def irreconcilable(book, at):
    """The rows the two books cannot agree on, each with one pinned reason code.

    A grade's two sides disagree on the *basis* when they hold different loan
    ids — the loan whose provision column is the defaulted row and whose
    capital column still prices on its cycle letter — and on the *horizon* when
    the ids are the same and the money differs, which is the standing fact of a
    reconciliation: a provision over one reporting horizon is not a capital
    over the whole life. A grade that agrees in both ids and cents answers
    nothing — it is not a disagreement, and a reconciliation that named
    agreeing rows would be inventing problems to look thorough.

    A date the book does not cover, and an artifact the capital side cannot
    find, are refused by name.
    """
    rows = per_grade(book, at)
    named = []
    for row in rows:
        if set(row["ifrs9_ids"]) != set(row["irb_ids"]):
            reason = "basis"
        elif row["ifrs9_provision_cents"] != row["irb_capital_cents"]:
            reason = REASONS[1]
        else:
            continue
        named.append({"grade": row["grade"], "reason": reason,
                      "ifrs9_ids": row["ifrs9_ids"],
                      "irb_ids": row["irb_ids"],
                      "ifrs9_provision_cents": row["ifrs9_provision_cents"],
                      "irb_capital_cents": row["irb_capital_cents"]})
    return tuple(named)


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    at = led.reporting_dates[24]
    print("--- %s   (roll-forward closes at %d)"
          % (at, led.rollforward(at, at)["closing_cents"]))
    print("grade | ifrs9 ids              | provision | irb ids                 | capital")
    for row in per_grade(led, at):
        print("%-5s | %-22s | %d | %-23s | %d"
              % (row["grade"], ",".join(row["ifrs9_ids"]) or "-",
                 row["ifrs9_provision_cents"], ",".join(row["irb_ids"]) or "-",
                 row["irb_capital_cents"]))
    print()
    print("disagreements:")
    for row in irreconcilable(led, at):
        print("%-7s %-8s ifrs9 %d vs capital %d (ids %r vs %r)"
              % (row["grade"], row["reason"], row["ifrs9_provision_cents"],
                 row["irb_capital_cents"], row["ifrs9_ids"], row["irb_ids"]))