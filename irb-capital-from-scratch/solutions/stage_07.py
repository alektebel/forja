"""IRB and Regulatory Capital — stage 7: Risk weight and the RWA.

A capital requirement prices an exposure at a **risk weight**, and the risk
weight is where the whole formula lands: the series K of stage 4, the maturity
adjustment of stage 3, and the scaling constant the policy holds for itself —
`12.5` carried in ten-thousandths as `CAPITAL_SCALING_BP` — multiplied
together and set against the exposure at default the stage-6 arithmetic
answers. The record arrives exactly as the supervisor wants to read it: the
loan, the asset class it prices to, the weight in basis points, and the
risk-weighted amount in cents — `rw_bp * ead_cents // 10000`, one division,
pinned.

The whole book is then a total, and the stage makes the total defensible: it
runs over the loans on the book at the reporting date that still have a
remaining term, and it answers the per-class split of the same rows — the
sum of the very risk weights it just computed, keyed by `irb.CLASSES`, with a
class that prices nothing in the estate still answered as a zero row rather
than dropped, so a reader sees the empty class rather than missing it.

What this stage refuses is a loan that is not on the book at all (a
derecognised holding carries no RWA), a loan past its remaining term (no term,
no weight), and a date the book does not cover — by name, as everywhere in
this course.
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

#: The asset classes the formula prices, in their own order.
CLASSES = irb.CLASSES

#: The scaling constant, `12.5` in ten-thousandths: the policy's own number.
CAPITAL_SCALING_BP = irb.CAPITAL_SCALING_BP

#: The clamps an effective maturity lives between, in whole years.
M_MIN = irb.M_MIN

M_MAX = irb.M_MAX

#: The drawn/undrawn conversion factors, as the policy carries them.
CCF_BY_PRODUCT_BP = irb.CCF_BY_PRODUCT_BP

#: The fields of one risk-weight record, in order.
RW_KEYS = ("loan", "asset_class", "rw_bp", "ead_cents", "rwa_cents")

#: The fields of the whole-book total, in order.
RWA_KEYS = ("at", "exposures", "total_rwa_cents", "by_class")

#: The scale every rate and basis-point measure is held at.
BP_SCALE = 10000


class RwaError(PolicyError):
    """The refusal this stage raises: something that cannot be a risk weight.

    It names the offender — the loan the book does not hold, one not on the
    book at the reporting date, one past its remaining term, the date the book
    does not cover, the artifact the stage would need and does not find —
    because a weight the formula cannot stand behind must say what it was asked
    for rather than answer one a reviewer cannot walk.
    """


# -- the K and the exposure, recomputed -------------------------------------

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
    """The loan's downturn LGD: recoveries when defaulted with the class multiplier.

    Stage 5's order pinned — haircut, discount, clamp, and only then the
    multiplier, skipped for `refrigerate` — recomputed locally so the weight
    stands on the policy without reading any stage of this course.
    """
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


def _k_series(held, at, flows, lgd_bp, series):
    """`(marginals, discounted, term_years)` — stage 4's series, recomputed locally."""
    last = flows[-1]["date"]
    months = _months_between(at, last)
    term_years = min(M_MAX, max(M_MIN, (months + 11) // 12))
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
        factor = factor * BP_SCALE // (BP_SCALE + held["rate_bp"])
        discounted.append((marginal * lgd_bp // BP_SCALE) * factor // BP_SCALE)
    return marginals, discounted, term_years


def _be_ead(book, held, at):
    """The best-estimate exposure at `at` — stage 6's arithmetic, recomputed.

    The drawn cash floored, the undrawn limit after paying ahead is consumed,
    and the product row converting the undrawn part with one truncated
    division.
    """
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
    for flow in book.schedule(held)["flows"]:
        if flow["date"] <= at:
            plan += flow["amount_cents"]
    undrawn = max(0, held["undrawn_limit_cents"] - max(0, drawn - plan))
    ccf_bp = CCF_BY_PRODUCT_BP[held["segment"]]
    return drawn + undrawn * ccf_bp // BP_SCALE


def _in_force(book, at):
    """The artifact in force at `at`, or a refusal naming the date."""
    try:
        model = book.model_in_force(at)
    except BookError as refused:
        raise RwaError("no artifact is in force at %s (%s)" % (at, refused))
    if model is None:
        raise RwaError("no regulatory artifact is in force at %s" % (at,))
    return model


# -- the stage's own surface ------------------------------------------------

def risk_weight(book, loan, at):
    """The risk weight of `loan` at `at`: K, the maturity adjustment and `12.5`.

    The weight is the capital series of stage 4 — the year-by-year sum of
    marginal PDs, downturn LGDs and discounted shares — lifted by the maturity
    adjustment `10000 + (2 * m - 5) * b // 2` at the whole years the loan has
    left, scaled by the policy's own `12.5` in ten-thousandths with one
    truncated division: `k_bp * mf * CAPITAL_SCALING_BP // (10000 * 10000)`.
    The record carries the weight, the exposure stage 6 answers and the
    risk-weighted amount `rw_bp * ead_cents // 10000`.

    A loan not on the book at `at`, a loan past its remaining term, a date the
    book does not cover, or an asset class the policy does not price is
    refused by name.
    """
    loan_id = _loan_id(loan)
    try:
        live = book.on_book(at)
    except BookError as refused:
        raise RwaError("the estate at %s is not there to read (%s)" % (at, refused))
    if loan_id not in live:
        raise RwaError("loan %r is not on the book at %s" % (loan_id, at))
    try:
        held = book.loan(loan_id)
    except BookError as refused:
        raise RwaError("the book does not hold loan %r (%s)" % (loan_id, refused))
    model = _in_force(book, at)
    try:
        grade = model["grades"][loan_id]
    except KeyError:
        raise RwaError("the artifact %r v%d in force at %s carries no grade for loan "
                       "%r" % (model["name"], model["version"], at, loan_id))
    lgd_bp = _downturn_lgd(book, loan_id, held, at, model)
    flows = book.schedule(held)["flows"]
    months = _months_between(at, flows[-1]["date"])
    if months <= 0:
        raise RwaError("loan %r stands past its remaining term at %s"
                       % (loan_id, at))
    series = model["pd_bp"][grade]
    _marginals, discounted, term_years = _k_series(held, at, flows, lgd_bp, series)
    k_bp = sum(discounted)
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
    rw_bp = k_bp * mf * CAPITAL_SCALING_BP // (BP_SCALE * BP_SCALE)
    ead_cents = _be_ead(book, held, at)
    return {"loan": loan_id,
            "asset_class": asset_class,
            "rw_bp": rw_bp,
            "ead_cents": ead_cents,
            "rwa_cents": rw_bp * ead_cents // BP_SCALE}


def total_rwa(book, at):
    """The whole book's risk-weighted amount at `at`, and its split by class.

    The loans on the book at `at` that still have a remaining term — a matured
    holding is out of the estate's own risk, at least until someone writes a
    policy for it — each priced at `risk_weight`, and the answer is the sum and
    the per-class split **of those same rows**: no row is recomputed at a
    different rate, no class is keyed on anything but `irb.CLASSES`, and a
    class that prices nothing answers a zero row instead of being dropped, so a
    reader sees the empty class rather than missing it.

    A date the book does not cover is refused by name; so is the artifact the
    stage would need and does not find.
    """
    model = _in_force(book, at)
    by_class = dict((asset_class, 0) for asset_class in CLASSES)
    exposures = 0
    total = 0
    for loan_id in book.on_book(at):
        months = _months_between(at, book.schedule(loan_id)["flows"][-1]["date"])
        if months <= 0:
            continue
        record = risk_weight(book, loan_id, at)
        by_class[record["asset_class"]] += record["rwa_cents"]
        total += record["rwa_cents"]
        exposures += 1
    return {"at": at, "exposures": exposures, "total_rwa_cents": total,
            "by_class": by_class}


if __name__ == "__main__":
    import book
    led = book.Book.build(7)
    for at in (led.reporting_dates[0], led.reporting_dates[13], led.reporting_dates[24]):
        record = total_rwa(led, at)
        print("--- %s   exposures %d   total %d"
              % (at, record["exposures"], record["total_rwa_cents"]))
        print("loan | class          | rw    | ead      | rwa")
        for loan_id in led.on_book(at):
            try:
                row = risk_weight(led, loan_id, at)
                print("%-5s | %-14s | %d | %d | %d"
                      % (row["loan"], row["asset_class"], row["rw_bp"],
                         row["ead_cents"], row["rwa_cents"]))
            except RwaError as refused:
                print("%-5s | refused: %s" % (loan_id, refused))
        print("by class: " + ", ".join("%s=%d" % (name, cents)
                                       for name, cents
                                       in sorted(record["by_class"].items())))
