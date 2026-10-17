"""Credit Lifecycle From Scratch — stage 1: The schedule, the day count and the rate that discounts it.

Every later stage of this course discounts something — a recovery, an expected loss, a
provision — so this stage has to answer the two questions all of them stand on: what
does the contract say is owed, and at what rate does that stream of money discount back
to what the bank carried?

A loan arrives as data: an amount in cents, a rate in basis points, a term in months, a
first due date and a day-count basis. The schedule turns that into `term_months`
instalments on the month ends the world's own calendar produces, each one the smallest
level payment in cents whose amortisation clears the balance, with the last instalment
carrying the remainder so that the principal is repaid to the cent. There is no closed
form here on purpose: the balance is truncated at every step and the interest is
`balance * period_rate // 10000`, which is the arithmetic a reviewer reproduces by
hand, and the note a supervisor asks for is the walk itself.

The rate is then *searched* rather than solved. The effective interest rate is the
smallest whole basis point whose present value of those same instalments does not
exceed the net carrying amount, found by bisection over `0..MAX_EIR_BP`, and the
residue it leaves is reported instead of hidden: a whole number of basis points cannot
usually price a stream to the cent, and the gap between what the flows are worth and
what the bank carried is the honest answer. `present_value` steps its factor one flow
at a time — `factor = factor * 10000 // (10000 + period_rate_bp)` — so no power is ever
computed and no integer ever leaves the scale of the flow it is applied to.

    FLOW_KEYS                     the two fields of one flow, in order
    SCHEDULE_KEYS                 the seven fields of a schedule, in order
    EIR_KEYS                      the seven fields of an effective rate, in order
    BASES                         the two day counts the world counts days in
    MAX_EIR_BP                    the wall the rate search never crosses
    EIR_TOLERANCE_BP              the width of the rate the search resolves to
    ScheduleError                 the refusal this stage raises
    schedule(book, loan)          -> SCHEDULE_KEYS: the contract's own instalments
    level_payment(principal, rate, term, basis)
                                  -> the smallest level payment that clears the loan
    present_value(flows, rate_bp, basis)
                                  -> the discounted worth of a stream of flows
    effective_rate(book, loan)    -> EIR_KEYS: the smallest rate that pays for them

DESIGN DECISION — why is the level payment searched for rather than computed?
Because the contract's amortisation is not the annuity formula's: the balance is
truncated to the cent at every step, so the instalment that actually clears the loan is
the smallest integer one, and the only honest way to name it is to walk the balance for
each candidate. `level_payment` therefore bisects the cents and asks, for each
candidate, whether the walk ends at or below zero — which is a fact a reader can
reproduce with a pencil, and which no closed form can promise once the divisions are
truncated. A formula would answer about one cent less on some loans and the contract
would disagree with the schedule the bank booked.

DESIGN DECISION — why does the last instalment carry the remainder?
Because a level payment is a whole number of cents and the loan is not: the amortisation
of a truncated walk lands wherever it lands, so the final instalment is the balance plus
its own period's interest — exactly what it takes to bring the balance to zero — rather
than one more copy of the level payment. That is what "the principal is repaid exactly"
means in whole cents: the sum of the *principal* every instalment carries is the
principal, no cent of it unpaid and no cent of it paid twice, and the sum of the
instalments is the principal plus the interest the loan was written at. Leaving the
final instalment equal to the level one either leaves the loan short by the truncation
or takes a cent more than the contract's own walk did.

DESIGN DECISION — why is the day count the world's and not this stage's?
Because the two bases are two different contracts: a period is a 30-day month against
either a 360-day year or a 365-day one, so `thirty-360` charges `rate * 30 // 360` per
period and `actual-365` charges `rate * 30 // 365`, and the two must never answer the
same number. `rules.period_rate` owns that division for the whole course, and this
stage only ever hands it a rate and a basis. A local re-implementation — the annual
rate charged monthly, or the day count rounded the stage's own way — would agree with
the book on a lucky loan and disagree on a real one, which is exactly the class of bug
this course exists to make visible.

DESIGN DECISION — why is the present value stepped instead of powered?
Because `(10000 + rate)` to the power of thirty periods is a number with a hundred and
fifty digits and a float waiting to be introduced to keep it small. Stepping the factor
one flow at a time — divide by the period's own rate, truncate, multiply by the flow,
truncate — keeps every integer inside the scale of the amount being discounted, keeps
the arithmetic reproducible by hand, and makes the first flow's discount the same
one-period step as every later flow's. It is also the shape stages 4, 6 and 8 will
borrow when they discount recoveries and provisions.

DESIGN DECISION — why is the effective rate bisected, and why is the residue reported?
Because the answer the contract asks for is "the smallest whole basis point that does
not pay more than the carrying amount", which is a property of the arithmetic and not a
formula: the search asks the question of a rate, keeps the bracket, and narrows until
it is one basis point wide. A truncated rate leaves a residue — the carrying amount
minus the present value the rate manages — and that residue is data about the loan, not
an error: this stage reports it and refuses only at the wall, where even `MAX_EIR_BP`
cannot pay for the flows. Storing a rate whose residue is hidden is how a reporting
stack ends up unable to explain a number a year later.
"""

import dates
import rules
from book import BookError

FLOW_KEYS = ("date", "amount_cents")

SCHEDULE_KEYS = ("loan", "flows", "principal_cents", "rate_bp", "term_months",
                 "first_due", "level_payment_cents")

EIR_KEYS = ("loan", "eir_bp", "pv_cents", "carrying_cents", "residual_cents",
            "periods", "basis")

BASES = ("actual-365", "thirty-360")

MAX_EIR_BP = 10000

EIR_TOLERANCE_BP = 1

_FEE_KIND = "fee"

_LOAN_ID_KEYS = ("loan", "id")


class ScheduleError(ValueError):
    """The refusal this stage raises: something that cannot be a schedule.

    It names the offender — the loan the book does not hold, the basis outside
    `BASES`, the term below one month, the rate outside `0..MAX_EIR_BP`, the flow
    that is not a `FLOW_KEYS` record — because a schedule the contract cannot
    produce must say what it was asked for rather than answer a number nobody can
    defend.
    """


def _checked_basis(basis):
    """The day count, or a refusal naming the one that arrived."""
    if basis not in BASES:
        raise ScheduleError("the basis %r is not one of %r" % (basis, BASES))
    return basis


def _checked_rate(rate_bp):
    """The rate as a whole count of basis points inside `0..MAX_EIR_BP`."""
    if isinstance(rate_bp, bool) or not isinstance(rate_bp, int):
        raise ScheduleError("the rate %r is not a whole count of basis points"
                            % (rate_bp,))
    if rate_bp < 0 or rate_bp > MAX_EIR_BP:
        raise ScheduleError("the rate %d is outside 0..%d basis points"
                            % (rate_bp, MAX_EIR_BP))
    return rate_bp


def _checked_term(term_months):
    """The term as a whole count of months, at least one."""
    if isinstance(term_months, bool) or not isinstance(term_months, int):
        raise ScheduleError("the term %r is not a whole count of months"
                            % (term_months,))
    if term_months < 1:
        raise ScheduleError("the term %d is below one month" % (term_months,))
    return term_months


def _checked_cents(amount_cents, what):
    """An amount as a whole count of cents that a debt can be owed in."""
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
        raise ScheduleError("%s %r is not a whole count of cents"
                            % (what, amount_cents))
    if amount_cents < 0:
        raise ScheduleError("%s %d is negative, and a schedule pays a debt off"
                            % (what, amount_cents))
    return amount_cents


def _checked_flows(flows):
    """The flows as a tuple of `FLOW_KEYS` records, or a refusal naming one.

    A flow is a record of a date and an amount; a stream that is one flow rather
    than a sequence of them, a row that is not a record, a missing field and an
    amount that is not a whole count of cents are all shapes the contract does
    not have, and each one is refused by name rather than discounted.
    """
    if isinstance(flows, (str, bytes)) or isinstance(flows, dict) \
            or not hasattr(flows, "__iter__"):
        raise ScheduleError("the flows %r is not a sequence of flows" % (flows,))
    rows = tuple(flows)
    for flow in rows:
        if not isinstance(flow, dict):
            raise ScheduleError("the flow %r is not a %r record" % (flow, FLOW_KEYS))
        for key in FLOW_KEYS:
            if key not in flow:
                raise ScheduleError("the flow %r carries no %r" % (flow, key))
        if not isinstance(flow["date"], str):
            raise ScheduleError("the flow %r's date %r is not a date"
                                % (flow, flow["date"]))
        if isinstance(flow["amount_cents"], bool) \
                or not isinstance(flow["amount_cents"], int):
            raise ScheduleError("the flow %r's amount %r is not a whole count of cents"
                                % (flow, flow["amount_cents"]))
    return rows


def _period_rate_bp(rate_bp, basis):
    """The world's own rate for one period: the day count is never done here.

    `rules.period_rate` is where a month's share of the year lives, so the stage
    hands it a rate and a basis and takes a number back. `thirty-360` and
    `actual-365` are then the world's two answers rather than two local ones, and
    a stage that charged the annual rate monthly — or that re-implemented the day
    count — would answer a different number for the same contract.
    """
    return rules.period_rate(_checked_rate(rate_bp), _checked_basis(basis))


def _amortise(principal_cents, period_bp, payment_cents, term_months):
    """The balance the walk leaves, at most `term_months` periods on.

    Interest is charged on the balance the period opens with, truncated to the
    cent, and the payment is taken off after it: the contract's own order, and
    the one a reviewer reproduces by hand. A balance already at or below zero
    ends the walk early — a loan that is repaid owes nothing more — so the
    answer is at or below zero exactly when the payment clears the loan within
    its term.
    """
    balance = principal_cents
    for _ in range(term_months):
        if balance <= 0:
            return balance
        balance = balance + balance * period_bp // 10000 - payment_cents
    return balance


def _loan_id(loan):
    """The identity a loan record carries, or the id that arrived in its place.

    `LOAN_KEYS` names it `loan`; a record carrying only `id` is read too, so the
    bank's own probes can hand their shape in. The id is read and never guessed,
    because it is the name a refusal has to carry.
    """
    if not isinstance(loan, dict):
        return loan
    for key in _LOAN_ID_KEYS:
        if key in loan:
            return loan[key]
    raise ScheduleError("the loan record %r carries no %r" % (loan, _LOAN_ID_KEYS[0]))


def _resolve(ledger, loan):
    """The book's own record of `loan`, or a refusal naming what was asked for."""
    identify = _loan_id(loan)
    try:
        return ledger.loan(identify)
    except BookError as refused:
        raise ScheduleError("the book does not hold loan %r (%s)" % (identify, refused))


def _loan_basis(record):
    """The day count the loan is written on, refused by name when it has none."""
    try:
        basis = record["basis"]
    except KeyError:
        raise ScheduleError("loan %r carries no day-count basis" % (_loan_id(record),))
    return _checked_basis(basis)


def _loan_parts(record, basis):
    """The four terms of the contract, checked, and the level payment they imply."""
    principal = _checked_cents(record["principal_cents"], "the principal")
    rate = _checked_rate(record["rate_bp"])
    term = _checked_term(record["term_months"])
    level = level_payment(principal, rate, term, basis)
    return principal, rate, term, level


def _flows_of(record, basis):
    """The contract's own flows, and the level payment they were written at.

    One flow per month of the term, the first on `first_due` and each later one a
    month on through `dates.add_months`, so the clamping rule and the drifting day
    are the world's. Every instalment is the level payment except the last, which
    is the balance plus its own period's interest: the amount that brings the
    balance to exactly zero and so repays the principal to the cent.
    """
    principal, rate, term, level = _loan_parts(record, basis)
    period_bp = rules.period_rate(rate, basis)
    balance = principal
    flows = []
    for step in range(term):
        interest = balance * period_bp // 10000
        amount = level if step < term - 1 else balance + interest
        flows.append({"date": dates.add_months(record["first_due"], step),
                      "amount_cents": amount})
        balance = balance + interest - amount
    return tuple(flows), level


def _fees(ledger, record):
    """The loan's own fees: what the net carrying amount is measured against."""
    total = 0
    for payment in ledger.payments(record):
        if payment["kind"] == _FEE_KIND:
            total = total + payment["amount_cents"]
    return total


def level_payment(principal_cents, rate_bp, term_months, basis):
    """The smallest level payment in cents whose amortisation clears the loan.

    The balance is carried at `rules.period_rate(rate_bp, basis)` per period —
    interest on the opening balance, truncated to the cent, then the payment — and
    the answer is the smallest integer payment whose walk ends at or below zero
    within `term_months` periods. It is bisected, not computed: the truncation at
    every step means no closed form knows the answer to the cent.

    A basis outside `BASES`, a term below one month or a rate outside
    `0..MAX_EIR_BP` is refused by name.
    """
    principal = _checked_cents(principal_cents, "the principal")
    period_bp = _period_rate_bp(rate_bp, basis)
    term = _checked_term(term_months)
    low = 0
    high = 2 * principal
    while low < high:
        middle = (low + high) // 2
        if _amortise(principal, period_bp, middle, term) <= 0:
            high = middle
        else:
            low = middle + 1
    return low


def present_value(flows, rate_bp, basis):
    """What a stream of flows is worth today, at a rate and a day count.

    Each flow is discounted by one period more than the flow before it, the factor
    being divided by the period's own rate and truncated at every step:
    `factor = factor * 10000 // (10000 + period_rate_bp)`, then
    `flow * factor // 10000`. No power is computed, and no integer is ever carried
    at a finer scale than the amount it discounts.

    A rate outside `0..MAX_EIR_BP`, a basis outside `BASES`, or a flow that is not
    a `FLOW_KEYS` record is refused by name.
    """
    period_bp = _period_rate_bp(rate_bp, basis)
    rows = _checked_flows(flows)
    factor = rules.DISCOUNT_SCALE
    total = 0
    for flow in rows:
        factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
        total = total + flow["amount_cents"] * factor // rules.DISCOUNT_SCALE
    return total


def schedule(book, loan):
    """The contract's own instalments for a loan the book holds.

    One flow per month of the term, dated from `first_due` through
    `dates.add_months`, each the loan's `level_payment_cents` except the last,
    which carries the remainder and brings the balance to exactly zero. The record
    echoes the loan's own four terms and answers the level payment it was written
    at, so a later stage can recompute the loan from the schedule alone.

    A loan the book does not hold, or one whose own terms are outside the
    contract, is refused by name.
    """
    record = _resolve(book, loan)
    basis = _loan_basis(record)
    flows, level = _flows_of(record, basis)
    return {"loan": _loan_id(record),
            "flows": flows,
            "principal_cents": record["principal_cents"],
            "rate_bp": record["rate_bp"],
            "term_months": record["term_months"],
            "first_due": record["first_due"],
            "level_payment_cents": level}


def effective_rate(book, loan):
    """The smallest whole basis point whose present value pays for the loan.

    The contractual flows are discounted at each candidate rate and the search
    keeps the smallest rate in `0..MAX_EIR_BP` whose present value is not greater
    than the net carrying amount — the principal, less the loan's own fees when the
    book records any. It is bisected rather than solved, and the record reports the
    present value the rate achieves and the residue it leaves (`carrying − pv`),
    because a whole number of basis points cannot usually price a stream to the
    cent and the residue is what the rate could not reach.

    A rate at the wall — even `MAX_EIR_BP` paying less than the carrying amount —
    is refused rather than returned, and so is a loan the book does not hold.
    """
    record = _resolve(book, loan)
    basis = _loan_basis(record)
    flows, _level = _flows_of(record, basis)
    carrying = _checked_cents(record["principal_cents"], "the principal") \
        - _fees(book, record)
    at_wall = present_value(flows, MAX_EIR_BP, basis)
    if at_wall > carrying:
        raise ScheduleError(
            "no rate in 0..%d discounts loan %r's flows to its carrying amount of "
            "%d cents; the wall itself pays %d"
            % (MAX_EIR_BP, _loan_id(record), carrying, at_wall))
    low = 0
    high = MAX_EIR_BP
    while high - low >= EIR_TOLERANCE_BP:
        middle = (low + high) // 2
        if present_value(flows, middle, basis) <= carrying:
            high = middle
        else:
            low = middle + 1
    pv = present_value(flows, low, basis)
    return {"loan": _loan_id(record),
            "eir_bp": low,
            "pv_cents": pv,
            "carrying_cents": carrying,
            "residual_cents": carrying - pv,
            "periods": len(flows),
            "basis": basis}
