"""Credit Origination From Scratch — stage 7: The covenants written before the drawdown.

A credit decision is not only a number. Before the drawdown the bank writes
down what the borrower promises: leverage the projections must not climb past,
service the cash generation must cover, cash the bank must never fall under —
the policy names them per purpose, in the order the committee wrote them, and
this stage measures each promise on the borrower's own projections, year by
year, and names the year the promise came closest to breach. The measure is
the promise's own arithmetic — net debt over EBITDA the tall way, EBITDA over
the year's debt service, cash against its floor in cents — and the record
answers one row per covenant for an sme or a corporate borrower, and nothing
at all for the purposes that promise none of this.

The service half is bound to the loan the bank is actually selling: the debt
service a covenant is measured against is the booked terms' own service — the
level payment of the approved amount at the priced rate over the approved
months, times twelve — which is why this stage reads the priced rate of stage
5 and the approved structure of stage 6, and nothing later: the decision, the
letter and the booking all read what this stage wrote. The payment itself is
the searched, not solved, walk stage 1 owns — the balance truncated to the
cent at every step, the instalment that clears the loan the smallest integer
one — re-walked here on the terms this stage was handed, because the ladder
imports two stages and not three.

    COVENANT_KEYS                  the seven fields of one covenant record, in order
    COVENANT_VERDICTS              the three verdicts a promise can carry
    STAGE_ERROR                    the prefix every refusal of this stage opens with
    CovenantError                  the refusal this stage raises
    covenants(cases, identity)     -> tuple of COVENANT_KEYS: the promises, measured
    headroom(covenant, value)      -> int: the distance a measure sits from its floor

DESIGN DECISION — why does the record measure the worst year rather than every
year? Because a covenant is a promise and a year: the letter names one year the
borrower must be measured on, so the record has to pick one and defend the pick.
The worst year is the one whose measure sits closest to breach — the tallest
measure for a `max-` promise, the shortest for a `min-` one — and a tie among
equal measures names the first of the equal years, because the projections are
read in order and a tie broken the same way twice is a run that reruns. A
record that measures the best year, or the first, or averages them, answers a
promise nobody's letter ever carried.

DESIGN DECISION — why is the headroom taken the opposite way on a `max-` covenant?
Because a breach is the thing the record is there to name, in both directions,
on one scale. A `min-` promise measures directly (EBITDA over service, cash
over its floor) and its headroom is the measure over the floor — kept at
10000 and above. A `max-` promise measures the tall way, so its measure grows
as the covenant weakens and the headroom is the floor over the measure, which
shrink as the promise bends — the same `10000` line, crossed the other way.
Headroom is 10000ths of the covenant the borrower stands away from breach, and
the contract's own truncation is pinned at that scale, not at the borrower's.

DESIGN DECISION — why is the debt service the priced terms' service, and whose
level payment walk re-does it?
Because the covenant binds the loan the bank booked the structure of: the
service a `min-dscr` promise is measured against is the level payment of the
stage 6 approval at the stage 5 price over the stage 6 tenor, twelve times —
not the fit's proposed words, and never the request. Stage 1's `payment` owns
the searched walk, but the ladder imports two earlier stages and not three,
so the walk — opening-balance interest truncated, payment taken after it,
smallest clearing instalment bisected — is carried here in the bank's own
period (thirty days of a 360-day year, truncating). The check recomputes the
service independently, from the bank's own booked facility terms, so a
payment that drifts a cent from the bank's ledger is a wrong stage, not a
wrong test.

DESIGN DECISION — what does a covenant nothing binds answer, and why not refuse?
Because "no promise to measure" is an answer, not an error. A borrower whose
projections carry no year at all — the estate's declined corporate, and any
other — answers `no-year` for every covenant its purpose carries, headroom 0
and year 0, the verdict word carrying the reason. A declined application's
service covenant answers the same: zero approved and zero months are terms
that bind nothing, so service has no debt to sit against — while the
balance-sheet covenants (leverage, cash) still measure the borrower's own
projections, because a declined borrower's balance sheet is still the fact
the bank wrote conditions from.

DESIGN DECISION — why is `kept` the word, and what carries a breach?
Because the contract pins the breach word (`breach`) and leaves the healthy
vocabulary to the stage, the way stage 1 pinned its own five verdicts. This
stage answers `kept` for a covenant at or above its headroom line, `breach`
below it — the word stage 8's conditions cite as `covenant-<name>-year-<worst>`
— and `no-year` for a promise nothing binds. A breach is recorded with its
own year and its own headroom, never refused, never floored: a covenant that
amortises its breach away is the promise the downside case exists to catch.

DESIGN DECISION — why does `covenants` take the estate in and answer for it?
Because a refusal branch is only checkable against an estate the stage was
actually handed: the stage reads the application, the projections, and — for
a covenanted borrower — the approved structure and the priced rate through
the ladder stages, asks no other door, and writes nothing back. A purpose the
policy does not name, an estate's own unknown id (the estate refuses itself)
or a measure whose division the arithmetic cannot take is refused by name,
with the offender in the message.
"""

import cases
import policy
import stage_05
import stage_06

COVENANT_KEYS = ("id", "name", "kind", "floor", "headroom_bp", "verdict", "year")

COVENANT_VERDICTS = ("kept", "breach", "no-year")

STAGE_ERROR = "stage 7: "

_BP = 10000

_DAYS_PER_PERIOD = 30

_DAYS_PER_YEAR = 360

_MONTHS_PER_YEAR = 12

_KINDS = ("max-leverage", "min-dscr", "min-cash")

_KEPT = "kept"

_BREACH = "breach"

_NO_YEAR = "no-year"


class CovenantError(ValueError):
    """The refusal this stage raises: a covenant, a purpose or a measure it cannot name.

    The promises are read out of the policy's own covenant tables and measured
    on the estate's own projections. A purpose outside `PURPOSES` has no table
    to be promised from, a purpose the policy names but the tables never wrote
    has nothing to promise, and a measure whose division the arithmetic cannot
    take — EBITDA of nothing under a `max-` promise, a priced rate outside the
    payment's own wall — is refused with the application or the covenant named,
    the way every refusal in this course says who it is for.
    """


def _count(value, what):
    """A whole count, refused by name when it is not."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CovenantError(STAGE_ERROR + ("%s %r is a %s, not a whole count"
                                           % (what, value, type(value).__name__)))
    return value


def _row(covenant):
    """One of the policy's covenant rows — `(name, kind, floor)` — as it stands."""
    if isinstance(covenant, bool) or not isinstance(covenant, tuple) \
            or len(covenant) != 3:
        raise CovenantError(STAGE_ERROR + ("the covenant %r is a %s, not a row of "
                                           "(name, kind, floor)"
                                           % (covenant, type(covenant).__name__)))
    name, kind, floor = covenant
    if not isinstance(name, str):
        raise CovenantError(STAGE_ERROR + ("the covenant name %r is a %s, not a "
                                           "text" % (name, type(name).__name__)))
    if kind not in _KINDS:
        raise CovenantError(STAGE_ERROR + ("the covenant %r is written of kind %r, "
                                           "and the kinds a promise is measured in "
                                           "are %r" % (name, kind, _KINDS)))
    _count(floor, "the floor of %r" % (name,))
    if floor <= 0:
        raise CovenantError(STAGE_ERROR + ("the floor of %r is %d, and a promise is "
                                           "floored at something positive"
                                           % (name, floor)))
    return name, kind, floor


def headroom(covenant, value):
    """How far one measured value sits from one covenant's floor, in 10000ths.

    `covenant` is one of the policy's own rows — `(name, kind, floor)` — and
    `value` the covenant's own measure for one year: the ratio in basis points
    for a `max-leverage` and a `min-dscr`, the cash itself in cents for a
    `min-cash`. A `max-` promise is measured the tall way, so its headroom is
    the floor taken over the measure — `10000 * floor // value`, truncating —
    and a `min-` one takes the measure over its floor. Kept answers `10000`
    and above, breach below, whichever way the division runs, and a breach is
    never a refusal: being under the floor is what the record is there to
    name. A covenant that is not one of the policy's rows, a measure that is
    not a whole count, a `max-` measure of nothing, or a floor the division
    cannot be taken against is refused by name.
    """
    name, kind, floor = _row(covenant)
    measure = _count(value, "the measure of %r" % (name,))
    if kind.startswith("max-"):
        if measure <= 0:
            raise CovenantError(STAGE_ERROR + ("the measure of %r is %d, and a "
                                               "max- covenant cannot be divided "
                                               "into nothing" % (name, measure)))
        return _BP * floor // measure
    if measure < 0:
        raise CovenantError(STAGE_ERROR + ("the measure of %r is %d, and nothing a "
                                           "borrower reports is negative"
                                           % (name, measure)))
    return _BP * measure // floor


def _period_bp(rate_bp):
    """The rate per monthly period: a month is thirty days of a 360-day year."""
    return rate_bp * _DAYS_PER_PERIOD // _DAYS_PER_YEAR


def _walk(balance, period, payment, remaining):
    """The balance after `remaining` truncated periods of `payment`."""
    for _ in range(remaining):
        if balance <= 0:
            return balance
        balance = balance + balance * period // _BP - payment
    return balance


def _level_payment(principal_cents, rate_bp, term_months, identity):
    """The smallest whole-cent payment that clears one booked loan.

    Stage 1's own arithmetic, re-walked here on the terms this stage was
    handed: the interest is charged on the balance the period opens with,
    truncated to the cent, the payment taken off after it, and the answer is
    the smallest integer payment whose walk ends at or below zero within the
    term — bisected, never closed-formed, because the truncation at every
    step makes the clearing instalment a search's answer. A rate outside
    `0.._BP`, a term below one month, a principal below one cent, or anything
    but whole counts in those places is refused by name, with the application
    the terms belong to.
    """
    rate = _count(rate_bp, "the priced rate of %r" % (identity,))
    term = _count(term_months, "the approved months of %r" % (identity,))
    principal = _count(principal_cents, "the approved amount of %r" % (identity,))
    if rate < 0 or rate > _BP:
        raise CovenantError(STAGE_ERROR + ("the priced rate %d of %r is outside "
                                           "0..%d basis points, and no payment "
                                           "covers it" % (rate, identity, _BP)))
    if term < 1:
        raise CovenantError(STAGE_ERROR + ("the approved months of %r is %d, and "
                                           "no loan pays before it starts"
                                           % (identity, term)))
    if principal < 1:
        raise CovenantError(STAGE_ERROR + ("the approved amount of %r is %d, and "
                                           "no covenanted loan is smaller than a "
                                           "cent" % (identity, principal)))
    period = _period_bp(rate)
    low, high = 0, 2 * principal
    while low < high:
        middle = (low + high) // 2
        if _walk(principal, period, middle, term) <= 0:
            high = middle
        else:
            low = middle + 1
    return low


def _measure_year(kind, row, terms, identity):
    """One projection year, as one kind of covenant measures it."""
    if kind == "max-leverage":
        ebitda = _count(row["ebitda_cents"], "the year %r EBITDA of %r"
                        % (row["year"], identity))
        if ebitda <= 0:
            raise CovenantError(STAGE_ERROR + ("the year %r of %r carries EBITDA "
                                               "%d, and a leverage covenant cannot "
                                               "be taken against nothing"
                                               % (row["year"], identity, ebitda)))
        net_debt = _count(row["net_debt_cents"], "the year %r net debt of %r"
                          % (row["year"], identity))
        return _BP * net_debt // ebitda
    if kind == "min-dscr":
        ebitda = _count(row["ebitda_cents"], "the year %r EBITDA of %r"
                        % (row["year"], identity))
        if terms <= 0:
            raise CovenantError(STAGE_ERROR + ("the debt service of %r is %d, and "
                                               "a service covenant cannot be "
                                               "measured against nothing"
                                               % (identity, terms)))
        return _BP * ebitda // terms
    cash = _count(row["cash_cents"], "the year %r cash of %r"
                  % (row["year"], identity))
    if cash < 0:
        raise CovenantError(STAGE_ERROR + ("the year %r of %r carries cash %d, and "
                                           "a cash covenant cannot measure a purse "
                                           "the bank has already fallen out of"
                                           % (row["year"], identity, cash)))
    return cash


def _worst_year(kind, years, terms, identity):
    """The year the measure sat closest to breach, with the measure itself.

    A `max-` promise is closest to breach where its measure is the tallest,
    a `min-` one where it is the shortest. The projections are read in order,
    and a tie among equal measures names the first of the equal years — a tie
    broken the same way twice is a run that reruns.
    """
    tallest = kind.startswith("max-")
    worst = None
    for row in years:
        measure = _measure_year(kind, row, terms, identity)
        if worst is None:
            worst = (measure, row["year"])
        elif tallest and measure > worst[0]:
            worst = (measure, row["year"])
        elif not tallest and measure < worst[0]:
            worst = (measure, row["year"])
    return worst


def _no_year(identity, covenant):
    """A promise nothing binds: recorded and worded, never raised."""
    name, kind, floor = covenant
    return {"id": identity, "name": name, "kind": kind, "floor": floor,
            "headroom_bp": 0, "verdict": _NO_YEAR, "year": 0}


def _measured(identity, covenant, years, terms):
    """One promise over the projections, at its worst year."""
    name, kind, floor = covenant
    if kind == "min-dscr" and terms is None:
        return _no_year(identity, covenant)
    measure, year = _worst_year(kind, years, terms, identity)
    head = headroom(covenant, measure)
    verdict = _BREACH if head < _BP else _KEPT
    return {"id": identity, "name": name, "kind": kind, "floor": floor,
            "headroom_bp": head, "verdict": verdict, "year": year}


def covenants(cases, identity):
    """The promises one application's purpose carries, measured on its projections.

    One `COVENANT_KEYS` record per covenant the purpose carries, in the
    policy's own order, and an empty tuple for a purpose that carries none.
    The debt service a `min-dscr` promise is measured against is the booked
    terms' own service — the level payment of the stage 6 approval at the
    stage 5 price over the stage 6 tenor, times twelve — so the priced rate
    and the approved structure are read through the ladder stages, and a
    decline, which zeros both, binds no service at all. A borrower with no
    projections answers `no-year` for every covenant the policy carries for
    its purpose. The estate is read and never written: the application and
    projections doors directly, the structure and price doors through the
    ladder, and nothing beyond them.
    """
    application = cases.application(identity)
    purpose = application["purpose"]
    if purpose not in policy.PURPOSES:
        raise CovenantError(STAGE_ERROR + ("the purpose %r is not one the policy "
                                           "names: %r" % (purpose, policy.PURPOSES)))
    if purpose not in policy.COVENANTS:
        raise CovenantError(STAGE_ERROR + ("the policy carries no covenant table for "
                                           "%r" % (purpose,)))
    rows = policy.COVENANTS[purpose]
    if not rows:
        return ()
    years = cases.projections(identity)
    if not years:
        return tuple(_no_year(identity, row) for row in rows)
    try:
        structure = stage_06.limit(cases, identity)
    except ValueError as refused:
        raise CovenantError(STAGE_ERROR + ("the approved structure of %r was not "
                                           "handed over: %s" % (identity, refused)))
    approved = _count(structure["approved_cents"], "the approved amount of %r"
                      % (identity,))
    approved_months = _count(structure["approved_months"], "the approved months of %r"
                             % (identity,))
    terms = None
    if approved > 0 and approved_months > 0:
        try:
            priced = stage_05.price(identity, cases)
        except ValueError as refused:
            raise CovenantError(STAGE_ERROR + ("the priced rate of %r was not "
                                               "handed over: %s" % (identity, refused)))
        payment = _level_payment(approved, priced["price_bp"], approved_months,
                                 identity)
        terms = payment * _MONTHS_PER_YEAR
    return tuple(_measured(identity, row, years, terms) for row in rows)


def _measure():
    """The covenant table over the estate's covenanted borrowers, printed."""
    book = cases.build(7)
    for name in book.names():
        try:
            records = covenants(book, name)
        except CovenantError as refused:
            print("%s  refused: %s" % (name, refused))
            continue
        for record in records:
            print("%s  %-9s %-12s floor %9d  headroom %8d  %-7s year %r"
                  % (record["id"], record["name"], record["kind"], record["floor"],
                     record["headroom_bp"], record["verdict"], record["year"]))


if __name__ == "__main__":
    _measure()
