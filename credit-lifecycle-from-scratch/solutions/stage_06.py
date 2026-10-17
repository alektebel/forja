"""Credit Lifecycle From Scratch — stage 6: The expected credit loss, its horizon and its scenarios.

Three figures and a horizon, multiplied in one pinned order and discounted at the loan's
own effective rate. The stage is the book's own record for the date — stage 7's answer
as the bank booked it, never re-decided here — and the horizon follows it: twelve months
while the loan performs, the loan's remaining life, measured off the contractual
schedule, once its credit risk has increased. The exposures and the loss given default
come from stage 5 and stage 4; the probability of default comes from the artifact in
force at the date, read linearly in months and truncated, and multiplied by the
scenario's own multiplier rather than the loss given default's. Then `loss_bp = pd_bp *
lgd_bp // 10000`, `loss_cents = loss_bp * ead_cents // 10000`, then the discount, then
the sum — because three truncations in an order are a different number from the same
three in another order, and a supervisor recomputes this one by hand.

The two optional keywords exist for the stages that have to recompute a provision the
book never booked: `stage` forces the horizon a counterfactual would use, and `model`
supplies the artifact whose PD, LGD and CCF are read instead of the ones in force. Left
out, they mean exactly the pinned four-argument call.
"""

import dates
import rules
import stage_01
import stage_04
import stage_05
from book import BookError

ECL_KEYS = ("loan", "date", "stage", "horizon_months", "pd_bp", "lgd_bp", "ead_cents",
            "ecl_cents", "scenario")

WEIGHTED_KEYS = ("loan", "date", "scenario_ecls", "weights_bp", "weighted_cents")

SCENARIOS = rules.SCENARIOS

SCENARIO_WEIGHTS_BP = rules.SCENARIO_WEIGHTS_BP

SCENARIO_PD_MULTIPLIER_BP = rules.SCENARIO_PD_MULTIPLIER_BP

_STAGES = (1, 2, 3)


def _loan_id(loan):
    """The identifier the course's own records key a loan by."""
    try:
        return loan["loan"]
    except (KeyError, TypeError):
        raise BookError("a loan the bank cannot key: %r" % (loan,))


def _record(book, loan, date):
    """The bank's own record for the loan at the date, with the two fields this stage reads.

    The stage and the default flag are the book's, not this stage's: whether an exposure
    provisions twelve months or its whole life is stage 7's decision, and whether a loan
    has defaulted is stage 2's, and neither is re-decided here.
    """
    record = book.status(loan, date)
    if not isinstance(record, dict) or "stage" not in record or "default" not in record:
        raise BookError("the book records no stage and default for %s at %s"
                        % (_loan_id(loan), date))
    return record


def _stage_number(record, loan, date):
    """The stage the bank recorded, as a number."""
    stage = record["stage"]
    if isinstance(stage, str) and stage.isdigit():
        stage = int(stage)
    if stage not in _STAGES:
        raise BookError("the book records the stage %r for %s at %s"
                        % (record["stage"], _loan_id(loan), date))
    return stage


def _remaining(book, loan, date):
    """The loan's remaining contractual periods: the schedule's flows strictly after the date."""
    flows = stage_01.schedule(book, loan)["flows"]
    return tuple(flow for flow in flows if flow["date"] > date)


def _horizon(book, loan, date, stage):
    """The horizon the stage asks for: twelve months, or the loan's remaining life."""
    if stage == 1:
        return rules.PERIODS_PER_YEAR
    return len(_remaining(book, loan, date))


def _roster(book):
    """Every artifact the book holds, in the book's own order."""
    models = book.models
    return tuple(models() if callable(models) else models)


def _version_key(version):
    """A version, made comparable: a count, or the dotted counts an artifact writes it in."""
    if isinstance(version, int):
        return (version,)
    return tuple(int(piece) if piece.isdigit() else 0
                 for piece in str(version).split("."))


def _in_force(book, date):
    """The artifact in force at the date: the greatest `as_of` not after it, greater `version` winning.

    A loan's provision is measured under the artifact that was in force when the date was
    reported, not under whichever version happens to be last on the book's shelf.
    """
    rows = [row for row in _roster(book) if row["as_of"] <= date]
    if not rows:
        raise BookError("no model artifact is in force at %s" % (date,))
    newest = max(row["as_of"] for row in rows)
    rows = [row for row in rows if row["as_of"] == newest]
    return max(rows, key=lambda row: _version_key(row["version"]))


def _model_pd(model, grade, months):
    """The artifact's own cumulative PD for a grade over a horizon in months.

    The artifact carries one cumulative PD per year. A horizon that falls between two
    years is read linearly in months and truncated, and a horizon past the artifact's own
    last entry takes that entry rather than an extrapolation — the model is data and this
    stage does not fit one.
    """
    series = model["pd_bp"][grade]
    whole = months // 12
    rest = months - whole * 12
    if whole >= len(series):
        return series[-1]
    if whole == 0:
        return series[0] * months // 12
    left = series[whole - 1]
    if rest == 0:
        return left
    return left + (series[whole] - left) * rest // 12


def _scenario_pd(model, grade, months, scenario):
    """The artifact's PD over the horizon, scaled by the scenario's own multiplier."""
    if scenario not in SCENARIO_PD_MULTIPLIER_BP:
        raise BookError("the policy holds no PD multiplier for the %s scenario" % (scenario,))
    pd_bp = _model_pd(model, grade, months) * SCENARIO_PD_MULTIPLIER_BP[scenario] // 10000
    if pd_bp > 10000:
        pd_bp = 10000
    return pd_bp


def _model_grade(model, loan):
    """The grade the artifact rates this loan at: the model's own rating, never the origination one.

    A model artifact carries its own view of the portfolio — `grades` maps a loan to the
    grade the model rates it at — and the provision is measured on that grade, so a model
    that cannot rate a loan is refused rather than measured on somebody else's grade.
    """
    loan_id = _loan_id(loan)
    if loan_id not in model["grades"]:
        raise BookError("the model %s %s does not rate %s"
                        % (model["name"], model["version"], loan_id))
    return model["grades"][loan_id]


def _model_lgd(model, grade):
    """The artifact's own LGD for a grade."""
    if grade not in model["lgd_bp"]:
        raise BookError("the model %s %s holds no LGD for the grade %s"
                        % (model["name"], model["version"], grade))
    return model["lgd_bp"][grade]


def _model_ccf(model, segment):
    """The artifact's own CCF for a segment."""
    if segment not in model["ccf_bp"]:
        raise BookError("the model %s %s holds no CCF for the segment %s"
                        % (model["name"], model["version"], segment))
    return model["ccf_bp"][segment]


def _exposure(book, loan, date, model):
    """The exposure at the date: stage 5's answer, its CCF replaced by the artifact's when one is given."""
    record = stage_05.ead(book, loan, date)
    if model is None:
        return record["ead_cents"]
    return (record["drawn_cents"]
            + record["undrawn_cents"] * _model_ccf(model, loan["segment"]) // 10000)


def _loss_cents(pd_bp, lgd_bp, ead_cents):
    """The undiscounted loss in cents: the contract's two products, in its own order."""
    loss_bp = pd_bp * lgd_bp // 10000
    return loss_bp * ead_cents // 10000


def _discounted(book, loan, date, stage, loss_cents):
    """The loss discounted at the loan's effective rate, stepped the way stage 1 steps it.

    A performing loan's single twelve-month loss is discounted by one period; a loan whose
    credit risk has increased spreads its loss over the periods it has left, in equal
    cents, and each period's share is discounted with its own step.
    """
    rate = stage_01.effective_rate(book, loan)
    if stage == 1:
        flows = ({"date": dates.add_months(date, rules.PERIODS_PER_YEAR),
                  "amount_cents": loss_cents},)
    else:
        remaining = _remaining(book, loan, date)
        if not remaining:
            return 0
        share = loss_cents // len(remaining)
        flows = tuple({"date": flow["date"], "amount_cents": share}
                      for flow in remaining)
    return stage_01.present_value(flows, rate["eir_bp"], rate["basis"])


def _weights():
    """The policy's weight for every scenario, in the policy's order, or a refusal."""
    weights = []
    for scenario in SCENARIOS:
        if scenario not in SCENARIO_WEIGHTS_BP:
            raise BookError("the policy holds no weight for the %s scenario" % (scenario,))
        weights.append(SCENARIO_WEIGHTS_BP[scenario])
    weights = tuple(weights)
    if sum(weights) != rules.DISCOUNT_SCALE:
        raise BookError("the scenario weights sum to %d basis points, not %d"
                        % (sum(weights), rules.DISCOUNT_SCALE))
    return weights


def ecl(book, loan, date, scenario, stage=None, model=None):
    """The expected credit loss of `loan` at `date` under one `scenario`.

    The stage is the book's own record for the date unless `stage` forces another, and
    the horizon follows the stage: twelve months for a performing loan, the loan's
    remaining life — measured off its contractual schedule — once its credit risk has
    increased. The probability of default is the artifact's own cumulative figure for the
    grade the artifact rates the loan at, read over that horizon and multiplied by the
    scenario's PD multiplier, truncated and capped at 10000; the loss given default is
    stage 4's answer for a loan the record says was in default and the artifact's own
    figure otherwise; the exposure is stage 5's answer at the date, with the artifact's
    CCF in place of stage 5's when `model` is given. The loss is `pd_bp * lgd_bp //
    10000`, then `loss_bp * ead_cents // 10000`, then discounted at the loan's effective
    rate with stage 1's stepwise truncation: one period for a performing loan's single
    twelve-month loss, and one step per remaining period for a loan that spreads its loss
    over its remaining life in equal cents.

    `scenario` must be one of `SCENARIOS`, `loan` must be one the book holds, and the
    artifact must rate the loan; anything else raises `BookError` naming the offender.
    """
    if scenario not in SCENARIOS:
        raise BookError("the scenario %r is not one of %s" % (scenario, SCENARIOS))
    if stage is not None and stage not in _STAGES:
        raise BookError("the stage %r is not one of %s" % (stage, _STAGES))
    supplied = model
    loan_id = _loan_id(loan)
    record = _record(book, loan, date)
    if stage is None:
        stage = _stage_number(record, loan, date)
    if model is None:
        model = _in_force(book, date)
    grade = _model_grade(model, loan)
    horizon = _horizon(book, loan, date, stage)
    pd_bp = _scenario_pd(model, grade, horizon, scenario)
    if record["default"]:
        lgd_bp = stage_04.lgd(book, loan)["lgd_bp"]
    else:
        lgd_bp = _model_lgd(model, grade)
    ead_cents = _exposure(book, loan, date, supplied)
    loss_cents = _loss_cents(pd_bp, lgd_bp, ead_cents)
    return {"loan": loan_id, "date": date, "stage": stage,
            "horizon_months": horizon, "pd_bp": pd_bp, "lgd_bp": lgd_bp,
            "ead_cents": ead_cents,
            "ecl_cents": _discounted(book, loan, date, stage, loss_cents),
            "scenario": scenario}


def weighted_ecl(book, loan, date, stage=None, model=None):
    """The scenario-weighted provision: one `ecl` per scenario, and the policy's weights.

    `scenario_ecls` is the ECL in cents of every scenario in `SCENARIOS` order and
    `weights_bp` the policy's weight for each of them in the same order, and
    `weighted_cents` is the sum of `ecl_cents * weight_bp // 10000` with every product
    truncated before it is added. Weights that do not sum to 10000 raise `BookError`
    naming what they did sum to — the policy is refused, not normalised.
    """
    if stage is not None and stage not in _STAGES:
        raise BookError("the stage %r is not one of %s" % (stage, _STAGES))
    weights = _weights()
    ecls = tuple(ecl(book, loan, date, scenario, stage=stage, model=model)["ecl_cents"]
                 for scenario in SCENARIOS)
    weighted_cents = 0
    for cents, weight_bp in zip(ecls, weights):
        weighted_cents += cents * weight_bp // 10000
    return {"loan": _loan_id(loan), "date": date, "scenario_ecls": ecls,
            "weights_bp": weights, "weighted_cents": weighted_cents}
