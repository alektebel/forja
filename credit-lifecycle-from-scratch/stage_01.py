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

TODO: implement `ScheduleError`, `schedule`, `level_payment`, `present_value` and
`effective_rate` in this file: the contract's own instalments off the world's calendar,
the smallest level payment whose truncated amortisation clears the loan, the stepped
discount that never computes a power, and the bisection over whole basis points that
reports the residue it leaves.

    A loan is refused by name when the book does not hold it, when its basis is not one
    of `BASES`, when its term is below one month, when its rate is outside
    `0..MAX_EIR_BP`, and when a flow is not a `FLOW_KEYS` record.
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
    raise NotImplementedError("stage 1: implement level_payment()")


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
    raise NotImplementedError("stage 1: implement present_value()")


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
    raise NotImplementedError("stage 1: implement schedule()")


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
    raise NotImplementedError("stage 1: implement effective_rate()")
