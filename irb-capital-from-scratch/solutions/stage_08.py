"""IRB and Regulatory Capital — stage 8: The output floor, phased in.

An IRB bank's capital is bounded below by what a *standardized* bank would
report for the same exposures — the output floor — and the floor phases in:
a quarter of the proxy in the first regulated year, growing one seeded step a
year until it holds the whole thing. `irb.FLOOR_PHASE_PERCENT` is that
schedule as data — an integer percent per calendar year — and `phase(year)`
answers the row or refuses a year outside the schedule by name.

The floor binds per exposure, not in aggregate: each loan's own IRB risk
weight is set against the same loan's share of the standardized proxy —
the proxy is `ead * STANDARD_WEIGHT_BP[class] // 10000` at the class row the
policy provides (a fixed table, never computed from anything the course
produced), and the share is `proxy * percent // 100`, truncated. The
exposure files the greater of the two, and the totals fall out of the rows:
the floor's own total is the sum of the shares, the bank's own total is the
sum of the weights, and the applied answer is the sum of what each exposure
files.

What the schedule is precise about, the fixtures are precise about: in 2028 the
floor is a quarter of the proxy, and the estate has its own exposure-level
answers in both directions — a loan the floor already holds up at 25%, and a
year in which nothing binds and the bank files its own weights. The year 2031
is the one the pack files `floor` over: 60% of the proxy and the two loans it
holds up name themselves in the totals.
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

#: The schedule itself, as the policy carries it — a percent per calendar year.
FLOOR_PHASE_PERCENT = irb.FLOOR_PHASE_PERCENT

#: The standardized proxy's own weights per asset class, in basis points.
STANDARD_WEIGHT_BP = irb.STANDARD_WEIGHT_BP

#: The asset classes the proxy weights are keyed on, in their own order.
CLASSES = irb.CLASSES

#: The years the schedule runs over, pinned for the refusal's message.
YEARS = tuple(sorted(FLOOR_PHASE_PERCENT))

#: The two ways a bank files: the floor's answer, or its own weights.
FILES = ("floor", "own")

#: The fields of the applied record, in order.
APPLIED_KEYS = ("at", "year", "percent", "exposures", "own_rwa_cents",
                "floor_rwa_cents", "applied_rwa_cents", "bound_exposures", "files")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class FloorError(PolicyError):
    """The refusal this stage raises: something that cannot be a floor answer.

    It names the offender — the year outside the schedule, the date the book
    does not cover, the artifact of stage 7 the estate cannot produce — because
    a filing the schedule does not hold must say what it was asked for rather
    than answer one phase-in early or late.
    """


def phase(year):
    """The percent of the proxy the floor holds in `year`, from the schedule.

    The schedule is the policy's own table: `2028` answers one quarter, `2035`
    the whole of it, each integer percent as the year's row. A year outside the
    schedule — before `min(YEARS)` or after `max(YEARS)` — is refused by name,
    naming the years the schedule does hold, because a floor applied one year
    early is precisely the filing a supervisor reads for.
    """
    if isinstance(year, bool) or not isinstance(year, int):
        raise FloorError("the year %r is a %s, not a whole calendar year"
                         % (year, type(year).__name__))
    if year not in FLOOR_PHASE_PERCENT:
        raise FloorError("the output floor's schedule holds %d..%d and %d is not a "
                         "year it phases in" % (min(YEARS), max(YEARS), year))
    return FLOOR_PHASE_PERCENT[year]


def _loan_id(loan):
    """The identity a loan arrives under, as the book's records name it."""
    if isinstance(loan, dict) and "loan" in loan:
        return loan["loan"]
    return loan


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
    """`(rw_bp, ead_cents)` — stage 7's weight and exposure, recomputed locally."""
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
    return rw_bp, ead_cents


def _live_with_term(book, at):
    """The loans on the book at `at` with a remaining term, in estate order."""
    live = []
    for loan_id in book.on_book(at):
        months = _months_between(at, book.schedule(loan_id)["flows"][-1]["date"])
        if months > 0:
            live.append(loan_id)
    return tuple(live)


def applied(book, at, year):
    """The floor's answer for `at` at `year`, exposure by exposure.

    The record carries the year's percent, the loans the floor prices — the
    ones on the book at `at` with a remaining term — and the three totals the
    rows produce: the bank's own risk-weighted amount, the floor's total (the
    sum of the shares the schedule asks of each exposure), and the applied
    answer, which is the sum of what each exposure *files* — its own weight or
    the floor's share, whichever is greater. `bound_exposures` names how many
    loans floor holds above their own weight, and `files` answers
    `"floor"` when at least one does and `"own"` when none does, because the
    proposal a bank submits names which of the two answers it filed — an
    aggregate-only floor would hide the loans the profits were taken from.

    A year outside the schedule and a date the book does not cover are refused
    by name.
    """
    percent = phase(year)
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise FloorError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise FloorError("no regulatory artifact is in force at %s, so the estate "
                         "has no risk weights to compare the floor with" % (at,))
    own_total = 0
    floor_total = 0
    applied_total = 0
    bound = 0
    exposures = 0
    for loan_id in _live_with_term(book, at):
        held = book.loan(loan_id)
        rw_bp, ead_cents = _k_rwa(book, held, at, model)
        asset_class, _treatment = irb.ASSET_CLASS_OF[held["segment"]]
        proxy = ead_cents * STANDARD_WEIGHT_BP[asset_class] // BP_SCALE
        share = proxy * percent // 100
        own = rw_bp * ead_cents // BP_SCALE
        exposures += 1
        own_total += own
        floor_total += share
        applied_total += max(own, share)
        if share > own:
            bound += 1
    return {"at": at, "year": year, "percent": percent, "exposures": exposures,
            "own_rwa_cents": own_total, "floor_rwa_cents": floor_total,
            "applied_rwa_cents": applied_total, "bound_exposures": bound,
            "files": "floor" if bound else "own"}


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    print("year | percent")
    for year in YEARS:
        print("%d | %d" % (year, phase(year)))
    try:
        phase(2027)
    except FloorError as refused:
        print("refused: %s" % (refused,))
    print()
    for at in (led.reporting_dates[0], led.reporting_dates[12], led.reporting_dates[13]):
        for year in (2028, 2031):
            record = applied(led, at, year)
            print("%s | %d%% | own %d | floor %d | applied %d | bound %d | files %r"
                  % (at, record["percent"], record["own_rwa_cents"],
                     record["floor_rwa_cents"], record["applied_rwa_cents"],
                     record["bound_exposures"], record["files"]))
