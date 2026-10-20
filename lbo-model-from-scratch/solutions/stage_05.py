"""LBO Model From Scratch — solutions, stage 5: The covenants the model cannot quietly violate.

A covenant is a number with a date on it, and that is the whole of what makes
it enforceable: net debt below the year's own limit, measured on the state
the books carry at that year end, by integer arithmetic nobody can round a
favour out of. This stage measures the maintenance test — net debt over the
year's recorded EBITDA, in basis points, against the treaty's limit for that
year end — and the incurrence test, the maximum new draw the one-touch
ceiling still allows, against the state the caller hands it.

The stage names what breaks **as data**, never as an exception: a breach is
an answer — which test, which year, by how many basis points over — in the
same record that a passing state answers. A model that throws on a breach is
a model that cannot tell its user where it stands, and the estate recorded
this deal's breach in year three with the sponsor's cure cheque wired for
exactly that. The cure arithmetic rides with the record: the least cheque in
cents that flips the year's own test back under the limit, computed by
ceiling arithmetic on the same integers, so the sponsor knows the number
before the room knows the breach.

The refusal family exists for impossible asks, and only for them: a state
that does not shape like a balance sheet, a year whose limit the treaty does
not write, a division the EBITDA cannot carry. A breach of a real test is an
answer a covenant model delivers, not a refusal.

    TEST_KEYS           the eleven fields of the year's tests, in order
    STATE_KEYS          the two fields of the state they are measured on
    CURE_KEYS           the two fields of the cure arithmetic, in order
    INCURRENCE_KEYS     the two fields of the incurrence arithmetic, in order
    MAX_TERM_YEARS      the walk's horizon
    CovenantError       the refusal this stage raises
    tests(debt_state, estate, year) -> TEST_KEYS: the tests as data
    cure(estate, state, year) -> CURE_KEYS: the least cheque that flips the
                        year's own test, in cents, and the headroom it buys

    A state that does not shape like the estate's own states, a year the
    treaty does not write a limit for, and a state whose cash is negative
    are refused by name. A breach is never a refusal.
"""

TEST_KEYS = ("year", "year_end", "net_debt_cents", "ebitda_cents", "net_leverage_bp",
             "limit_bp", "headroom_bp", "breach", "by_bp", "cure_cents",
             "incurrence_cents")

STATE_KEYS = ("balances", "cash_cents")

CURE_KEYS = ("year", "year_end", "net_leverage_bp", "limit_bp", "cure_cents",
             "post_cure_bp", "headroom_bp")

INCURRENCE_KEYS = ("year", "year_end", "net_debt_cents", "incurrence_bp",
                   "incurrence_cents")

MAX_TERM_YEARS = 5

CURE_KIND = "cure"


class CovenantError(ValueError):
    """The refusal this stage raises: a test that cannot be measured — and
    never a breach, which is data.

    It names the offender: the state that does not shape like the estate's
    own, the year whose limit the treaty does not write, the cash that is
    negative, the test where a whole number of basis points cannot carry the
    state. Anything else — any real covenant position, passing or not — is
    an answer.
    """


def _state(estate, state, year):
    """The caller's state, shaped and tied to terms, or a refusal naming it."""
    if not isinstance(state, dict):
        raise CovenantError("the covenants: the state is a %s, not a balance sheet"
                            % (type(state).__name__,))
    balances = state.get("balances")
    cash = state.get("cash_cents")
    if not isinstance(balances, dict):
        raise CovenantError("the covenants: the state's balances are a %s, not a record"
                            % (type(balances).__name__,))
    for terms in estate.tranches():
        if terms["name"] not in balances:
            raise CovenantError("the covenants: the state holds no balance for %s"
                                % (terms["name"],))
        if isinstance(balances[terms["name"]], bool) \
                or not isinstance(balances[terms["name"]], int):
            raise CovenantError("the covenants: the state's %s balance is not a whole "
                                "number" % (terms["name"],))
    if isinstance(cash, bool) or not isinstance(cash, int):
        raise CovenantError("the covenants: the state's cash_cents is not an integer "
                            "count of cents")
    if cash < 0:
        raise CovenantError("the covenants: the state's cash of %d is negative" % (cash,))
    return balances, cash


def _walk_year(year):
    if isinstance(year, bool) or not isinstance(year, int):
        raise CovenantError("the covenants: %s is not a walk year" % (year,))
    if year < 1 or year > MAX_TERM_YEARS:
        raise CovenantError("the covenants: %d is not a year the walk walks" % (year,))
    return year


def _net(balances, cash):
    return sum(balances.values()) - cash


def tests(debt_state, estate, year):
    """The year's maintenance test and the year's incurrence ceiling, as data.

    Net debt is the state's balances less its cash; the year's EBITDA is the
    estate's recorded one; the ratio is
    `net_debt * 10000 // ebitda` basis points; and the verdict answers the
    treaty's limit for this year end, the headroom below it, and whether the
    state breaches — as a boolean in the record, never an exception. The
    record also answers the two numbers the room asks for after a breach is
    read out: the least cure cheque that flips this state's test (zero when
    the state passes) and the largest new draw the incurrence ceiling
    (`estate.incurrence_bp()`) still allows, floored at zero when the state
    is already past it.

    A state that does not shape like a balance sheet, a year the treaty
    writes no limit for, and a negative cash are refused by name. A breach
    answers as data.
    """
    year = _walk_year(year)
    balances, cash = _state(estate, debt_state, year)
    actual = estate.actuals(year)
    ebitda = actual["ebitda_cents"]
    if ebitda <= 0:
        raise CovenantError("the covenants: year %d's recorded EBITDA of %d carries no "
                            "ratio" % (year, ebitda))
    net = _net(balances, cash)
    ratio = net * 10000 // ebitda
    limit = estate.net_leverage_limit(actual["year_end"])
    breach = ratio > limit
    net_max = (ebitda * (limit + 1) - 1) // 10000
    cure_cents = 0 if net <= net_max else net - net_max
    incurrence = estate.incurrence_bp()
    incur_max = (ebitda * (incurrence + 1) - 1) // 10000
    incurrence_cents = max(0, incur_max - net)
    return dict(zip(TEST_KEYS, (year, actual["year_end"], net, ebitda, ratio, limit,
                                max(0, limit - ratio), breach,
                                ratio - limit if breach else 0,
                                cure_cents, incurrence_cents)))


def cure(estate, state, year):
    """The least cheque that flips the state's own test, on the treaty's
    cure rights.

    The answer is the cure year's arithmetic against the state as handed:
    the least whole number of cents such that the state's net leverage,
    measured after the cheque lands, sits at or under the year end's limit.
    The least *allowed* net is the largest integer whose ratio stays under
    the ceiling — `(ebitda * (limit + 1) - 1) // 10000` — and the cheque is
    the difference. A state that already passes answers zero and the
    headroom it stands under.

    The state's shape and the year's walk are refused by name; a breach is
    not a refusal but exactly what this surface prices.
    """
    year = _walk_year(year)
    balances, cash = _state(estate, state, year)
    net = _net(balances, cash)
    actual = estate.actuals(year)
    ebitda = actual["ebitda_cents"]
    ratio = net * 10000 // ebitda
    limit = estate.net_leverage_limit(actual["year_end"])
    net_max = (ebitda * (limit + 1) - 1) // 10000
    cheque = 0 if net <= net_max else net - net_max
    return dict(zip(CURE_KEYS, (year, actual["year_end"], ratio, limit, cheque,
                                (net - cheque) * 10000 // ebitda,
                                max(0, limit - (net - cheque) * 10000 // ebitda))))
