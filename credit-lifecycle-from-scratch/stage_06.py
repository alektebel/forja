"""Credit Lifecycle From Scratch — stage 6: The expected credit loss, its horizon and its scenarios.

A provision is not a number a bank feels its way to: it is three figures and a horizon
multiplied together and discounted, and every one of those four is a decision somebody
else has already made. This stage makes none of them, it reads them. The exposure comes
from stage 5's answer at the reporting date; the loss given default from stage 4's
answer where the loan has actually defaulted and from the model artifact where it has
not; the probability of default from the artifact's own term structure for the loan's
own rating of the loan; and the horizon from the stage the bank's own record has already
decided — twelve months while the loan is performing, and the whole remaining life of
the loan once its credit risk has increased, because that difference *is* the
difference between an exposure a bank expects to be repaid and one it does not.

The artifact is data and this stage does not fit one. It carries one cumulative
probability of default per year and per grade; a horizon falling between two years is
read linearly in months and truncated, and a horizon past the artifact's last entry
takes that entry rather than an extrapolation — the course has no library to interpolate
with and no business inventing a tail. The scenarios are the policy's too: each one
multiplies the *probability of default*, truncated and capped at one, because a scenario
is a statement about how many borrowers default rather than about how much is recovered,
and scaling the loss given default by it would charge the same stress twice.

Then the arithmetic, in one order and one order only. `loss_bp = pd_bp * lgd_bp //
10000`, `loss_cents = loss_bp * ead_cents // 10000`, then the discount, then the sum.
Three truncations in an order are not the same number as the same three in another
order, and the arithmetic a reviewer recomputes by hand is exactly this: two percentage
products in basis points, one cents product, and a discount at the loan's own effective
rate that steps one period at a time. A performing loan's single twelve-month loss is
discounted by one period; a loan whose credit risk has increased spreads its loss over
the periods it has left, in equal cents, each period discounted with its own step.

The last piece is the weighing. One ECL per scenario, in the policy's own order, each
weighted by the policy's own weight and summed with every product truncated first. And
weights that do not add up to the whole are refused rather than normalised: a policy
that does not add up is a data error, and normalising it would hide exactly the thing a
supervisor is looking for.

    ECL_KEYS                                 the nine fields of one provision, in order
    WEIGHTED_KEYS                            the five fields of the weighted provision
    SCENARIOS                                the three scenarios, in the policy's order
    SCENARIO_WEIGHTS_BP                      the policy's weight per scenario, in bp
    SCENARIO_PD_MULTIPLIER_BP                the policy's PD multiplier per scenario
    ecl(book, loan, date, scenario,
        stage=None, model=None)              -> ECL_KEYS at one scenario
    weighted_ecl(book, loan, date,
        stage=None, model=None)              -> WEIGHTED_KEYS over the policy's scenarios

DESIGN DECISION — why is the horizon read from the bank's record rather than decided
here? Because it is not this stage's decision and this stage cannot make it: whether an
exposure provisions its next twelve months or its whole life is what the significant
increase in credit risk decides, and that is stage 7's answer. So `ecl` asks the book
for the status it recorded for the loan at the date — the stage, and whether the loan
was in default — and measures the horizon that stage asks for: `PERIODS_PER_YEAR` while
the loan is performing, and the loan's remaining life, counted off the contractual
schedule and not assumed, once it is not. The two optional overrides exist for the
stages that have to recompute a provision the book did not book — the roll-forward
asking what the day's exposure would have provisioned under yesterday's stage, the
journal asking what it provisions under another artifact — and neither changes what
the pinned four-argument call answers.

DESIGN DECISION — why does a scenario multiply the probability of default? Because a
scenario is a statement about default frequency and about the path the economy takes,
and the three things the policy gives for it are a weight, a PD multiplier and nothing
else. Multiplying the loss given default instead would charge the same stress twice,
since an adverse scenario lowers the PD's denominator *and* would then lower what is
recovered on the same collateral; multiplying the finished ECL would make the scenario a
discount on the answer rather than an input to it, and the product's truncation would
move to a place the policy never put it. So the multiplier lands on the PD, truncated,
capped at 10000 — a scenario can stress a probability but it cannot make it exceed
certainty.

DESIGN DECISION — why is the multiplication order pinned, and why is the discounting
stage 1's? Because truncation is not associative: `pd * lgd // 10000 * ead // 10000` and
`pd * (lgd * ead // 10000) // 10000` are different integers, and the contract writes the
first. The loss is therefore built as a rate in basis points and only then turned into
cents, and the discount is not re-derived here at all: the flows are handed to stage 1's
`present_value`, which steps `factor = factor * 10000 // (10000 + period_rate_bp)` once
per flow and truncates at each step, so the rate that discounts the provision is the
loan's own effective rate — the one stage 1 searched for — and not the nominal one the
contract was written at.

DESIGN DECISION — why is a lifetime loss spread in equal cents rather than discounted
whole? Because the artifact gives one figure per year and a bank books it over the
periods that remain: the loss is divided by the number of remaining periods, each
period takes its equal share, and each share is discounted by its own step, so a
provision over a long remaining life is not the same number as one figure discounted
once to the end. The remainder of that division is not booked anywhere: a share is what
a period carries, and inventing a final period to hide the cents would be reporting a
number the policy never stated.

DESIGN DECISION — why are weights that do not sum to 10000 refused instead of
normalised? Because normalising them would answer a question the policy did not ask with
an answer nobody chose: a weight is a probability the bank attached to a scenario, and
if the three do not add up to one the policy is wrong, not the arithmetic. The refusal
names the sum it found, so the reader knows by how much; and a stage that silently
renormalised would make an ECL that no committee ever approved look perfectly ordinary.

TODO: implement `ecl` in this file: the horizon from the recorded stage, the artifact's
own PD read over that horizon and multiplied by the scenario's, the LGD from stage 4 or
from the model, the exposure from stage 5, and the loss multiplied in the pinned order
and discounted at the loan's effective rate.

TODO: implement `weighted_ecl` in this file: one `ecl` per scenario in the policy's own
order, the policy's weights in the same order, and the weighted total summed after each
product is truncated — or a refusal naming a weight set that does not add up to the
whole.
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


def ecl(book, loan, date, scenario, stage=None, model=None):
    """The expected credit loss of `loan` at `date` under one `scenario`.

    The stage is the book's own record for the date unless `stage` forces another, and
    the horizon follows the stage: twelve months for a performing loan, the loan's
    remaining life — measured off its contractual schedule — once its credit risk has
    increased. The probability of default is the artifact's own cumulative figure for
    the grade the artifact rates the loan at, over that horizon, multiplied by the scenario's PD
    multiplier, truncated and capped at 10000; the loss given default is stage 4's answer
    for a loan the record says was in default and the artifact's own figure otherwise;
    the exposure is stage 5's answer at the date. The loss is
    `pd_bp * lgd_bp // 10000`, then `loss_bp * ead_cents // 10000`, then discounted at
    the loan's effective rate with stage 1's stepwise truncation: one period for a
    performing loan's single twelve-month loss, and one step per remaining period for a
    loan that spreads its loss over its remaining life in equal cents. A `model` supplied
    by the caller replaces the artifact in force for the PD, the LGD *and* the exposure:
    the artifact's own `ccf_bp` for the loan's segment replaces stage 5's, so a
    counterfactual artifact is priced with its own exposure as well as its own PD.

    `scenario` must be one of `SCENARIOS`, `loan` must be one the book holds, and the
    artifact's `grades` must rate the loan; anything else raises
    `BookError` naming the offender.
    """
    raise NotImplementedError("stage 6: implement ecl()")


def weighted_ecl(book, loan, date, stage=None, model=None):
    """The scenario-weighted provision: one `ecl` per scenario, and the policy's weights.

    `scenario_ecls` is the ECL in cents of every scenario in `SCENARIOS` order and
    `weights_bp` the policy's weight for each of them in the same order, and
    `weighted_cents` is the sum of `ecl_cents * weight_bp // 10000` with every product
    truncated before it is added. Weights that do not sum to 10000 raise `BookError`
    naming what they did sum to — the policy is refused, not normalised.
    """
    raise NotImplementedError("stage 6: implement weighted_ecl()")
