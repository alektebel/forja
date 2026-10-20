"""Credit Origination From Scratch — stage 1: Affordability and the debt-service arithmetic.

Before a loan exists it is an application, and the bank's first arithmetic is a
decision: does the payment the applicant is asking for fit the income the
applicant can prove? This stage answers exactly that question, in the two halves
the policy says the test has — a debt-service ratio that may not clear the cap,
and a leftover that may not fall below the floor — and reports the record a
credit committee reads: what was asked, what was proven, what the service is, and
which half fired when it fired.

The payment in that service is the level payment of the **requested** amount at
the **proposed** rate (`policy.PROPOSED_RATE_BP[purpose]`) over the requested
term, and it is **searched, not solved**: the balance is truncated to the cent at
every step and the interest is `balance * period_rate // 10000`, so the
instalment that clears the loan is the smallest integer one and no closed form
can know it. `payment` bisects whole cents the way the bank booked its contracts
(`cases.py`'s own ledger is built from the same search), and stage 1 prices the
fit at the words the applicant walked in with, not at what the bank would sell.

The obligations are turned into monthly cash at the frequency the applicant
states them: a monthly charge is its amount, an annual one is consumed over
twelve monthly pieces — `amount_cents // 12`, truncating, the dropped cent being
the applicant's own rounding and not something the arithmetic hides. The ratio
half and the leftover half bound the same household from two sides, and either
can fail while the other passes: the estate holds an application for each
direction, and `CO-10` sits exactly on `policy.DSR_CAP_BP`, kept there by the
truncation the contract pins — which is why the cap is inclusive and checked
against the recomputed ratio, never a rounded one.

    FIT_KEYS                       the ten fields of a fit record, in order
    FREQUENCIES                    the two frequencies an obligation is stated in
    FIT_VERDICTS                   the five verdicts the two halves can answer
    DSR_SCALE_BP                   the scale the ratio is taken at — 100% is it
    AffordError                    the refusal this stage raises
    affordability(cases, id)       -> FIT_KEYS: the two halves, decided
    calendar_monthly(amount, freq) -> int: the monthly cash an obligation costs
    payment(cases, amount, rate, term)
                                   -> int: the smallest level payment that clears

DESIGN DECISION — why is the level payment searched for rather than computed?
Because the contract's amortisation is not the annuity formula's: the balance is
truncated to the cent at every step and the interest is charged on the balance
the period *opens* with, so the instalment that actually clears the loan is the
smallest integer one, and the only honest way to name it is to walk the balance
for each candidate. `payment` bisects whole cents and asks, for each candidate,
whether the walk ends at or below zero within the term — a fact a reviewer with a
pencil reproduces, and the same walk the bank booked its facilities with. A
formula would answer a cent off on some loans and the estate's own ledger would
disagree with it.

DESIGN DECISION — why are the ratio and the leftover two halves of one test?
Because they bound the same household from two sides and neither implies the
other: a high earner with an enormous charge has a ratio inside the cap and a
leftover below the floor; a modest earner with a small charge keeps a healthy
leftover over a ratio that is a hair over. The policy pins both (`DSR_CAP_BP`,
`AFFORD_FLOOR_CENTS`) and the record answers both halves' numbers — ratio,
leftover, service — so the committee can see *which* half fired and by how much.
A stage that takes either half alone is wrong twice, and the estate holds an
application for each direction.

DESIGN DECISION — why is the fit priced at the verified income and the declared
one only reported? Because the bank lends against what the applicant can *prove*,
not what the applicant said: `verified_income_cents` is the denominator of the
ratio and the source of the leftover, and `declared_income_cents` is a field the
record carries so the gap between what was said and what was proven is data the
record reports, not scandal it hides. Where the two disagree — and the estate
disagrees them on most applications — a stage that scores the declared one
answers a number the bank's own decision does not recognise.

DESIGN DECISION — why does the record floor the leftover at zero but read the
half-test on the raw difference? Because the two have different jobs: the
record's `leftover_cents` is an audited figure, and an audited figure of minus
cents reads as an error of the record rather than a condition of the household —
so it is floored at zero. The half-test is the other way: a household whose
service exceeds its income is *under water*, and the verdict names that
(`"under-water"`) rather than letting a floored zero dress a breach up as an
ordinary miss of the floor. The negative is visible in the verdict's own reason.

DESIGN DECISION — why is an unknown frequency refused instead of guessed?
Because `FREQUENCIES` is the policy's own vocabulary of how an obligation is
stated, and an annual charge read as monthly — or a quarterly one read as either
— changes the applicant's affordability more than the rate does. The turn happens
here, once, at the frequency the applicant stated, and anything outside the
vocabulary is refused by name: the monthly figure of an obligation is arithmetic
this stage owns, and a stage that silently averages a charge it cannot read
answers a fit nobody can audit.

TODO: implement `AffordError`-refusing `calendar_monthly`, `payment` and
`affordability` in this file: the monthly turn of an obligation at the frequency
it was stated in, the smallest whole-cent level payment whose truncated
amortisation clears the requested amount at the proposed rate, and the two
halves of the fit decided against the verified income.

    A fit is refused by name when the application id is unknown to the estate (the
    estate's own refusal), when the purpose carries no proposed rate, when an
    obligation is stated at a frequency outside `FREQUENCIES`, and when the
    verified income is not a positive count of cents. A payment is refused by
    name when the principal is below one cent, when the rate is outside
    `0..DSR_SCALE_BP`, and when the term is below one month.
"""

import policy

FIT_KEYS = ("id", "verified_income_cents", "declared_income_cents",
            "obligations_monthly_cents", "payment_cents", "service_cents",
            "fit_bp", "leftover_cents", "verdict", "fits")

FREQUENCIES = policy.FREQUENCIES

FIT_VERDICTS = ("clear", "over-the-cap", "under-the-floor", "over-both",
                "under-water")

DSR_SCALE_BP = 10000

_BP = DSR_SCALE_BP

_DAYS_PER_PERIOD = 30

_DAYS_PER_YEAR = 360

_MONTHS_PER_YEAR = 12

AFFORD_ERROR = "affordability: "


class AffordError(ValueError):
    """The refusal this stage raises: something that cannot be a fit.

    It names the offender — the obligation stated at a frequency outside
    `FREQUENCIES`, the amount that is not a count of cents, the principal below
    one cent, the rate outside `0..DSR_SCALE_BP`, the term below one month, the
    purpose the policy carries no proposed rate for, the verified income that is
    not a positive count — because the bank's first arithmetic must say what it
    was asked for rather than answer a number nobody can defend.
    """


def _whole(value, what):
    """A whole count, or a refusal naming what arrived in its place."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AffordError(AFFORD_ERROR + ("%s %r is a %s, not a whole count"
                                          % (what, value, type(value).__name__)))
    return value


def _positive_cents(value, what):
    """A count of cents a debt or a payment can be carried in."""
    cents = _whole(value, what)
    if cents < 0:
        raise AffordError(AFFORD_ERROR + ("%s %d is negative, and nothing a bank "
                                          "counts is" % (what, cents)))
    return cents


def _checked_rate(rate_bp):
    """The rate as a whole count of basis points inside `0..DSR_SCALE_BP`."""
    rate = _whole(rate_bp, "the rate")
    if rate < 0 or rate > DSR_SCALE_BP:
        raise AffordError(AFFORD_ERROR + ("the rate %d is outside 0..%d basis "
                                          "points" % (rate, DSR_SCALE_BP)))
    return rate


def _checked_term(term_months):
    """The term as a whole count of months, at least one."""
    term = _whole(term_months, "the term")
    if term < 1:
        raise AffordError(AFFORD_ERROR + ("the term %d is below one month"
                                          % (term,)))
    return term


def _checked_principal(amount_cents):
    """The principal as a whole count of cents, at least one."""
    principal = _positive_cents(amount_cents, "the principal")
    if principal < 1:
        raise AffordError(AFFORD_ERROR + ("the principal %d is below one cent"
                                          % (principal,)))
    return principal


def _checked_frequency(frequency):
    """A frequency the policy names, refused by name when it does not."""
    if frequency not in FREQUENCIES:
        raise AffordError(AFFORD_ERROR + ("the frequency %r is not one of %r"
                                          % (frequency, FREQUENCIES)))
    return frequency


def _period_bp(rate_bp):
    """The rate per monthly period: a month is thirty days of a 360-day year."""
    return rate_bp * _DAYS_PER_PERIOD // _DAYS_PER_YEAR


def _walk(principal_cents, period, payment_cents, term_months):
    """The balance the walk leaves after `term_months` periods, at most.

    Interest is charged on the balance the period opens with, truncated to the
    cent, and the payment is taken off after it — the bank's own order. A
    balance already at or below zero ends the walk early, so the answer is at
    or below zero exactly when the payment clears the loan within its term.
    """
    balance = principal_cents
    for _ in range(term_months):
        if balance <= 0:
            return balance
        balance = balance + balance * period // _BP - payment_cents
    return balance


def calendar_monthly(amount_cents, frequency):
    """The monthly cash an obligation costs, at the frequency it was stated in.

    A `monthly` obligation is its own amount; an `annual` one is consumed over
    twelve monthly pieces, `amount_cents // 12`, truncating — the remainder is
    the applicant's own rounding, dropped deliberately by the policy the estate
    states. A frequency outside `FREQUENCIES`, or an amount that is not a whole
    count of cents, is refused by name.
    """
    _checked_frequency(frequency)
    amount = _positive_cents(amount_cents, "the obligation")
    if frequency == "annual":
        return amount // _MONTHS_PER_YEAR
    return amount


def payment(cases, amount_cents, rate_bp, term_months):
    """The smallest whole-cent payment whose amortisation clears the loan.

    The level payment of `amount_cents` at `rate_bp` over `term_months` months:
    interest is charged on the balance the period opens with —
    `balance * period_rate_bp // 10000`, truncated, a month being thirty days of
    a 360-day year (`period_rate_bp = rate_bp * 30 // 360`) — and the payment is
    taken off after it. The answer is the smallest integer payment whose walk
    ends at or below zero within the term. It is bisected, not computed, and the
    same walk the bank booked its own facilities with.

    A rate outside `0..DSR_SCALE_BP`, a term below one month, or a principal
    below one cent is refused by name. The estate is taken to refuse what the
    policy refuses; the arithmetic itself reads no record of it.
    """
    principal = _checked_principal(amount_cents)
    period = _period_bp(_checked_rate(rate_bp))
    term = _checked_term(term_months)
    low = 0
    high = 2 * principal
    while low < high:
        middle = (low + high) // 2
        if _walk(principal, period, middle, term) <= 0:
            high = middle
        else:
            low = middle + 1
    return low


def _proposed_rate(purpose):
    """The rate the proposal walked in at, refused by name for a stranger."""
    if purpose not in policy.PROPOSED_RATE_BP:
        raise AffordError(AFFORD_ERROR + ("the purpose %r is not one the policy "
                                          "carries a proposed rate for"
                                          % (purpose,)))
    return policy.PROPOSED_RATE_BP[purpose]


def _verified_income(income_cents):
    """The proven income as a positive count of cents, refused otherwise."""
    income = _positive_cents(income_cents, "the verified income")
    if income < 1:
        raise AffordError(AFFORD_ERROR + ("the verified income %d is below one "
                                          "cent, and nothing fits zero"
                                          % (income,)))
    return income


def _verdict(fit_bp, raw_leftover):
    """Which half of the test fired, in `FIT_VERDICTS` words.

    The ratio half is `fit_bp <= policy.DSR_CAP_BP` and the leftover half is the
    raw difference against `policy.AFFORD_FLOOR_CENTS`; a household under water
    — the raw difference negative — is named as such, the negative kept visible
    in the verdict rather than floored away by the record.
    """
    under_water = raw_leftover < 0
    over_cap = fit_bp > policy.DSR_CAP_BP
    under_floor = raw_leftover < policy.AFFORD_FLOOR_CENTS
    if under_water:
        return "under-water"
    if over_cap and under_floor:
        return "over-both"
    if over_cap:
        return "over-the-cap"
    if under_floor:
        return "under-the-floor"
    return "clear"


def affordability(cases, id):
    """The two halves of the fit, decided, as a `FIT_KEYS` record.

    The payment is the level payment of the **requested** amount at the
    **proposed** rate — `policy.PROPOSED_RATE_BP[purpose]` — over the requested
    term: the fit of what was asked for, not of what the bank will sell. The
    obligations are turned into monthly cash at the frequency each was stated
    in, the service is payment plus obligations, `fit_bp` is the service over
    the verified income in basis points (truncating), the leftover is the
    verified income minus the service (floored at zero in the record, read raw
    by the half-test), `fit_bp` may not clear `policy.DSR_CAP_BP` and the raw
    leftover may not fall below `policy.AFFORD_FLOOR_CENTS` — both halves
    required, and the verdict names which fired.

    An unknown application id is the estate's own refusal. A purpose the policy
    carries no proposed rate for, an obligation at a frequency outside
    `FREQUENCIES`, or a verified income that is not a positive count of cents is
    refused by name.
    """
    application = cases.application(id)
    obligations = cases.obligations(id)
    monthly = 0
    for row in obligations:
        monthly = monthly + calendar_monthly(row["amount_cents"],
                                             row["frequency"])
    verified = _verified_income(application["verified_income_cents"])
    payment_cents = payment(cases, application["requested_cents"],
                            _proposed_rate(application["purpose"]),
                            application["term_months"])
    service = payment_cents + monthly
    fit_bp = _BP * service // verified
    raw_leftover = verified - service
    leftover = raw_leftover if raw_leftover > 0 else 0
    verdict = _verdict(fit_bp, raw_leftover)
    return {"id": id,
            "verified_income_cents": verified,
            "declared_income_cents": application["declared_income_cents"],
            "obligations_monthly_cents": monthly,
            "payment_cents": payment_cents,
            "service_cents": service,
            "fit_bp": fit_bp,
            "leftover_cents": leftover,
            "verdict": verdict,
            "fits": verdict == "clear"}


def _fit_table(cases):
    """The fit of every application, one row a committee member reads."""
    rows = []
    verdicts = {}
    for name in cases.names():
        record = affordability(cases, name)
        print("%s  fit_bp %5d  verified %7d  declared %7d  payment %7d  "
              "service %9d  leftover %9d  %s"
              % (record["id"], record["fit_bp"],
                 record["verified_income_cents"],
                 record["declared_income_cents"], record["payment_cents"],
                 record["service_cents"], record["leftover_cents"],
                 record["verdict"]))
        verdicts[record["verdict"]] = verdicts.get(record["verdict"], 0) + 1
        rows.append(record)
    return rows, verdicts


def _measure():
    """The fit table over the ten applications, printed, with the verdict counted."""
    case_book = cases.build(7)
    rows, verdicts = _fit_table(case_book)
    print("verdicts:", sorted(verdicts.items()),
          "fits:", sum(1 for record in rows if record["fits"]))
    print("policy: DSR_CAP_BP", policy.DSR_CAP_BP, "AFFORD_FLOOR_CENTS",
          policy.AFFORD_FLOOR_CENTS)


if __name__ == "__main__":
    import cases
    _measure()
