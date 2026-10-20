"""IRB and Regulatory Capital — stage 10: The audit the supervisor files.

Everything the course has built becomes one filing. The pack carries, per
asset class and per through-the-cycle grade, the exposures that price into it
— the on-book loans with a remaining term — with each row's exposure count,
its EAD, its capital (the K of stage 4 times the exposure), its risk-weighted
amount (stage 7's rows) and its *applied* risk-weighted amount (stage 8's
floor, at the year the filing names — the greater of the bank's own weight and
the floor's share, exposure by exposure). A coverage ratio per grade closes
the pack: the grade's IFRS 9 provision over its applied RWA, in basis points,
truncated — the one number that says whether the provision column and the
capital column are at all comparable, with the rows where the two cannot agree
carried (stage 9 named them) rather than hidden.

The filing has duties, and this stage enforces them the way a supervisor's
review would. A loan is priced once: every on-book, remaining-term exposure
appears in exactly one (class, grade) row, and the rows' exposure counts add
to the pack's own count. Per class the rows sum to the class, and the classes
sum to the pack's own totals — no column may claim a cent its rows cannot
explain. And the disagreement rows the pack files are exactly the ones stage
9's contract named — same grade, same reason — even when that means filing
nothing, because a pack reconciling quietly would fail loudly only years
later, where a supervisor needs it now.
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

#: The asset classes the pack groups by, in the policy's own order.
CLASSES = irb.CLASSES

#: The grades the pack groups by, in the world's own order.
GRADES = rules.GRADES

#: The fields of one exposure row, in order.
ROW_KEYS = ("asset_class", "grade", "exposures", "ead_cents", "capital_cents",
            "rwa_cents", "applied_rwa_cents")

#: The fields of the pack itself, in order.
PACK_KEYS = ("at", "floor_year", "percent", "exposures", "total_rwa_cents",
             "applied_rwa_cents", "capital_cents", "rows", "coverage_bp",
             "disagreements")

#: The fields of a coverage row: the grade and its basis points of coverage.
COVERAGE_KEYS = ("grade", "coverage_bp")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class AuditError(PolicyError):
    """The refusal this stage raises: something that cannot be a filing.

    It names the offender — the year outside the floor's schedule, the date the
    book does not cover, the artifact the pack's capital column would need and
    does not find, a duty the pack's own rows broke and the loan that broke it
    — because a filing a supervisor must be able to walk must say what it was
    asked for rather than file one no row can explain.
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
    """`(k_bp, rw_bp, ead_cents)` — stages 4, 7 and 6's rows, recomputed locally."""
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
    return total, rw_bp, ead_cents


def phase(year):
    """The schedule row of `stage 8`, read by this stage as the filing's percent."""
    if isinstance(year, bool) or not isinstance(year, int):
        raise AuditError("the floor year %r is a %s, not a whole calendar year"
                         % (year, type(year).__name__))
    years = tuple(sorted(irb.FLOOR_PHASE_PERCENT))
    if year not in irb.FLOOR_PHASE_PERCENT:
        raise AuditError("the output floor's schedule holds %d..%d and %d is not a "
                         "year it phases in" % (years[0], years[-1], year))
    return irb.FLOOR_PHASE_PERCENT[year]


def capital_pack(book, at, floor_year):
    """The pack the supervisor files: exposures, weights, floor, capital, coverage.

    `floor_year` names the year's floor answer (the schedule row `phase`
    answers); `at` names the reporting date the pack prices at. The pack's
    rows are keyed `(asset_class, grade)` in the order the two tables are
    pinned in — `irb.CLASSES` then `rules.GRADES` — so a reader and a program
    agree on what row one is and every class and grade the estate prices into
    is answered. Per row: the exposure count, the EAD the loans carry, the
    capital K prices in cents (`k_bp * ead_cents // 10000`), the risk-weighted
    amount and the applied amount after the floor's share, exposure by
    exposure.

    `coverage_bp` answers, per grade, its IFRS 9 provision over its applied
    RWA in basis points — `provision * 10000 // applied`, truncated, and a
    grade the floor and the weights price at nothing answers zero — and
    `disagreements` carries the stage 9 contract's reason rows, recomputed
    here by the same contract, not imported from a stage of this course.

    A year outside the floor's schedule, a date the book does not cover, an
    artifact column the pack cannot read, or a duty the pack's own rows break
    — a loan priced twice, a row claiming a cent its loans do not carry — is
    refused by name.
    """
    percent = phase(floor_year)
    try:
        live = book.on_book(at)
    except BookError as refused:
        raise AuditError("the estate at %s is not there to read (%s)" % (at, refused))
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise AuditError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise AuditError("no regulatory artifact is in force at %s, so the pack "
                         "has no through-the-cycle grade to file by" % (at,))
    rows_map = {}
    seen = []
    exposures = 0
    for loan_id in live:
        held = book.loan(loan_id)
        months = _months_between(at, book.schedule(held)["flows"][-1]["date"])
        if months <= 0:
            continue
        asset_class, _treatment = irb.ASSET_CLASS_OF[held["segment"]]
        grade = model["grades"][loan_id]
        if asset_class not in CLASSES:
            raise AuditError("%r prices to an asset class the pack does not file"
                             % (held["segment"],))
        if grade not in GRADES:
            raise AuditError("the artifact prices loan %r at grade %r, which the "
                             "pack does not file" % (loan_id, grade))
        if loan_id in seen:
            raise AuditError("loan %r is priced twice in the pack, so some row "
                             "explains a cent twice" % (loan_id,))
        seen.append(loan_id)
        k_bp, rw_bp, ead_cents = _k_rwa(book, held, at, model)
        proxy = ead_cents * irb.STANDARD_WEIGHT_BP[asset_class] // BP_SCALE
        share = proxy * percent // 100
        own = rw_bp * ead_cents // BP_SCALE
        key = (asset_class, grade)
        row = rows_map.get(key)
        if row is None:
            row = {"asset_class": asset_class, "grade": grade, "exposures": 0,
                   "ead_cents": 0, "capital_cents": 0, "rwa_cents": 0,
                   "applied_rwa_cents": 0}
            rows_map[key] = row
        row["exposures"] += 1
        row["ead_cents"] += ead_cents
        row["capital_cents"] += k_bp * ead_cents // BP_SCALE
        row["rwa_cents"] += own
        row["applied_rwa_cents"] += max(own, share)
        exposures += 1
    rows = tuple(rows_map[(asset_class, grade)]
                 for asset_class in CLASSES for grade in GRADES
                 if (asset_class, grade) in rows_map)
    total_rwa = sum(row["rwa_cents"] for row in rows)
    total_applied = sum(row["applied_rwa_cents"] for row in rows)
    total_capital = sum(row["capital_cents"] for row in rows)
    for row in rows:
        if row["exposures"] == 0 and (row["ead_cents"] or row["rwa_cents"]
                                      or row["applied_rwa_cents"]):
            raise AuditError("the %s/%s row claims %d weighted and %d applied with no "
                             "exposure priced into it"
                             % (row["asset_class"], row["grade"], row["rwa_cents"],
                                row["applied_rwa_cents"]))
    provisions = _provisions(book, at)
    applied_grade = {}
    for row in rows:
        applied_grade[row["grade"]] = applied_grade.get(row["grade"], 0) \
            + row["applied_rwa_cents"]
    coverage = {}
    for grade in GRADES:
        provision = provisions.get(grade, 0)
        priced = applied_grade.get(grade, 0)
        coverage[grade] = provision * BP_SCALE // priced if priced else 0
    disagreements = _irreconcilable(book, at, model)
    return {"at": at, "floor_year": floor_year, "percent": percent,
            "exposures": exposures, "total_rwa_cents": total_rwa,
            "applied_rwa_cents": total_applied, "capital_cents": total_capital,
            "rows": rows, "coverage_bp": coverage, "disagreements": disagreements}


def _irreconcilable(book, at, model):
    """Stage 9's reason rows, recomputed by the same contract, not imported."""
    live = tuple(loan_id for loan_id in book.on_book(at)
                 if _months_between(at, book.schedule(loan_id)["flows"][-1]["date"]) > 0)
    ifrs = {}
    ifrs_cents = {}
    capital = {}
    capital_cents = {}
    for loan_id in live:
        pit = book.grade(loan_id, at)
        ifrs.setdefault(pit, []).append(loan_id)
        ifrs_cents[pit] = ifrs_cents.get(pit, 0) + book.status(loan_id, at)["ecl_cents"]
        ttc = model["grades"][loan_id]
        capital.setdefault(ttc, []).append(loan_id)
        _k_bp, rw_bp, ead_cents = _k_rwa(book, book.loan(loan_id), at, model)
        capital_cents[ttc] = capital_cents.get(ttc, 0) + rw_bp * ead_cents // BP_SCALE
    named = []
    for grade in GRADES:
        if set(ifrs.get(grade, ())) != set(capital.get(grade, ())):
            reason = "basis"
        elif ifrs_cents.get(grade, 0) != capital_cents.get(grade, 0):
            reason = "horizon"
        else:
            continue
        named.append({"grade": grade, "reason": reason,
                      "ifrs9_ids": tuple(ifrs.get(grade, ())),
                      "irb_ids": tuple(capital.get(grade, ())),
                      "ifrs9_provision_cents": ifrs_cents.get(grade, 0),
                      "irb_capital_cents": capital_cents.get(grade, 0)})
    return tuple(named)


def _provisions(book, at):
    """The IFRS 9 provision per grade at `at`, from the world's own status rows."""
    provisions = {}
    for loan_id in book.on_book(at):
        pit = book.grade(loan_id, at)
        provisions[pit] = provisions.get(pit, 0) + book.status(loan_id, at)["ecl_cents"]
    return provisions


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    at = led.reporting_dates[24]
    pack = capital_pack(led, at, 2032)
    print("--- %s | floor year %d (%d%%) | exposures %d"
          % (at, pack["floor_year"], pack["percent"], pack["exposures"]))
    print("class            | grade | n | ead      | capital  | rwa       | applied")
    for row in pack["rows"]:
        print("%-16s | %-7s | %d | %d | %d | %d | %d"
              % (row["asset_class"], row["grade"], row["exposures"], row["ead_cents"],
                 row["capital_cents"], row["rwa_cents"], row["applied_rwa_cents"]))
    print()
    print("coverage: " + ", ".join("%s=%d" % (grade, bp)
                                   for grade, bp in pack["coverage_bp"].items()))
    for row in pack["disagreements"]:
        print("disagrees: %s %s" % (row["grade"], row["reason"]))