"""book.py — the portfolio, the bank's own records and the answer key.

Provided, frozen, and never written by the course. This module is the bank: the
raw facts a reporting stack is handed, and the records the bank itself keeps
about them. Stage *N* recomputes one slice of it, and the book is what the slice
is held against.

It holds four kinds of thing.

* **The estate** — twelve loans across the six segments and all seven grades,
  their contractual terms, their collateral, their undrawn limits, and the
  reporting window of thirty-six month ends (`2031-01-31` … `2033-12-31`).
* **The observed facts** — the payments the borrower made (instalments, prepayments
  and fees), the events the bank recorded (forbearance, distressed restructuring,
  cross-default and bankruptcy, a write-off, a cure), and the recoveries collected
  against defaulted loans (cash, collateral realisation and the negative `costs`
  row that reduces them).
* **The artifacts** — three versioned models, two of them versions of one name, so
  a provision movement can be attributed to the model that caused it.
* **The bank's own records** — `schedule`, `grade`, `status`, `defaults`,
  `migrations`, `observed_default_rate` and `rollforward`. These are the answer
  key, and they are computed **with the same pinned integer rules the contract
  hands the stages**: the same truncation, the same order of operations, the same
  remainder rules. A stage that implements its §4 correctly agrees with the book
  exactly; a stage that rounds differently is caught.

The estate is **fixed**: `Book.build(seed)` answers the same loans, facts,
artifacts and records for every seed, and the seed moves only the borrowers'
names. That is deliberate — the ten checks and their boundaries are built on these
particular facts (a loan whose arrears sit under the materiality threshold while
ninety days have passed, a cure that arrives before its probation, a grade that
crosses the SICR test, a window that spans a model change) and a seed that moved
them would move the course's own answer key.

Nothing here reads a clock and nothing here is random: the stream `build` draws
the names from is a plain congruential generator, so `build(7)` twice answers
equal records, equal records and equal counters.

Three conventions this module pins, because §2.3 leaves them to the author:

1. `status(loan, date)` is **total** over every (loan, reporting date) — a loan
   that has not been drawn yet, and one already written off, both have a row, and
   the row is what the policy's own rules say about the facts at that date.
   *Liveness* is a separate question, and `on_book(date)` is where it is asked: a
   loan is live at a date when it has been originated and no write-off is on it at
   or before that date. The roll-forward's populations come from `on_book`, not
   from `status`.
2. The **loan's outstanding principal** at a date is its contractual principal
   less the principal portions of the instalments actually paid by then, less
   prepayments, floored at zero — the complement of the drift a level-payment
   schedule produces, not the sum of the cash that arrived.
3. A **`cure` event clears the flags recorded before it only when it lands at or
   after the signalled default's probation** (`add_months(signalled_on,
   CURE_MONTHS)`). An early cure is a no-op, which is what makes §4.2's "a default
   whose cure arrives before the probation ends does not cure" visible in the
   records rather than only in a rule.

Every ask is one line of `log` (what was asked, for whom, and how many rows the
answer carried) and `stats()` recounts the ledger, so a check can prove what a
stage asked for, and that a refused call asked for nothing.
"""

import dates
import rules

LOAN_KEYS = ("loan", "borrower", "segment", "grade_origination", "principal_cents",
             "rate_bp", "term_months", "first_due", "origination", "collateral_kind",
             "collateral_cents", "undrawn_limit_cents", "measured_at")

PAYMENT_KEYS = ("loan", "due", "paid_on", "amount_cents", "kind")

EVENT_KEYS = ("loan", "date", "kind", "detail_cents")

RECOVERY_KEYS = ("loan", "date", "amount_cents", "source")

MODEL_KEYS = ("name", "version", "as_of", "grades", "pd_bp", "lgd_bp", "ccf_bp")

STATUS_KEYS = ("loan", "date", "grade", "dpd", "bucket", "stage", "default", "cured",
               "ead_cents", "ecl_cents")

LOG_KEYS = ("call", "argument", "rows")

STAT_KEYS = ("lookups", "schedules", "statuses", "migrations", "recoveries", "models")

#: Which counter each ask belongs to. `stats` is deliberately absent: the recount
#: must not move the ledger it recounts.
_CALL_STATS = {
    "loans": "lookups",
    "loan": "lookups",
    "payments": "lookups",
    "events": "lookups",
    "defaults": "lookups",
    "on_book": "lookups",
    "reporting_dates": "lookups",
    "grade": "lookups",
    "rollforward": "lookups",
    "schedule": "schedules",
    "status": "statuses",
    "migrations": "migrations",
    "observed_default_rate": "migrations",
    "recoveries": "recoveries",
    "recoveries_of": "recoveries",
    "models": "models",
    "model": "models",
    "model_in_force": "models",
}

PAYMENT_KINDS = ("instalment", "prepayment", "fee")

EVENT_KINDS = ("forbearance", "distressed-restructuring", "cross-default", "bankruptcy",
               "write-off", "cure")

RECOVERY_SOURCES = ("cash", "collateral", "costs")

MEASURED_AT = ("amortised-cost", "fvoci")

SCALE = {
    "loans": 250000,
    "borrowers": 180000,
    "segments": 6,
    "reporting_dates": 36,
    "defaulted": 4200,
    "written_off": 1100,
    "models": 3,
}

#: The last reporting date of the book, and how many month ends precede it.
LAST_REPORTING_DATE = "2033-12-31"

REPORTING_DATES = 36

#: The primary rating model: the artifact the bank's own provision is priced with.
RATING_MODEL = "pd-rating"

BOOK_ERROR = "book: "

#: The rate a period rate is built from, per basis point of the annual rate: `10000`.
DISCOUNT_SCALE = rules.DISCOUNT_SCALE


class BookError(ValueError):
    """The book's refusal: a shape it cannot accept, a loan or a date it does not hold."""


class LoanRecord(dict):
    """A loan record with `LOAN_KEYS`, and two aliases served by `__missing__`.

    `LOAN_KEYS` is the promise, and it has no `"id"` and no `"basis"`: a check may
    assert the key tuple exactly. The harness and a few callers read `loan["id"]`
    and `loan["basis"]` all the same, so those two names answer here **without
    being keys** — `"id"` is the record's own `"loan"`, and `"basis"` is
    `rules.DEFAULT_BASIS`, the day count the book's own records are kept on.
    """

    def __missing__(self, key):
        if key == "id" or key == "basis":
            return self["loan"] if key == "id" else rules.DEFAULT_BASIS
        raise KeyError(key)


class Rows(tuple):
    """A tuple a caller may also call: `book.loans` and `book.loans()` are one answer.

    §2.3 names the portfolio and the artifacts without a call (`loans`, `models`),
    while the harness reads them as methods. Both idioms answer the same tuple, so
    neither reader has to guess.
    """

    def __call__(self):
        return self


def _need(mapping, keys, what):
    """A mapping whose keys are exactly `keys`, in order, or the refusal naming it."""
    if not isinstance(mapping, dict):
        raise BookError(BOOK_ERROR + ("%s is a %s, not a mapping"
                                      % (what, type(mapping).__name__)))
    got = tuple(mapping)
    if got != tuple(keys):
        raise BookError(BOOK_ERROR + ("%s has the keys %r, not %r"
                                      % (what, got, tuple(keys))))
    return mapping


def _whole(value, what):
    """A whole number, and a `bool` is not one here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BookError(BOOK_ERROR + ("%s is a %s, not a whole number"
                                      % (what, type(value).__name__)))
    return value


def _text(value, what):
    """A text, or the refusal naming what arrived."""
    if not isinstance(value, str):
        raise BookError(BOOK_ERROR + ("%s is a %s, not a text"
                                      % (what, type(value).__name__)))
    return value


def _stream(seed):
    """A seed's deterministic integer stream — this module's only source of variety."""
    state = _whole(seed, "the seed") % 2147483648
    while True:
        state = (state * 1103515245 + 12345) % 2147483648
        yield state


# --- the estate -----------------------------------------------------------
#
# Twelve loans, the six segments, all seven origination grades. The estate is
# fixed on purpose: the checks' boundaries are built on these particular facts,
# and only the borrowers' names come from the seed's stream.
#
# (id, segment, grade at origination, principal_cents, rate_bp, term_months,
#  origination, first_due, collateral_kind, collateral_cents, undrawn_limit_cents,
#  measured_at)

_ESTATE = (
    ("L-01", "mortgage", "A", 24000000, 350, 120, "2030-09-15", "2030-10-31",
     "property", 30000000, 0, "amortised-cost"),
    ("L-02", "consumer", "B", 2400000, 890, 60, "2031-02-10", "2031-03-31",
     "none", 0, 0, "amortised-cost"),
    ("L-03", "sme", "C", 8000000, 520, 84, "2030-11-05", "2030-12-31",
     "receivables", 3000000, 5000000, "fvoci"),
    ("L-04", "corporate", "D", 16000000, 470, 96, "2030-12-10", "2031-01-31",
     "equipment", 5000000, 0, "amortised-cost"),
    ("L-05", "credit-card", "E", 130000, 1990, 24, "2031-04-20", "2031-05-31",
     "none", 0, 2000000, "amortised-cost"),
    ("L-06", "leasing", "F", 3600000, 640, 48, "2031-01-12", "2031-02-28",
     "equipment", 4000000, 0, "amortised-cost"),
    ("L-07", "mortgage", "B", 30000000, 420, 120, "2030-10-08", "2030-11-30",
     "property", 36000000, 4000000, "amortised-cost"),
    ("L-08", "consumer", "C", 1800000, 760, 48, "2030-10-20", "2030-11-30",
     "none", 0, 0, "amortised-cost"),
    ("L-09", "sme", "D", 12000000, 610, 72, "2030-11-25", "2030-12-31",
     "receivables", 4000000, 3000000, "amortised-cost"),
    ("L-10", "corporate", "A", 20000000, 390, 120, "2030-11-05", "2030-12-31",
     "equipment", 6000000, 0, "amortised-cost"),
    ("L-11", "credit-card", "default", 900000, 2400, 36, "2031-06-05", "2031-07-31",
     "none", 0, 0, "amortised-cost"),
    ("L-12", "leasing", "A", 4200000, 560, 36, "2032-01-15", "2032-02-29",
     "equipment", 4500000, 0, "fvoci"),
)

#: The instalments each borrower paid, as the instrument numbers them (1 is the
#: first due). `paid` pays a range on its own due date; `catch_up` pays a range on
#: one later date (so partial payments accumulate and never reset); `extra` books
#: a second instalment against one due, which is the drawn amount above the
#: schedule's own plan; `prepay` and `fee` are the other two kinds of row.
_PAYMENTS = {
    "L-01": (("paid", 1, 200),),
    "L-02": (("paid", 1, 60), ("fee", "2031-03-31", 48000)),
    "L-03": (("paid", 1, 84), ("extra", 20, 2)),
    "L-04": (("paid", 1, 96),),
    "L-05": (("paid", 1, 2), ("paid", 4, 24)),
    "L-06": (("paid", 1, 1), ("catch_up", "2031-06-10", 2, 3), ("paid", 4, 48)),
    "L-07": (("paid", 1, 10), ("extra", 5, 2)),
    "L-08": (("paid", 1, 48),),
    "L-09": (("paid", 1, 5), ("extra", 4, 2), ("catch_up", "2032-02-10", 6, 9),
             ("paid", 10, 72)),
    "L-10": (("paid", 1, 12),),
    "L-11": (),
    "L-12": (("paid", 1, 36),),
}

#: (the date, the kind, the cents the event carries).
_EVENTS = {
    "L-02": (("2032-06-30", "forbearance", 240000),),
    "L-04": (("2032-04-15", "cross-default", 16000000),),
    "L-07": (("2031-11-20", "bankruptcy", 0), ("2032-03-15", "write-off", 0)),
    "L-08": (("2031-09-30", "forbearance", 180000), ("2032-01-31", "cure", 0)),
    "L-09": (("2031-10-31", "cure", 0), ("2032-02-29", "cure", 0)),
    "L-10": (("2032-01-31", "distressed-restructuring", 900000),
             ("2032-05-20", "write-off", 0)),
    "L-11": (("2031-06-10", "bankruptcy", 0),),
}

#: (the date, the amount in cents — a cost is negative — and the source).
_RECOVERIES = {
    "L-07": (("2032-04-30", 1200000, "cash"), ("2032-05-31", -150000, "costs"),
             ("2032-09-30", 8000000, "collateral")),
    "L-10": (("2032-06-30", 1500000, "cash"), ("2032-07-31", -200000, "costs"),
             ("2032-11-30", 4500000, "collateral")),
}

#: The bank's own re-ratings: the grade it records from a date on. A loan in
#: default is recorded at `"default"` whatever this says.
_GRADE_STEPS = {
    "L-06": (("2031-08-31", "E"),),
    "L-12": (("2032-09-30", "C"),),
}

#: The per-year cumulative PDs, in basis points: five years, monotone, inside
#: `0..10000`, the last one the lifetime.
_RATING_PD = {
    "A": (40, 90, 150, 220, 300),
    "B": (90, 190, 300, 420, 560),
    "C": (260, 520, 800, 1050, 1300),
    "D": (520, 1000, 1500, 2000, 2500),
    "E": (900, 1750, 2600, 3400, 4200),
    "F": (1800, 3200, 4400, 5400, 6200),
    "default": (10000, 10000, 10000, 10000, 10000),
}

_UPDATED_PD = {
    "A": (45, 100, 165, 235, 320),
    "B": (100, 210, 330, 460, 610),
    "C": (280, 560, 860, 1130, 1400),
    "D": (560, 1080, 1600, 2150, 2700),
    "E": (960, 1860, 2760, 3600, 4450),
    "F": (1900, 3380, 4640, 5700, 6540),
    "default": (10000, 10000, 10000, 10000, 10000),
}

_RATING_LGD = {"A": 4500, "B": 4800, "C": 5200, "D": 5800, "E": 6400, "F": 7000,
               "default": 7500}

_UPDATED_LGD = {"A": 4600, "B": 4950, "C": 5400, "D": 5900, "E": 6600, "F": 7100,
                "default": 7500}

_WORKOUT_LGD = {"A": 4300, "B": 4700, "C": 5100, "D": 5700, "E": 6300, "F": 6900,
                "default": 7400}

#: The workout artifact's own forwards. A loan in workout has already defaulted, so
#: the grades that reach it (a card and an SME book in this estate, C and E) are
#: certain to be a loss, and the rest of the scale carries the workout view's higher
#: forwards rather than the rating model's. This artifact is dated after every
#: reporting date, so it is never in force: it is the world's own counterfactual, the
#: artifact a stage passes explicitly, and the one whose backtest is deliberately
#: outside tolerance at its own degrees of freedom — without it, a diagnostic the
#: course pins a table for could never be seen to fire.
_WORKOUT_PD = {
    "A": (2000, 3200, 4400, 5600, 6800),
    "B": (3000, 4400, 5800, 7200, 8600),
    "C": (10000, 10000, 10000, 10000, 10000),
    "D": (3500, 4900, 6300, 7700, 9100),
    "E": (10000, 10000, 10000, 10000, 10000),
    "F": (4000, 5400, 6800, 8200, 9600),
    "default": (10000, 10000, 10000, 10000, 10000),
}

_MODEL_CCF = {"mortgage": 6000, "consumer": 8000, "sme": 7000, "corporate": 5000,
              "credit-card": 9000, "leasing": 6500}

#: The loans the second rating model re-rated, and the grade it gives them.
_RERATED = {"L-06": "E", "L-07": "default", "L-12": "C"}

_BORROWERS = (
    "Northwind Cement", "Contoso Steel", "Fabrikam Foods", "Aalborg Shipping",
    "Baltic Timber", "Oslo Fasteners", "Turin Motors", "Sevilla Hotels",
    "Lisbon Ceramics", "Dublin Pharma", "Antwerp Diamonds", "Bilbao Tools",
    "Bergen Fisheries", "Gdansk Furniture", "Tallinn Software", "Riga Logistics",
    "Vilnius Textiles", "Zagreb Winery", "Trieste Coffee", "Valencia Citrus",
    "Porto Granite", "Cork Dairy", "Utrecht Optics", "Ghent Brewing",
)


# --- the bank's own arithmetic --------------------------------------------
#
# Everything below is written the way §4 pins it: the same truncation, the same
# order of operations, the same remainder rules. These functions are the bank's
# records, so a stage that implements its own §4 correctly lands on the same
# integers — and a stage that rounds differently does not.

def _period_rate(rate_bp, basis):
    """The period rate of a loan's rate under a basis, from the policy's own rule."""
    return rules.period_rate(rate_bp, basis)


def _amortise(balance, period_bp, payment):
    """One period of a loan: interest on the balance, then the payment.

    The interest is truncated to the cent (`balance * period_bp // 10000`), which
    is why a level payment has to be searched for rather than solved for.
    """
    return balance + balance * period_bp // 10000 - payment


def _level_payment(principal_cents, rate_bp, term_months, basis):
    """The **smallest** instalment in cents that clears `principal_cents` in `term_months`.

    "Clears" is at or below zero: the balance is carried at the basis's period rate
    and truncated at every step, so the smallest clearing payment is an integer
    search, not a closed form. A term below one month, a rate outside `0..MAX_EIR_BP`
    or a principal that is not a positive whole number is refused by name.
    """
    _whole(principal_cents, "the principal")
    _whole(rate_bp, "the rate")
    _whole(term_months, "the term")
    if basis not in dates.BASES:
        raise BookError(BOOK_ERROR + ("%r is not one of the bases %r" % (basis, dates.BASES)))
    if term_months < 1:
        raise BookError(BOOK_ERROR + ("a term of %d months is not a loan" % (term_months,)))
    if principal_cents <= 0:
        raise BookError(BOOK_ERROR + ("a principal of %d cents is not a loan"
                                      % (principal_cents,)))
    if rate_bp < 0 or rate_bp > rules.MAX_EIR_BP:
        raise BookError(BOOK_ERROR + ("a rate of %d basis points is outside 0..%d"
                                      % (rate_bp, rules.MAX_EIR_BP)))
    period_bp = _period_rate(rate_bp, basis)
    low, high = 1, principal_cents + principal_cents * period_bp // 10000 + 1
    while low < high:
        middle = (low + high) // 2
        balance = principal_cents
        for _step in range(term_months):
            balance = _amortise(balance, period_bp, middle)
        if balance <= 0:
            high = middle
        else:
            low = middle + 1
    return low


def _flows(loan):
    """The contract's own flows: `(date, amount_cents)` per instalment, in order.

    Instalment `i` falls due at `add_months(first_due, i)` for `i = 0..term-1`, so
    the clamping rule of `dates.add_months` is the schedule's. Each instalment is
    the level payment except the last, which carries the remainder: it is exactly
    what is left with that period's interest, so the balance closes at zero and the
    last instalment is never larger than the level payment it replaces.
    """
    basis = rules.DEFAULT_BASIS
    period_bp = _period_rate(loan["rate_bp"], basis)
    payment = _level_payment(loan["principal_cents"], loan["rate_bp"],
                             loan["term_months"], basis)
    balance = loan["principal_cents"]
    flows = []
    for step in range(loan["term_months"]):
        interest = balance * period_bp // 10000
        amount = balance + interest if step == loan["term_months"] - 1 else payment
        balance = balance + interest - amount
        flows.append((dates.add_months(loan["first_due"], step), amount))
    if balance != 0:
        raise BookError(BOOK_ERROR + ("the schedule of %r closes at %d cents, not zero"
                                      % (loan["loan"], balance)))
    return tuple(flows)


def _level_payment_of(loan):
    """The level payment the loan's own schedule is built from."""
    return _level_payment(loan["principal_cents"], loan["rate_bp"], loan["term_months"],
                          rules.DEFAULT_BASIS)


def _present_value(flows, rate_bp, basis):
    """The present value of `flows` at `rate_bp` under `basis`, stepped and truncated.

    The factor is carried forward one period at a time
    (`factor = factor * 10000 // (10000 + period_rate_bp)`) and each term is
    `amount * factor // 10000`, so no power is ever computed and no integer leaves
    the flow's own scale. `flows` is a sequence of `(date, amount_cents)` pairs.
    """
    period_bp = _period_rate(rate_bp, basis)
    factor = rules.DISCOUNT_SCALE
    total = 0
    for _date, amount in flows:
        factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
        total = total + amount * factor // rules.DISCOUNT_SCALE
    return total


def _carrying(loan, payments):
    """The net carrying amount: the principal less the fees the loan's own rows hold."""
    fees = sum(row["amount_cents"] for row in payments if row["kind"] == "fee")
    return loan["principal_cents"] - fees


def _effective_rate(loan, flows, payments):
    """The **smallest** rate in `0..MAX_EIR_BP` whose present value pays the carrying amount.

    Found by bisection over the integer rate: a truncated rate leaves a residue,
    and the residue is reported rather than hidden. Answers `(rate_bp, pv_cents,
    carrying_cents, residual_cents, periods, basis)`; the basis is the book's own,
    because a loan record carries no basis of its own.
    """
    basis = rules.DEFAULT_BASIS
    carrying = _carrying(loan, payments)
    low, high = 0, rules.MAX_EIR_BP
    while low < high:
        middle = (low + high) // 2
        if _present_value(flows, middle, basis) <= carrying:
            high = middle
        else:
            low = middle + 1
    pv_cents = _present_value(flows, low, basis)
    return low, pv_cents, carrying, carrying - pv_cents, len(flows), basis


def _months_between(start, end):
    """The whole months from `start` to `end`, with the clamping rule honoured.

    `months_between("2031-01-31", "2031-02-28")` is one: a month later, clamped to
    February's last day, is still at or before the end. A flow that lands on the
    day itself is zero months away.
    """
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months


# --- the rows -------------------------------------------------------------

def _loans(seed):
    """The twelve loan records, in estate order — `LOAN_KEYS`, the seed naming them."""
    stream = _stream(seed)
    loans = []
    for index, row in enumerate(_ESTATE):
        loan_id, segment, grade, principal, rate, term, origination, first_due, \
            kind, collateral, undrawn, measured = row
        loans.append(LoanRecord((
            ("loan", loan_id),
            ("borrower", _BORROWERS[(next(stream) + index * 7) % len(_BORROWERS)]),
            ("segment", segment),
            ("grade_origination", grade),
            ("principal_cents", principal),
            ("rate_bp", rate),
            ("term_months", term),
            ("first_due", first_due),
            ("origination", origination),
            ("collateral_kind", kind),
            ("collateral_cents", collateral),
            ("undrawn_limit_cents", undrawn),
            ("measured_at", measured),
        )))
    return tuple(loans)


def _payments_of(loan, flows):
    """The borrower's payments — `PAYMENT_KEYS` rows, in the order they were made.

    The spec is the fixture's, the amounts and the due dates are the schedule's: a
    paid instalment carries its own due date and its instalment's amount, a catch-up
    carries one later `paid_on` for several dues (partial payments accumulate, they
    do not reset), an overpayment books a second instalment against one due, and a
    `fee` and a `prepayment` are the other two kinds.
    """
    rows = []
    for step in _PAYMENTS.get(loan["loan"], ()):
        if step[0] == "paid" or step[0] == "catch_up":
            first, last = step[-2], step[-1]
            for index in range(first, min(last, len(flows)) + 1):
                due, amount = flows[index - 1]
                paid_on = due if step[0] == "paid" else step[1]
                rows.append({"loan": loan["loan"], "due": due, "paid_on": paid_on,
                             "amount_cents": amount, "kind": "instalment"})
        elif step[0] == "extra":
            index, multiple = step[1], step[2]
            if index <= len(flows):
                due, amount = flows[index - 1]
                rows.append({"loan": loan["loan"], "due": due, "paid_on": due,
                             "amount_cents": amount * multiple, "kind": "instalment"})
        elif step[0] == "prepay":
            rows.append({"loan": loan["loan"], "due": step[1], "paid_on": step[1],
                         "amount_cents": step[2], "kind": "prepayment"})
        elif step[0] == "fee":
            rows.append({"loan": loan["loan"], "due": step[1], "paid_on": step[1],
                         "amount_cents": step[2], "kind": "fee"})
        else:
            raise BookError(BOOK_ERROR + ("%r is not a payment the fixtures know"
                                          % (step[0],)))
    return tuple(sorted((dict(row) for row in rows),
                        key=lambda row: (row["paid_on"], row["due"], row["kind"])))


def _events_of(loan):
    """The events the bank recorded on one loan — `EVENT_KEYS` rows, in date order."""
    rows = [dict(zip(EVENT_KEYS, (loan["loan"], date, kind, detail)))
            for date, kind, detail in _EVENTS.get(loan["loan"], ())]
    return tuple(sorted(rows, key=lambda row: (row["date"], row["kind"])))


def _recoveries_of(loan):
    """The recovery rows on one loan — `RECOVERY_KEYS`, in date order, costs negative."""
    rows = [dict(zip(RECOVERY_KEYS, (loan["loan"], date, amount, source)))
            for date, amount, source in _RECOVERIES.get(loan["loan"], ())]
    return tuple(sorted(rows, key=lambda row: (row["date"], row["source"])))


def _models():
    """The three artifacts: two versions of the rating model and one later workflow model.

    `grades` is the model's **own** rating of every loan; the second version re-rates
    the loans `_RERATED` names, which is what stage 10's journal has to attribute.
    `pd_bp` is per grade and per year, `lgd_bp` per grade, `ccf_bp` per segment.
    """
    first_grades = {row[0]: row[2] for row in _ESTATE}
    second_grades = dict(first_grades)
    second_grades.update(_RERATED)
    return (
        _model(RATING_MODEL, 1, "2030-12-31", first_grades, _RATING_PD, _RATING_LGD,
               _MODEL_CCF),
        _model(RATING_MODEL, 2, "2032-01-31", second_grades, _UPDATED_PD, _UPDATED_LGD,
               _MODEL_CCF),
        _model("lgd-workout", 1, "2034-06-30", first_grades, _WORKOUT_PD, _WORKOUT_LGD,
               _MODEL_CCF),
    )


def _model(name, version, as_of, grades, pd_bp, lgd_bp, ccf_bp):
    """One artifact record, `MODEL_KEYS` in order, with the policy's shapes checked."""
    if tuple(pd_bp) != rules.GRADES:
        raise BookError(BOOK_ERROR + ("model %r v%d rates the grades %r, not %r"
                                      % (name, version, tuple(pd_bp), rules.GRADES)))
    if tuple(lgd_bp) != rules.GRADES:
        raise BookError(BOOK_ERROR + ("model %r v%d prices the grades %r, not %r"
                                      % (name, version, tuple(lgd_bp), rules.GRADES)))
    if tuple(ccf_bp) != rules.SEGMENTS:
        raise BookError(BOOK_ERROR + ("model %r v%d draws on the segments %r, not %r"
                                      % (name, version, tuple(ccf_bp), rules.SEGMENTS)))
    return {"name": name, "version": version, "as_of": as_of, "grades": grades,
            "pd_bp": pd_bp, "lgd_bp": lgd_bp, "ccf_bp": ccf_bp}


def _facts(seed):
    """Everything derived from the estate: the flows, the payments and the rates."""
    loans = _loans(seed)
    flows, level, payments, eir = {}, {}, {}, {}
    for loan in loans:
        loan_id = loan["loan"]
        flows[loan_id] = _flows(loan)
        level[loan_id] = _level_payment_of(loan)
        payments[loan_id] = _payments_of(loan, flows[loan_id])
        eir[loan_id] = _effective_rate(loan, flows[loan_id], payments[loan_id])
    return {
        "loans": loans,
        "flows": flows,
        "level": level,
        "payments": payments,
        "eir": eir,
        "events": {loan["loan"]: _events_of(loan) for loan in loans},
        "recoveries": {loan["loan"]: _recoveries_of(loan) for loan in loans},
        "models": _models(),
    }


class _Loan:
    """One loan's facts, and the bank's own arithmetic over them.

    Everything here is per loan and stateless with respect to the rest of the book:
    the flows, the payments, the events, the recoveries, the effective rate, the
    drawn and undrawn amounts, the outstanding principal, the arrears, the defaults
    the bank signalled and the grade it recorded. What needs the rest of the
    portfolio — the segment CCF, the stage, the provision — is the book's.
    """

    def __init__(self, facts, loan, reporting):
        self.record = loan
        self.flows = facts["flows"][loan["loan"]]
        self.payments = facts["payments"][loan["loan"]]
        self.events = facts["events"][loan["loan"]]
        self.recoveries = facts["recoveries"][loan["loan"]]
        self.eir_bp, self.pv_cents, self.carrying_cents, self.residual_cents, \
            self.periods, self.basis = facts["eir"][loan["loan"]]
        self.level_payment_cents = facts["level"][loan["loan"]]
        self.reporting = reporting
        self.grade_steps = tuple(sorted(_GRADE_STEPS.get(loan["loan"], ())))
        self.write_off = None
        for event in self.events:
            if event["kind"] == "write-off":
                self.write_off = event["date"]
        self.signals = []
        self.flag_states = {}
        self._walk_defaults()

    # -- the observed facts -------------------------------------------------
    def _paid(self, kinds, date):
        """The cents paid up to `date` by rows of the named kinds."""
        return sum(row["amount_cents"] for row in self.payments
                   if row["kind"] in kinds and row["paid_on"] <= date)

    def drawn_cents(self, date):
        """What the borrower has actually drawn: instalments paid less prepayments."""
        return max(0, self._paid(("instalment",), date) - self._paid(("prepayment",), date))

    def plan_cents(self, date):
        """What the schedule's own plan said would have been paid by `date`."""
        return sum(amount for due, amount in self.flows if due <= date)

    def undrawn_cents(self, date):
        """The limit less the drawn amount **above the schedule's plan**, never negative."""
        limit = self.record["undrawn_limit_cents"]
        excess = self.drawn_cents(date) - self.plan_cents(date)
        return max(0, limit - max(0, excess))

    def outstanding_cents(self, date):
        """The loan's outstanding principal at `date`.

        The contractual principal less the principal portions of the instalments
        actually paid by then, less prepayments, floored at zero. A period's
        interest is truncated on the balance before the payment and the principal
        portion is what the payment left over, so the balance is the schedule's own
        amortisation balance rather than the sum of the cash that arrived.
        """
        period_bp = _period_rate(self.record["rate_bp"], rules.DEFAULT_BASIS)
        balance = self.record["principal_cents"]
        for due, _amount in self.flows:
            if due > date:
                break
            interest = balance * period_bp // 10000
            paid = sum(row["amount_cents"] for row in self.payments
                       if row["kind"] == "instalment" and row["due"] == due
                       and row["paid_on"] <= date)
            balance = balance - min(balance, max(0, paid - interest))
        return max(0, balance - self._paid(("prepayment",), date))

    def live(self, date):
        """Whether the book still holds the loan at `date` (originated, not written off)."""
        return self.record["origination"] < date \
            and not (self.write_off is not None and self.write_off <= date)

    # -- the delinquency ----------------------------------------------------
    def arrears_cents(self, date):
        """What is owed and unpaid on the instalments due by `date`."""
        owed, covered = 0, 0
        for due, amount in self.flows:
            if due > date:
                break
            owed = owed + amount
            covered = covered + sum(row["amount_cents"] for row in self.payments
                                    if row["kind"] == "instalment" and row["due"] == due
                                    and row["paid_on"] <= date)
        return max(0, owed - covered)

    def reference_due(self, date):
        """The oldest instalment that is still unpaid, or `None` when there is none."""
        paid = {}
        for row in self.payments:
            if row["kind"] == "instalment" and row["paid_on"] <= date:
                paid[row["due"]] = paid.get(row["due"], 0) + row["amount_cents"]
        for due, amount in self.flows:
            if due > date:
                return None
            if paid.get(due, 0) < amount:
                return due
        return None

    def material(self, date):
        """The policy's two-part test: both halves must pass."""
        arrears = self.arrears_cents(date)
        if arrears < rules.MATERIALITY_ABSOLUTE_CENTS:
            return False
        return arrears * rules.DISCOUNT_SCALE >= rules.MATERIALITY_RELATIVE_BP \
            * self.drawn_cents(date)

    def dpd(self, date):
        """The days from the oldest **materially** unpaid instalment to `date`.

        Arrears that fail either half of the materiality test do not accrue days:
        a loan whose shortfall sits under €100 has no days past due however long it
        has been sitting there, and neither has one under 1% of its exposure.
        """
        due = self.reference_due(date)
        if due is None or not self.material(date):
            return 0
        return dates.days_between(due, date)

    def bucket(self, dpd, defaulted):
        """`dpd` walked through `BUCKET_DAYS`; a signalled default speaks at zero days."""
        if defaulted:
            return "default"
        for index, bound in enumerate(rules.BUCKET_DAYS):
            if dpd <= bound:
                return rules.BUCKETS[index]
        return rules.BUCKETS[-1]

    # -- the defaults the bank signalled ------------------------------------
    def _walk_defaults(self):
        """Walk the reporting dates, signalling defaults and honouring cures.

        A default is signalled at the first reporting date at which a trigger holds
        — days past due at the backstop, or an uncured event of one of `UTP_FLAGS`
        — and its probation runs `CURE_MONTHS` from that date. A `cure` event clears
        the flags and closes the default **only when it lands at or after the
        probation**: an early cure is a no-op, so the loan stays defaulted between
        two cures, which is the case §4.2's own rule is about.
        """
        flags = set()
        opened = None
        index = 0
        for date in self.reporting:
            while index < len(self.events) and self.events[index]["date"] <= date:
                event = self.events[index]
                index = index + 1
                if event["kind"] in rules.UTP_FLAGS:
                    flags.add(event["kind"])
                elif event["kind"] == "cure" and opened is not None \
                        and opened["probation_until"] <= event["date"]:
                    opened["cured_on"] = event["date"]
                    self.signals.append(opened)
                    opened = None
                    flags.clear()
            self.flag_states[date] = frozenset(flags)
            names = ()
            dpd = self.dpd(date)
            if dpd >= rules.DEFAULT_DAYS_PAST_DUE:
                names = ("days-past-due",)
            names = names + tuple(kind for kind in rules.UTP_FLAGS if kind in flags)
            if names and opened is None:
                opened = {"loan": self.record["loan"], "signalled_on": date,
                          "triggers": names, "cured_on": None,
                          "probation_until": dates.add_months(date, rules.CURE_MONTHS)}
        if opened is not None:
            self.signals.append(opened)
        self.signals.sort(key=lambda row: row["signalled_on"])

    def flags_at(self, date):
        """The uncured `UTP_FLAGS` kinds the bank holds at a **reporting** date."""
        return self.flag_states.get(date, frozenset())

    def triggers(self, date):
        """What makes the loan a default at `date`, in the contract's own order."""
        names = []
        if self.dpd(date) >= rules.DEFAULT_DAYS_PAST_DUE:
            names.append("days-past-due")
        for kind in rules.UTP_FLAGS:
            if kind in self.flags_at(date):
                names.append(kind)
        return tuple(names)

    def defaulted(self, date):
        """Whether the loan is defaulted at `date`.

        A trigger speaks for itself, and a signalled default that has not validly
        cured speaks even at zero days past due — which is why the bank's own
        `default` flag is not the bucket's arithmetic done twice.
        """
        if self.dpd(date) >= rules.DEFAULT_DAYS_PAST_DUE:
            return True
        if self.flags_at(date):
            return True
        return any(row["cured_on"] is None and row["signalled_on"] <= date
                   for row in self.signals)

    def default_date(self):
        """The date the loan's first default was signalled, or `None`."""
        return self.signals[0]["signalled_on"] if self.signals else None

    def grade(self, date):
        """The grade the bank records for the loan at `date`.

        `default` while the loan is defaulted, the last re-rating at or before the
        date otherwise, and its origination grade before any re-rating. Total over
        every date, like the status rows are.
        """
        if self.defaulted(date):
            return "default"
        grade = self.record["grade_origination"]
        for step_date, value in self.grade_steps:
            if step_date <= date:
                grade = value
        return grade

    # -- what came back -----------------------------------------------------
    def recovered_cents(self, default_date):
        """The recovery discounted to `default_date`, the collateral's haircut applied.

        A `collateral` row is haircut by the policy for the loan's own collateral
        kind and then discounted from the day it was collected; cash and costs pass
        at face and are discounted from their own day too. A cost is negative, so it
        reduces what came back.
        """
        period_bp = _period_rate(self.record["rate_bp"], rules.DEFAULT_BASIS)
        total = 0
        for row in self.recoveries:
            amount = row["amount_cents"]
            if row["source"] == "collateral":
                haircut = rules.COLLATERAL_HAIRCUT_BP[self.record["collateral_kind"]]
                amount = amount * (rules.DISCOUNT_SCALE - haircut) // rules.DISCOUNT_SCALE
            factor = rules.DISCOUNT_SCALE
            for _step in range(_months_between(default_date, row["date"])):
                factor = factor * rules.DISCOUNT_SCALE \
                    // (rules.DISCOUNT_SCALE + period_bp)
            total = total + amount * factor // rules.DISCOUNT_SCALE
        return total

    def lgd_bp(self):
        """The loan's own loss given default, in basis points, clamped to the policy."""
        default_date = self.default_date()
        if default_date is None:
            raise BookError(BOOK_ERROR + ("%r has never defaulted, so it has no loss given "
                                          "default" % (self.record["loan"],)))
        balance = self.outstanding_cents(default_date)
        if balance <= 0:
            return rules.LGD_CAP_BP
        recovered = min(self.recovered_cents(default_date), balance)
        answer = rules.DISCOUNT_SCALE - recovered * rules.DISCOUNT_SCALE // balance
        return min(max(answer, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)


def _model_pd(model, grade, months):
    """The model's cumulative PD for `grade` over `months`, truncated at every step.

    The artifact hands one cumulative PD per year. A horizon inside a year is that
    year's figure scaled by the months it moved through; a horizon inside the
    series is the earlier year plus its share of the difference; a horizon beyond
    the series is the series' last entry, which is the lifetime PD. Nothing here
    invents a shape: the data is the model's and this is a reading of it.
    """
    series = model["pd_bp"][grade]
    if months <= 0:
        return 0
    whole, rest = divmod(months, rules.PERIODS_PER_YEAR)
    if whole >= len(series):
        return series[-1]
    if whole == 0:
        return series[0] * months // rules.PERIODS_PER_YEAR
    if rest == 0:
        return series[whole - 1]
    return series[whole - 1] + (series[whole] - series[whole - 1]) * rest \
        // rules.PERIODS_PER_YEAR


class Book:
    """The bank: the portfolio, the artifacts, and the records it keeps about them.

    `Book.build(seed)` is the way in, and every answer it gives is deterministic.
    A caller names a loan by its record or by its id, and a refusal names the
    offender: the loan, the date, the model or the window it could not accept.
    """

    def __init__(self, facts, reporting):
        self._facts = facts
        self._reporting = tuple(reporting)
        self._ids = tuple(loan["loan"] for loan in facts["loans"])
        self._loans = {loan["loan"]: _Loan(facts, loan, self._reporting)
                       for loan in facts["loans"]}
        self._models = tuple(facts["models"])
        self._log = []
        self._ccf = self._segment_ccfs()
        self._stages = {}
        self._eads = {}
        self._ecls = {}
        self._statuses = {}
        for loan_id in self._ids:
            self._record(loan_id)

    # -- the segment CCF, the model in force, the stages, the provisions ----
    def _segment_ccfs(self):
        """The observed CCF per segment: the aggregate drawdown over the aggregate limit.

        A segment's defaulted loans contribute their drawdown at default against
        their undrawn limit at origination, and the ratio is taken **after** the
        sums, not averaged per loan. A segment with nothing to divide by answers the
        policy's floor: "we have not observed one yet" is the floor, not zero.
        """
        drawdowns = {segment: 0 for segment in rules.SEGMENTS}
        openings = {segment: 0 for segment in rules.SEGMENTS}
        for loan_id in self._ids:
            loan = self._loans[loan_id]
            default_date = loan.default_date()
            if default_date is None:
                continue
            segment = loan.record["segment"]
            drawn = loan.drawn_cents(default_date) \
                - loan.drawn_cents(loan.record["origination"])
            drawdowns[segment] = drawdowns[segment] + max(0, drawn)
            openings[segment] = openings[segment] + loan.undrawn_cents(
                loan.record["origination"])
        ratios = {}
        for segment in rules.SEGMENTS:
            if openings[segment] <= 0:
                ratios[segment] = rules.CCF_FLOOR_BP
            else:
                ratio = drawdowns[segment] * rules.DISCOUNT_SCALE // openings[segment]
                ratios[segment] = min(max(ratio, rules.CCF_FLOOR_BP), rules.CCF_CAP_BP)
        return ratios

    def _in_force(self, date):
        """The artifact in force at `date`: the greatest `as_of` not after it, then version.

        Answers `None` before the first artifact's `as_of`. The third model's `as_of`
        lies beyond every reporting date, so the rule is one answer per date.
        """
        found = None
        for model in self._models:
            if model["as_of"] > date:
                continue
            if found is None or (model["as_of"], model["version"]) \
                    > (found["as_of"], found["version"]):
                found = model
        return found

    def _sicr(self, loan, date, model):
        """Whether the loan shows a significant increase in credit risk at `date`.

        The two sides are the loan's **lifetime** PDs over its remaining life at
        that date: the current one at the grade the bank records for the date, and
        the one it started with at its origination grade, both from the artifact in
        force. Either half of §4.7's test makes it true — twice the origination PD,
        or an absolute move of `SICR_ABSOLUTE_BP` — and neither needs a division.
        """
        months = len([due for due, _amount in loan.flows if due > date])
        current = _model_pd(model, loan.grade(date), months)
        started = _model_pd(model, loan.record["grade_origination"], months)
        return current * rules.DISCOUNT_SCALE >= started * rules.SICR_MULTIPLIER_BP \
            or current - started >= rules.SICR_ABSOLUTE_BP

    def _stage_of(self, loan):
        """The stage at every reporting date, with the policy's return rule applied.

        A defaulted loan is in stage 3; a live test — the SICR reading, the days
        past due backstop, or an uncured flag — puts it in stage 2; otherwise it is
        in stage 1. A loan that was in stage 2 returns to stage 1 only after
        `SICR_RETURN_PERIODS` consecutive quiet reporting dates, while a loan that
        leaves a default by curing is compared afresh at the date it cures: the
        cure is stage 2's rule, not this one.
        """
        stages = {}
        previous, run = 1, 0
        for date in self._reporting:
            defaulted = loan.defaulted(date)
            quiet = (not defaulted and not loan.flags_at(date)
                     and loan.dpd(date) < rules.SICR_DAYS_PAST_DUE
                     and not self._sicr(loan, date, self._in_force(date)))
            if defaulted:
                stage, run = 3, 0
            elif quiet:
                if previous == 2:
                    run = run + 1
                    stage = 1 if run >= rules.SICR_RETURN_PERIODS else 2
                else:
                    run = 0
                    stage = 1
            else:
                stage, run = 2, 0
            stages[date] = stage
            previous = stage
        return stages

    def _ead_cents(self, loan, date):
        """The exposure at default: what is drawn, plus the undrawn limit at the CCF."""
        return loan.drawn_cents(date) + loan.undrawn_cents(date) \
            * self._ccf[loan.record["segment"]] // rules.DISCOUNT_SCALE

    def _ecl_cents(self, loan, date, scenario, model, stage, exposure=None):
        """One scenario's expected credit loss, in the contract's own arithmetic order.

        The horizon is the stage's — twelve months in stage 1, the loan's remaining
        life after that — the PD is the artifact's own cumulative PD over the
        horizon scaled by the scenario's multiplier, the LGD is stage 4's for a
        defaulted loan and the artifact's otherwise, and the loss is
        `pd * lgd // 10000` then `* ead // 10000` and only then discounted.

        `exposure` is the balance the loss is taken on: stage 5's own answer at the
        date, which is what the book records, and an explicitly passed artifact's
        re-estimate under its own `ccf_bp` when one is supplied — a counterfactual
        model is priced with its own exposure, and its CCF is part of it.
        """
        if model is None:
            return 0
        if exposure is None:
            exposure = self._eads[loan.record["loan"]][date]
        if exposure <= 0:
            return 0
        if stage == 1:
            horizon = rules.PERIODS_PER_YEAR
        else:
            horizon = len([due for due, _amount in loan.flows if due > date])
        if horizon <= 0:
            return 0
        grade = model["grades"][loan.record["loan"]]
        pd_bp = _model_pd(model, grade, horizon) \
            * rules.SCENARIO_PD_MULTIPLIER_BP[scenario] // rules.DISCOUNT_SCALE
        pd_bp = min(pd_bp, rules.DISCOUNT_SCALE)
        if loan.defaulted(date):
            lgd_bp = loan.lgd_bp()
        else:
            lgd_bp = model["lgd_bp"][grade]
        loss_cents = pd_bp * lgd_bp // rules.DISCOUNT_SCALE * exposure // rules.DISCOUNT_SCALE
        basis = rules.DEFAULT_BASIS
        if stage == 1:
            return _present_value(((None, loss_cents),), loan.eir_bp, basis)
        share = loss_cents // horizon
        period_bp = _period_rate(loan.eir_bp, basis)
        factor, total = rules.DISCOUNT_SCALE, 0
        for _step in range(horizon):
            factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)
            total = total + share * factor // rules.DISCOUNT_SCALE
        return total

    def _artifact_exposure(self, loan_id, date, model):
        """The exposure an artifact prices: stage 5's numbers with the artifact's own CCF.

        Passed a real artifact — a model a stage-8 line or a stage-6 what-if names —
        the CCF is the artifact's, so the re-estimate is `drawn + undrawn * ccf_bp //
        10000`, the same truncation stage 5 uses. `None` is the book's own exposure.
        """
        if model is None:
            return self._eads[loan_id][date]
        holder = self._loans[loan_id]
        ccf = model["ccf_bp"][holder.record["segment"]]
        return holder.drawn_cents(date) \
            + holder.undrawn_cents(date) * ccf // rules.DISCOUNT_SCALE

    def _weighted_cents(self, loan, date, model, stage, exposure=None):
        """The three scenarios' provisions, weight by weight, each product truncated."""
        total = 0
        for scenario in rules.SCENARIOS:
            total = total + self._ecl_cents(loan, date, scenario, model, stage, exposure) \
                * rules.SCENARIO_WEIGHTS_BP[scenario] // rules.DISCOUNT_SCALE
        return total

    def _record(self, loan_id):
        """Compute and keep one loan's own records: the stage, the EAD, the ECL, the row."""
        loan = self._loans[loan_id]
        stages = self._stage_of(loan)
        self._stages[loan_id] = stages
        self._eads[loan_id] = {date: self._ead_cents(loan, date)
                               for date in self._reporting}
        self._ecls[loan_id] = {}
        rows = {}
        for date in self._reporting:
            model = self._in_force(date)
            ecl = self._weighted_cents(loan, date, model, stages[date]) if model else 0
            self._ecls[loan_id][date] = ecl
            defaulted = loan.defaulted(date)
            dpd = loan.dpd(date)
            rows[date] = {"loan": loan_id, "date": date, "grade": loan.grade(date),
                          "dpd": dpd, "bucket": loan.bucket(dpd, defaulted),
                          "stage": stages[date], "default": defaulted,
                          "cured": (not defaulted) and any(
                              row["cured_on"] is not None and row["cured_on"] <= date
                              for row in loan.signals),
                          "ead_cents": self._eads[loan_id][date], "ecl_cents": ecl}
        self._statuses[loan_id] = rows

    # -- the register -------------------------------------------------------
    def _identify(self, loan, call):
        """A loan record or an id, resolved to the id the book holds."""
        if isinstance(loan, dict):
            name = loan.get("loan", loan.get("id"))
        elif isinstance(loan, str):
            name = loan
        else:
            raise BookError(BOOK_ERROR + ("%s asked for a loan as %r, which is neither a "
                                          "record nor an id" % (call, loan)))
        if not isinstance(name, str) or name not in self._loans:
            raise BookError(BOOK_ERROR + ("%s asked for the loan %r, which the book does "
                                          "not hold" % (call, name)))
        return name

    def _when(self, date, call):
        """A reporting date the book covers, or the refusal naming what arrived."""
        if not isinstance(date, str) or date not in self._reporting:
            raise BookError(BOOK_ERROR + ("%s asked for the date %r, which is not one of "
                                          "the book's %d month ends"
                                          % (call, date, len(self._reporting))))
        return date

    def _note(self, call, argument, rows):
        """One line of the ledger: what was asked, for whom, and what it cost."""
        self._log.append({"call": call, "argument": argument, "rows": rows})

    def _count(self, family):
        return len([line for line in self._log
                    if _CALL_STATS.get(line["call"]) == family])

    # -- the portfolio ------------------------------------------------------
    @property
    def loans(self):
        """Every loan record, in estate order — `LOAN_KEYS`, answerable as a call too."""
        self._note("loans", "all", len(self._ids))
        return Rows(self._copy_loan(loan_id) for loan_id in self._ids)

    @property
    def models(self):
        """The three versioned artifacts, in the book's own order."""
        self._note("models", "all", len(self._models))
        return Rows(self._copy_model(model) for model in self._models)

    @property
    def reporting_dates(self):
        """The book's month ends, oldest first — thirty-six of them."""
        self._note("reporting_dates", "all", len(self._reporting))
        return Rows(self._reporting)

    @property
    def log(self):
        """Every ask this book answered, in order — `LOG_KEYS` rows."""
        return tuple(dict(line) for line in self._log)

    def _copy_loan(self, loan_id):
        record = self._loans[loan_id].record
        return LoanRecord((key, record[key]) for key in LOAN_KEYS)

    def _copy_model(self, model):
        return {"name": model["name"], "version": model["version"],
                "as_of": model["as_of"], "grades": dict(model["grades"]),
                "pd_bp": {grade: tuple(series) for grade, series in model["pd_bp"].items()},
                "lgd_bp": dict(model["lgd_bp"]), "ccf_bp": dict(model["ccf_bp"])}

    def loan(self, value):
        """One loan record by id or by record; an unknown one is refused by name."""
        loan_id = self._identify(value, "loan")
        self._note("loan", loan_id, 1)
        return self._copy_loan(loan_id)

    def payments(self, value):
        """The borrower's payments on one loan — `PAYMENT_KEYS` rows, in date order."""
        loan_id = self._identify(value, "payments")
        rows = tuple(dict(row) for row in self._loans[loan_id].payments)
        self._note("payments", loan_id, len(rows))
        return rows

    def events(self, value):
        """The events the bank recorded on one loan — `EVENT_KEYS` rows, in date order."""
        loan_id = self._identify(value, "events")
        rows = self._loans[loan_id].events
        self._note("events", loan_id, len(rows))
        return tuple(dict(row) for row in rows)

    def recoveries(self, value):
        """The recovery rows on one loan — `RECOVERY_KEYS`, costs negative."""
        loan_id = self._identify(value, "recoveries")
        rows = self._loans[loan_id].recoveries
        self._note("recoveries", loan_id, len(rows))
        return tuple(dict(row) for row in rows)

    def recoveries_of(self, value):
        """`recoveries`, under the name the brief for this course uses for it."""
        loan_id = self._identify(value, "recoveries_of")
        rows = self._loans[loan_id].recoveries
        self._note("recoveries_of", loan_id, len(rows))
        return tuple(dict(row) for row in rows)

    def model(self, name, version):
        """One artifact by name and version; an unknown pair is refused by name."""
        found = None
        for model in self._models:
            if model["name"] == name and model["version"] == version:
                found = model
        if found is None:
            raise BookError(BOOK_ERROR + ("the book holds no model %r version %r"
                                          % (name, version)))
        self._note("model", "%s@%s" % (name, version), 1)
        return self._copy_model(found)

    def model_in_force(self, date):
        """The artifact a reporting date is priced with — `None` before the first."""
        found = self._in_force(date)
        self._note("model_in_force", date, 0 if found is None else 1)
        return None if found is None else self._copy_model(found)

    def on_book(self, date):
        """The loans the book is live on at a reporting date, in estate order.

        A loan is live when it has been originated and no write-off is on it at or
        before the date. `status` answers for every (loan, date) pair and is *not* a
        liveness test: this is where derecognition is asked about.
        """
        self._when(date, "on_book")
        live = tuple(loan_id for loan_id in self._ids
                     if self._loans[loan_id].live(date))
        self._note("on_book", date, len(live))
        return live

    # -- the bank's own records ---------------------------------------------
    def schedule(self, value):
        """The bank's own contractual flows for one loan — the answer key for stage 1."""
        loan_id = self._identify(value, "schedule")
        holder = self._loans[loan_id]
        record = {
            "loan": loan_id,
            "flows": tuple({"date": date, "amount_cents": amount}
                           for date, amount in holder.flows),
            "principal_cents": holder.record["principal_cents"],
            "rate_bp": holder.record["rate_bp"],
            "term_months": holder.record["term_months"],
            "first_due": holder.record["first_due"],
            "level_payment_cents": holder.level_payment_cents,
        }
        self._note("schedule", loan_id, len(holder.flows))
        return record

    def grade(self, value, date):
        """The grade the bank records for a loan at a reporting date."""
        loan_id = self._identify(value, "grade")
        self._when(date, "grade")
        answer = self._statuses[loan_id][date]["grade"]
        self._note("grade", "%s@%s" % (loan_id, date), 1)
        return answer

    def status(self, value, date):
        """The bank's own record for a loan at a reporting date — `STATUS_KEYS`."""
        loan_id = self._identify(value, "status")
        self._when(date, "status")
        row = dict(self._statuses[loan_id][date])
        self._note("status", "%s@%s" % (loan_id, date), 1)
        return row

    def defaults(self):
        """Every default the book signalled, in loan order and then by date."""
        rows = []
        for loan_id in self._ids:
            for signal in self._loans[loan_id].signals:
                rows.append({"loan": signal["loan"],
                             "signalled_on": signal["signalled_on"],
                             "triggers": tuple(signal["triggers"]),
                             "cured_on": signal["cured_on"],
                             "probation_until": signal["probation_until"]})
        self._note("defaults", "all", len(rows))
        return tuple(rows)

    def migrations(self, start, end):
        """The grade movements the book recorded between two reporting dates.

        Every loan in the book counts, so a stage that rebuilds the counts from
        `grade(loan, start)` and `grade(loan, end)` agrees exactly; a pair that never
        happened is not a key, and a loan recorded at `"default"` at either end
        speaks for itself.
        """
        self._when(start, "migrations")
        self._when(end, "migrations")
        if start >= end:
            raise BookError(BOOK_ERROR + ("a migration window from %s to %s does not run "
                                          "forwards" % (start, end)))
        counts = {}
        for loan_id in self._ids:
            holder = self._loans[loan_id]
            pair = (holder.grade(start), holder.grade(end))
            counts[pair] = counts.get(pair, 0) + 1
        self._note("migrations", "%s..%s" % (start, end), len(counts))
        return counts

    def observed_default_rate(self, grade, months, start, end):
        """The realised cumulative default rate of a grade's cohort, in basis points.

        The cohort is every loan the book records at `grade` at `start`; a loan
        counts as defaulted when its first signalled default falls inside the
        window `(start, min(end, add_months(start, months))]`, so the horizon is the
        caller's and the observation is the book's. A cohort with no loans answers
        `None` — a rate over nobody is not zero.
        """
        if grade not in rules.GRADES:
            raise BookError(BOOK_ERROR + ("%r is not one of the grades %r"
                                          % (grade, rules.GRADES)))
        _whole(months, "the months")
        if months < 0:
            raise BookError(BOOK_ERROR + ("a horizon of %d months runs backwards"
                                          % (months,)))
        self._when(start, "observed_default_rate")
        self._when(end, "observed_default_rate")
        if start >= end:
            raise BookError(BOOK_ERROR + ("a cohort window from %s to %s does not run "
                                          "forwards" % (start, end)))
        horizon = start if months == 0 else min(end, dates.add_months(start, months))
        cohort = [loan_id for loan_id in self._ids
                  if self._loans[loan_id].grade(start) == grade]
        defaulted = [loan_id for loan_id in cohort
                     if self._loans[loan_id].default_date() is not None
                     and start < self._loans[loan_id].default_date() <= horizon]
        self._note("observed_default_rate", "%s/%d/%s..%s" % (grade, months, start, end),
                   len(cohort))
        if not cohort:
            return None
        return len(defaulted) * rules.DISCOUNT_SCALE // len(cohort)

    def rollforward(self, start, end):
        """The provision's movement between two reporting dates, line by line.

        The banks' own version of §4.8: the opening and the closing totals are
        **recomputed** (never summed from the lines), the nine explanatory lines are
        computed in `LINES` order over the populations the amendment pins, and
        whatever the nine do not explain is reported as `other` rather than
        absorbed — so `difference_cents` is zero and the record is honest about
        being an explanation instead of an identity.
        """
        self._when(start, "rollforward")
        self._when(end, "rollforward")
        if start > end:
            raise BookError(BOOK_ERROR + ("a roll-forward from %s to %s runs backwards"
                                          % (start, end)))
        holders = self._loans
        old, new = self._in_force(start), self._in_force(end)
        live_start = [loan_id for loan_id in self._ids if holders[loan_id].live(start)]
        live_end = [loan_id for loan_id in self._ids if holders[loan_id].live(end)]
        both = [loan_id for loan_id in live_start if holders[loan_id].live(end)]
        fresh = [loan_id for loan_id in live_end if not holders[loan_id].live(start)]
        written = []
        for loan_id in self._ids:
            off = holders[loan_id].write_off
            if off is not None and start < off <= end:
                written.append(loan_id)
        gone = [loan_id for loan_id in live_start
                if not holders[loan_id].live(end) and loan_id not in written]
        opening = sum(self._ecls[loan_id][start] for loan_id in live_start)
        closing = sum(self._ecls[loan_id][end] for loan_id in live_end)

        def weight(loan_id, date, scenario, model, stage):
            return self._ecl_cents(holders[loan_id], date, scenario, model, stage,
                                   self._artifact_exposure(loan_id, date, model))

        def split(parts):
            total, pl = 0, 0
            for loan_id, cents in parts.items():
                total = total + cents
                if holders[loan_id].record["measured_at"] == "amortised-cost":
                    pl = pl + cents
            return total, pl

        lines = []
        lines.append(("derecognitions", split(
            {loan_id: -self._ecls[loan_id][start] for loan_id in gone}),
            "the loans the book was live on at %s and is not live on at %s, and that "
            "were not written off in between" % (start, end)))
        lines.append(("new-business", split(
            {loan_id: self._ecls[loan_id][end] for loan_id in fresh}),
            "the loans first live at %s, at their own provision that day" % (end,)))
        lines.append(("stage-transfers", split(
            {loan_id: weight(loan_id, end, rules.SCENARIOS[0], old,
                             self._stages[loan_id][end])
             - weight(loan_id, end, rules.SCENARIOS[0], old,
                      self._stages[loan_id][start]) for loan_id in both}),
            "the provision at %s under the stage of %s against the stage of %s, on the "
            "model in force at %s" % (end, end, start, start)))
        lines.append(("parameter", split(
            {loan_id: weight(loan_id, end, rules.SCENARIOS[0], new,
                             self._stages[loan_id][end])
             - weight(loan_id, end, rules.SCENARIOS[0], old,
                      self._stages[loan_id][end]) for loan_id in both}),
            "the model's own movement at %s and the stage of %s, in the base scenario"
            % (end, end)))
        lines.append(("scenario", split(
            {loan_id: self._weighted_cents(holders[loan_id], end, new,
                                           self._stages[loan_id][end])
             - weight(loan_id, end, rules.SCENARIOS[0], new,
                      self._stages[loan_id][end]) for loan_id in both}),
            "the scenario weighting's own movement at %s, on the model in force then"
            % (end,)))
        months = _months_between(start, end)
        unwound = {}
        for loan_id in live_start:
            holder = holders[loan_id]
            period_bp = _period_rate(holder.eir_bp, rules.DEFAULT_BASIS)
            for _step in range(months):
                unwound[loan_id] = unwound.get(loan_id, 0) \
                    + self._ecls[loan_id][start] * period_bp // rules.DISCOUNT_SCALE
        lines.append(("unwind", split(unwound),
                      "the passage of time: the opening provision carried at each "
                      "loan's own effective rate for the %d months" % (months,)))
        written_off = {}
        for loan_id in written:
            last = max(date for date in self._reporting
                       if date <= end and holders[loan_id].live(date))
            written_off[loan_id] = -self._ecls[loan_id][last]
        lines.append(("write-offs", split(written_off),
                      "the provisions of the loans written off between %s and %s, gone "
                      "with their balances" % (start, end)))
        collected = {}
        for loan_id in self._ids:
            off = holders[loan_id].write_off
            if off is None or off > start:
                continue
            for row in holders[loan_id].recoveries:
                if start < row["date"] <= end:
                    collected[loan_id] = collected.get(loan_id, 0) + row["amount_cents"]
        lines.append(("recoveries", split(collected),
                      "the flows collected between %s and %s against the stock already "
                      "written off at %s" % (start, end, start)))
        explained = sum(total for _name, (total, _pl), _why in lines)
        residual = closing - (opening + explained)
        lines.append(("other", (residual, residual),
                      "what the nine lines do not explain: the closing total less the "
                      "opening total and every line above, reported rather than absorbed"))
        pl_cents = sum(pl for _name, (_total, pl), _why in lines)
        lines_and_cents = [(name, total) for name, (total, _pl), _why in lines]
        cents_total = sum(total for _name, total in lines_and_cents)
        self._note("rollforward", "%s..%s" % (start, end), len(lines))
        return {
            "start": start, "end": end, "opening_cents": opening,
            "lines": tuple((name, total, why) for name, (total, _pl), why in lines),
            "pl_cents": pl_cents, "oci_cents": cents_total - pl_cents,
            "closing_cents": closing,
            "difference_cents": closing - (opening + cents_total),
        }

    def stats(self):
        """The ledger, recounted: what was asked of this book, by family.

        The six counters are `STAT_KEYS`, each recomputed from `log`. `stats` does
        not log itself, so two recounts of an untouched book answer equal.
        """
        return {family: self._count(family) for family in STAT_KEYS}

    @classmethod
    def build(cls, seed=7):
        """The bank's book for a seed: the estate, its facts, its artifacts, its records.

        The seed moves the borrowers' names and nothing else; the facts the ten
        checks are built on are the estate's. Every record is computed once, here.
        """
        last = LAST_REPORTING_DATE
        first = dates.add_months(last, -(REPORTING_DATES - 1))
        reporting = dates.month_ends(first, last)
        if len(reporting) != REPORTING_DATES:
            raise BookError(BOOK_ERROR + ("%s to %s is %d month ends, not %d"
                                          % (first, last, len(reporting),
                                             REPORTING_DATES)))
        return cls(_facts(seed), reporting)
