"""LBO Model From Scratch — solutions, stage 4: The mandatory prepayment and the cash that sweeps.

Stage 3 produced the table the term sheet mandates; this stage produces the
waterfall that moves cash. It is a state machine: the caller hands over the
balance sheet as it stands — every tranche's balance and the cash the books
carry — and the stage hands back what one walk year does to it. Interest is
first, on the balances the state carries; then the mandatory pieces; then the
revolver, drawn when the year's short needs it and repaid first from every
excess; then the term loan B's sweep, which takes its contract fee of what is
left; then the sponsor's cure cheque, wired in the year the world recorded it
and routed top-down through the prepayables; and the remainder is the year's
distribution, with the balance sheet carrying the floor.

The sweep takes a state, not a year's history. A what-if — a balance sheet
after a harder year, a state the check builds out of its own arithmetic —
flows through the same waterfall as the recorded one, which is the whole
reason the surface is state-shaped: a mechanism that re-derives rather than
re-reads can be asked about balances nobody recorded.

The stage refuses, by name: a year past the exit (the exit year closes in a
sale), a state that does not shape like a balance sheet, a negative cash
balance, and a revolver booked above what its own terms allow — because a
state that cannot exist has no waterfall to answer and no distribution to
name.

    SWEEP_KEYS          the twelve fields of the year's waterfall, in order
    MAX_TERM_YEARS      the walk's horizon
    SweepError          the refusal this stage raises
    sweep(estate, debt_state, year) -> SWEEP_KEYS: one year, on one state

    The record echoes the state it was handed as the year's opening, answers
    the aggregate columns of the waterfall, and carries the state the next
    year's opening must be — the closing balances and the cash the floor held.
"""

import dates

SWEEP_KEYS = ("year", "year_end", "opening", "rows", "interest_cents",
              "mandatory_amort_cents", "draw_cents", "repay_cents", "sweep_cents",
              "cure_cents", "distribution_cents", "state")

ROW_KEYS = ("name", "basis", "rate_bp", "opening_cents", "interest_cents",
            "mandatory_amort_cents", "draw_cents", "repay_cents", "mandatory_close_cents")

MAX_TERM_YEARS = 5


class SweepError(ValueError):
    """The refusal this stage raises: a waterfall that cannot be run.

    It names the offender — the year past the exit, the balance sheet that
    does not shape like one, the cash that is negative, the revolver booked
    above its own terms — because a state the world cannot have held is a
    state no waterfall answers, and pretending otherwise is how a model
    distributes money that was never there.
    """


def _state(estate, state, year):
    """The caller's state, shaped and tied to terms, or a refusal naming it."""
    if not isinstance(state, dict):
        raise SweepError("the sweep: the state is a %s, not a balance sheet"
                         % (type(state).__name__,))
    balances = state.get("balances")
    cash = state.get("cash_cents")
    if not isinstance(balances, dict):
        raise SweepError("the sweep: the state's balances are a %s, not a record"
                         % (type(balances).__name__,))
    if isinstance(cash, bool) or not isinstance(cash, int):
        raise SweepError("the sweep: the state's cash_cents is not an integer count "
                         "of cents" % ())
    if cash < 0:
        raise SweepError("the sweep: the state's cash of %d is negative" % (cash,))
    for terms in estate.tranches():
        if terms["name"] not in balances:
            raise SweepError("the sweep: the state holds no balance for %s" % (terms["name"],))
        if not isinstance(balances[terms["name"]], int) \
                or isinstance(balances[terms["name"]], bool):
            raise SweepError("the sweep: the state's %s balance is not a whole number"
                             % (terms["name"],))
    revolver = [terms for terms in estate.tranches() if terms["name"] == "revolver"][0]
    if balances.get("revolver", 0) > revolver["commitment_cents"]:
        raise SweepError("the sweep: the revolver is booked at %d, %d above what its "
                         "own terms draw"
                         % (balances["revolver"],
                            balances["revolver"] - revolver["commitment_cents"]))
    return balances, cash


def sweep(estate, debt_state, year):
    """One walk year's waterfall, on the state the caller hands over.


    raise NotImplementedError("4: implement sweep()")