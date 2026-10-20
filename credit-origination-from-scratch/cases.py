"""cases.py — the applications, the collateral and the bank's own records.

Provided, frozen, and never written by the course. Nothing here prices, scores or
decides — it is the estate the course answers for, and the bank's own records ARE
the answer key every stage is graded against: `decision`, `offer` and `facility`
carry what the bank actually decided, offered and booked, and the ten stages
reproduce those records from the raw facts alone.

What is in it, by design:

* **Ten applications**, `CO-01`..`CO-10`, in one deterministic build. The facts
  are set so the boundaries the contract pins are *landed*, not gestured at:
  `CO-10`'s debt-service ratio sits exactly on `policy.DSR_CAP_BP` — 4500bp,
  kept by the truncation the contract pins — and `CO-05` fails both halves of
  the fit; `CO-06`'s request sits under the collateral cap at its own requested
  amount and `CO-03`'s clears both the amount and the tenor cap, so the styling
  clause has something to say; `CO-04` and `CO-08` fire the two gates,
  `prior-default` first then `bankruptcy`; and an application of every grade A
  through E is priced, with the F's gated — so a `GRADE_OF` row nobody reaches
  does not exist.
* **The declared and the verified income differ** wherever an applicant would
  round their own pay in their favour: the gap between the two is a field the
  fit record reports, and a stage that scores the declared one answers a number
  the bank's own decision does not recognise.
* **An annual obligation** sits in `CO-02` and `CO-10`'s books at a frequency
  the policy names and the stage has to turn into monthly cash: the monthly
  figure of an annual charge is `amount_cents // 12`, and the cent the division
  drops is the applicant's, not the arithmetic's.
* **A booked facility is the bank's own ledger rows**, computed once here by the
  bank's own amortisation — level-payment search included — and handed out as
  the answer stage 10 is held to. The estate is allowed (and honest) to compute
  its *own* ledger; what it does not do is price, score, rate or decide anything
  for the learner: those are the ten stages.

Every accessor is a counted door: `lookups` moves on every call, and the
per-kind counters move only when a record comes back. A refused call — an
unknown id, an offer for a declined application, a facility for a never-booked
one — reaches no record, and `stats()` is where a check proves exactly that.
"""

import dates
import policy

CASE_ERROR = "cases: "

APPLICATION_KEYS = ("id", "purpose", "requested_cents", "term_months",
                    "declared_income_cents", "verified_income_cents",
                    "employment", "employment_years", "self_employed",
                    "arrived_on")

OBLIGATION_KEYS = ("kind", "amount_cents", "frequency")

COLLATERAL_KEYS = ("collateral_id", "kind", "value_cents", "lien_share_bp")

HISTORY_KEYS = ("accounts", "paid_on_time", "arrears_incidents",
                "prior_default", "bankruptcy")

PROJECTION_KEYS = ("year", "revenue_cents", "ebitda_cents", "net_debt_cents",
                   "cash_cents", "capex_cents")

DECISION_KEYS = ("id", "verdict", "role", "reasons", "conditions",
                 "approved_cents", "price_bp", "decided_on", "expires_on")

OFFER_KEYS = ("id", "clauses", "expiry_months", "letter_on")

FACILITY_KEYS = ("id", "booked_cents", "rate_bp", "term_months", "first_due",
                 "basis", "rows")

ROW_KEYS = ("date", "amount_cents")

#: The month a booked facility pays first: the month end after the one the
#: decision was made in. Everything else about the schedule is the contract's.
_FIRST_DUE_LAG = 1

#: The day count a booked facility's rows are dated on: the month ends the
#: calendar produces after the first due date, exactly as M1's own contracts run.
BASIS = "thirty-360"

_BP = 10000
_DAYS_PER_PERIOD = 30
_DAYS_PER_YEAR = 360

BUILD_SEED = 7

CASES_ERROR = CASE_ERROR

PERIODS_PER_YEAR = 12


class CaseError(ValueError):
    """The estate's refusal: an id, an accessor or a shape it cannot answer."""


class _Record(dict):
    """A record that knows its own keys, and refuses to be read out of shape."""

    __slots__ = ()

    def __missing__(self, key):
        raise CaseError(CASE_ERROR + ("this record carries the keys %r, and %r is "
                                      "not one of them" % (tuple(self), key)))


def _need(mapping, keys, what):
    """A record the world cannot build: refuse by name, before any number."""
    if not isinstance(mapping, dict):
        raise CaseError(CASE_ERROR + ("%s is a %s, not a mapping"
                                      % (what, type(mapping).__name__)))
    if tuple(mapping) != keys:
        raise CaseError(CASE_ERROR + ("%s has the keys %r, not %r"
                                      % (what, tuple(mapping), keys)))


def _whole(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CaseError(CASE_ERROR + ("%s is a %s, not a whole number"
                                      % (what, type(value).__name__)))
    return value


def _text(value, what):
    if not isinstance(value, str):
        raise CaseError(CASE_ERROR + ("%s is a %s, not a text"
                                      % (what, type(value).__name__)))
    return value


# --------------------------------------------------------------------------
# The facts. Ten applications, hand-set so the contract's boundaries are places
# a stage can visit, not edges it hopes a random applicant reaches.
# --------------------------------------------------------------------------

_APPLICATIONS = {
    "CO-01": _Record(id="CO-01", purpose="consumer", requested_cents=1200000,
                     term_months=48, declared_income_cents=280000,
                     verified_income_cents=260000, employment="employed",
                     employment_years=6, self_employed=False,
                     arrived_on="2031-01-12"),
    "CO-02": _Record(id="CO-02", purpose="consumer", requested_cents=800000,
                     term_months=36, declared_income_cents=320000,
                     verified_income_cents=240000, employment="employed",
                     employment_years=3, self_employed=False,
                     arrived_on="2031-01-20"),
    "CO-03": _Record(id="CO-03", purpose="sme", requested_cents=18000000,
                     term_months=96, declared_income_cents=3700000,
                     verified_income_cents=3500000, employment="owner",
                     employment_years=8, self_employed=True,
                     arrived_on="2031-01-14"),
    "CO-04": _Record(id="CO-04", purpose="corporate", requested_cents=8000000,
                     term_months=60, declared_income_cents=2250000,
                     verified_income_cents=2100000, employment="contractor",
                     employment_years=1, self_employed=True,
                     arrived_on="2031-01-27"),
    "CO-05": _Record(id="CO-05", purpose="consumer", requested_cents=2000000,
                     term_months=36, declared_income_cents=310000,
                     verified_income_cents=300000, employment="employed",
                     employment_years=4, self_employed=False,
                     arrived_on="2031-02-02"),
    "CO-06": _Record(id="CO-06", purpose="mortgage", requested_cents=42000000,
                     term_months=300, declared_income_cents=850000,
                     verified_income_cents=820000, employment="employed",
                     employment_years=9, self_employed=False,
                     arrived_on="2031-01-31"),
    "CO-07": _Record(id="CO-07", purpose="sme", requested_cents=12000000,
                     term_months=60, declared_income_cents=720000,
                     verified_income_cents=700000, employment="owner",
                     employment_years=11, self_employed=True,
                     arrived_on="2031-03-09"),
    "CO-08": _Record(id="CO-08", purpose="consumer", requested_cents=1500000,
                     term_months=60, declared_income_cents=310000,
                     verified_income_cents=290000, employment="contractor",
                     employment_years=1, self_employed=True,
                     arrived_on="2031-03-17"),
    "CO-09": _Record(id="CO-09", purpose="corporate", requested_cents=24000000,
                     term_months=120, declared_income_cents=940000,
                     verified_income_cents=900000, employment="employed",
                     employment_years=3, self_employed=False,
                     arrived_on="2031-02-11"),
    "CO-10": _Record(id="CO-10", purpose="consumer", requested_cents=600000,
                     term_months=24, declared_income_cents=640000,
                     verified_income_cents=635767, employment="contractor",
                     employment_years=2, self_employed=True,
                     arrived_on="2031-03-23"),
}

# The obligations, stated at the frequency the applicant states them: three
# annual charges in the books (CO-02, CO-05, CO-10) make the monthly turning of
# an annual charge stage 1's arithmetic and not this file's, and the cent the
# turning drops is deliberately in some of them and not others.
_OBLIGATIONS = {
    "CO-01": ({"kind": "rent", "amount_cents": 80000, "frequency": "monthly"},
              {"kind": "club", "amount_cents": 24000, "frequency": "annual"}),
    "CO-02": ({"kind": "card", "amount_cents": 20000, "frequency": "monthly"},
              {"kind": "club", "amount_cents": 24000, "frequency": "annual"}),
    "CO-03": ({"kind": "lease", "amount_cents": 90000, "frequency": "monthly"},),
    "CO-04": (),
    "CO-05": ({"kind": "rent", "amount_cents": 80000, "frequency": "monthly"},
              {"kind": "childcare", "amount_cents": 100000, "frequency": "monthly"},
              {"kind": "club", "amount_cents": 24000, "frequency": "annual"}),
    "CO-06": ({"kind": "service-charge", "amount_cents": 60000,
               "frequency": "monthly"},),
    "CO-07": ({"kind": "lease", "amount_cents": 30000, "frequency": "monthly"},),
    "CO-08": ({"kind": "rent", "amount_cents": 60000, "frequency": "monthly"},
              {"kind": "card", "amount_cents": 8000, "frequency": "monthly"}),
    "CO-09": (),
    "CO-10": ({"kind": "rent", "amount_cents": 180000, "frequency": "monthly"},
              {"kind": "card", "amount_cents": 77287, "frequency": "monthly"},
              {"kind": "club", "amount_cents": 12000, "frequency": "annual"}),
}

# The collateral: what is on offer, and how far along the value the lien reaches.
# `CO-01` lands the advance exactly on the policy cap at its requested amount,
# `CO-06` lands a hair under it, and `CO-09`'s lien pieces share the coverage.
_COLLATERAL = {
    "CO-01": ({"collateral_id": "CO-01-A", "kind": "cash", "value_cents": 1500000,
               "lien_share_bp": 10000},),
    "CO-02": ({"collateral_id": "CO-02-A", "kind": "cash", "value_cents": 1100000,
               "lien_share_bp": 10000},),
    "CO-03": ({"collateral_id": "CO-03-A", "kind": "property",
               "value_cents": 25000000, "lien_share_bp": 8000},
              {"collateral_id": "CO-03-B", "kind": "equipment",
               "value_cents": 6000000, "lien_share_bp": 9000},
              {"collateral_id": "CO-03-C", "kind": "cash",
               "value_cents": 4000000, "lien_share_bp": 10000}),
    "CO-04": ({"collateral_id": "CO-04-A", "kind": "property",
               "value_cents": 12000000, "lien_share_bp": 8500},),
    "CO-05": ({"collateral_id": "CO-05-A", "kind": "none", "value_cents": 0,
               "lien_share_bp": 0},),
    "CO-06": ({"collateral_id": "CO-06-A", "kind": "property",
               "value_cents": 55000000, "lien_share_bp": 8500},),
    "CO-07": ({"collateral_id": "CO-07-A", "kind": "receivables",
               "value_cents": 9000000, "lien_share_bp": 7500},
              {"collateral_id": "CO-07-B", "kind": "cash",
               "value_cents": 10000000, "lien_share_bp": 10000}),
    "CO-08": ({"collateral_id": "CO-08-A", "kind": "cash",
               "value_cents": 1600000, "lien_share_bp": 10000},),
    "CO-09": ({"collateral_id": "CO-09-A", "kind": "equipment",
               "value_cents": 30000000, "lien_share_bp": 9000},
              {"collateral_id": "CO-09-B", "kind": "property",
               "value_cents": 20000000, "lien_share_bp": 10000}),
    "CO-10": ({"collateral_id": "CO-10-A", "kind": "cash", "value_cents": 800000,
               "lien_share_bp": 10000},),
}

# The repayment history as counts and flags — the scorecard's own facts.
_HISTORY = {
    "CO-01": {"accounts": 2, "paid_on_time": 24, "arrears_incidents": 0,
              "prior_default": False, "bankruptcy": False},
    "CO-02": {"accounts": 2, "paid_on_time": 22, "arrears_incidents": 1,
              "prior_default": False, "bankruptcy": False},
    "CO-03": {"accounts": 1, "paid_on_time": 40, "arrears_incidents": 0,
              "prior_default": False, "bankruptcy": False},
    "CO-04": {"accounts": 3, "paid_on_time": 12, "arrears_incidents": 4,
              "prior_default": True, "bankruptcy": False},
    "CO-05": {"accounts": 1, "paid_on_time": 18, "arrears_incidents": 0,
              "prior_default": False, "bankruptcy": False},
    "CO-06": {"accounts": 2, "paid_on_time": 60, "arrears_incidents": 0,
              "prior_default": False, "bankruptcy": False},
    "CO-07": {"accounts": 2, "paid_on_time": 30, "arrears_incidents": 0,
              "prior_default": False, "bankruptcy": False},
    "CO-08": {"accounts": 1, "paid_on_time": 8, "arrears_incidents": 2,
              "prior_default": False, "bankruptcy": True},
    "CO-09": {"accounts": 4, "paid_on_time": 55, "arrears_incidents": 1,
              "prior_default": False, "bankruptcy": False},
    "CO-10": {"accounts": 1, "paid_on_time": 14, "arrears_incidents": 1,
              "prior_default": False, "bankruptcy": False},
}

# The borrower's own projections — the covenants' ground. Only an sme or a
# corporate carries one: a consumer and a mortgage promise nothing of this kind.
_PROJECTIONS = {
    "CO-03": ({"year": 1, "revenue_cents": 4200000000, "ebitda_cents": 630000000,
               "net_debt_cents": 2140000000, "cash_cents": 340000000,
               "capex_cents": 150000000},
              {"year": 2, "revenue_cents": 4400000000, "ebitda_cents": 660000000,
               "net_debt_cents": 2080000000, "cash_cents": 360000000,
               "capex_cents": 150000000},
              {"year": 3, "revenue_cents": 4590000000, "ebitda_cents": 590000000,
               "net_debt_cents": 2100000000, "cash_cents": 220000000,
               "capex_cents": 140000000},
              {"year": 4, "revenue_cents": 4720000000, "ebitda_cents": 640000000,
               "net_debt_cents": 1960000000, "cash_cents": 380000000,
               "capex_cents": 150000000},
              {"year": 5, "revenue_cents": 4860000000, "ebitda_cents": 670000000,
               "net_debt_cents": 1890000000, "cash_cents": 410000000,
               "capex_cents": 160000000}),
    "CO-07": ({"year": 1, "revenue_cents": 1800000000, "ebitda_cents": 390000000,
               "net_debt_cents": 1150000000, "cash_cents": 320000000,
               "capex_cents": 80000000},
              {"year": 2, "revenue_cents": 1890000000, "ebitda_cents": 420000000,
               "net_debt_cents": 1080000000, "cash_cents": 240000000,
               "capex_cents": 90000000},
              {"year": 3, "revenue_cents": 1970000000, "ebitda_cents": 400000000,
               "net_debt_cents": 1020000000, "cash_cents": 350000000,
               "capex_cents": 90000000},
              {"year": 4, "revenue_cents": 2060000000, "ebitda_cents": 440000000,
               "net_debt_cents": 940000000, "cash_cents": 400000000,
               "capex_cents": 100000000},
              {"year": 5, "revenue_cents": 2150000000, "ebitda_cents": 460000000,
               "net_debt_cents": 860000000, "cash_cents": 440000000,
               "capex_cents": 100000000}),
    "CO-09": ({"year": 1, "revenue_cents": 6200000000, "ebitda_cents": 510000000,
               "net_debt_cents": 1540000000, "cash_cents": 360000000,
               "capex_cents": 210000000},
              {"year": 2, "revenue_cents": 6490000000, "ebitda_cents": 540000000,
               "net_debt_cents": 1470000000, "cash_cents": 390000000,
               "capex_cents": 220000000},
              {"year": 3, "revenue_cents": 6680000000, "ebitda_cents": 560000000,
               "net_debt_cents": 1390000000, "cash_cents": 420000000,
               "capex_cents": 230000000},
              {"year": 4, "revenue_cents": 6980000000, "ebitda_cents": 600000000,
               "net_debt_cents": 1300000000, "cash_cents": 450000000,
               "capex_cents": 240000000},
              {"year": 5, "revenue_cents": 7240000000, "ebitda_cents": 630000000,
               "net_debt_cents": 1210000000, "cash_cents": 490000000,
               "capex_cents": 250000000}),
}

# The scorecard's own facts: the band each attribute answers, keyed by the
# policy's own attribute names and band vocabularies.
_BANDS = {
    "CO-01": {"dsr": "low", "stability": "long", "history": "clean",
              "collateral": "strong"},
    "CO-02": {"dsr": "low", "stability": "settled", "history": "spotted",
              "collateral": "adequate"},
    "CO-03": {"dsr": "mid", "stability": "settled", "history": "clean",
              "collateral": "weak"},
    "CO-04": {"dsr": "high", "stability": "short", "history": "impaired",
              "collateral": "weak"},
    "CO-05": {"dsr": "high", "stability": "settled", "history": "clean",
              "collateral": "strong"},
    "CO-06": {"dsr": "low", "stability": "long", "history": "clean",
              "collateral": "strong"},
    "CO-07": {"dsr": "mid", "stability": "long", "history": "clean",
              "collateral": "strong"},
    "CO-08": {"dsr": "high", "stability": "short", "history": "impaired",
              "collateral": "weak"},
    "CO-09": {"dsr": "mid", "stability": "settled", "history": "spotted",
              "collateral": "adequate"},
    "CO-10": {"dsr": "high", "stability": "short", "history": "spotted",
              "collateral": "adequate"},
}

# The bank's own decisions — the answer key stages 8, 9 and 10 are held to. A
# decline carries the legs that fired, in `policy.REASONS` order and nothing
# more: the reasons the bank's own record names are the ones the learner's
# record has to name, and an extra reason is as much an error as a missing one.
_DECISIONS = {
    "CO-01": {"verdict": "approve", "role": "underwriter",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": (), "approved_cents": 1200000, "price_bp": 425,
              "decided_on": "2031-02-15", "expires_on": "2031-03-15"},
    "CO-02": {"verdict": "approve", "role": "underwriter",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": (), "approved_cents": 800000, "price_bp": 452,
              "decided_on": "2031-06-30", "expires_on": "2031-07-31"},
    "CO-03": {"verdict": "counter", "role": "committee",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": ("styled", "covenant-liquidity-year-3"),
              "approved_cents": 15000000, "price_bp": 520,
              "decided_on": "2031-01-31", "expires_on": "2031-02-28"},
    "CO-04": {"verdict": "decline", "role": "underwriter",
              "reasons": ("rating", "gate"), "conditions": (),
              "approved_cents": 0, "price_bp": 0,
              "decided_on": "2031-02-03", "expires_on": ""},
    "CO-05": {"verdict": "decline", "role": "underwriter",
              "reasons": ("affordability", "collateral"), "conditions": (),
              "approved_cents": 0, "price_bp": 0,
              "decided_on": "2031-05-19", "expires_on": ""},
    "CO-06": {"verdict": "counter", "role": "committee",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": ("styled",), "approved_cents": 40000000,
              "price_bp": 425, "decided_on": "2031-02-20",
              "expires_on": "2031-03-20"},
    "CO-07": {"verdict": "approve", "role": "committee",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": ("covenant-liquidity-year-2",),
              "approved_cents": 12000000, "price_bp": 425,
              "decided_on": "2031-04-12", "expires_on": "2031-05-12"},
    "CO-08": {"verdict": "decline", "role": "underwriter",
              "reasons": ("collateral", "rating", "gate"), "conditions": (),
              "approved_cents": 0, "price_bp": 0,
              "decided_on": "2031-07-21", "expires_on": ""},
    "CO-09": {"verdict": "approve", "role": "committee",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": (), "approved_cents": 24000000, "price_bp": 750,
              "decided_on": "2031-03-05", "expires_on": "2031-04-05"},
    "CO-10": {"verdict": "approve", "role": "underwriter",
              "reasons": ("affordability", "scorecard", "collateral", "rating",
                          "limit"),
              "conditions": (), "approved_cents": 600000, "price_bp": 1470,
              "decided_on": "2031-05-28", "expires_on": "2031-06-28"},
}

# The letters: an approved or counter application has one, a decline has none,
# and the accessors refuse by name for an application whose book does not carry
# the record asked for.
_OFFERS = {
    "CO-01": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-02-15"},
    "CO-02": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-06-30"},
    "CO-03": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-01-31"},
    "CO-06": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-02-20"},
    "CO-07": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-04-12"},
    "CO-09": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-03-05"},
    "CO-10": {"clauses": policy.OFFER_CLAUSES, "expiry_months": 1,
              "letter_on": "2031-05-28"},
}

# The booked facilities: what the contract becomes. The rows are computed once,
# below, by the bank's own amortisation — the very arithmetic stage 1 owns and
# stage 10 must reproduce — and are handed out read-only.
_FACILITIES = {
    "CO-01": {"amount_cents": 1200000, "rate_bp": 425, "term_months": 48,
              "decided_on": "2031-02-15"},
    "CO-02": {"amount_cents": 800000, "rate_bp": 452, "term_months": 36,
              "decided_on": "2031-06-30"},
    "CO-03": {"amount_cents": 15000000, "rate_bp": 520, "term_months": 84,
              "decided_on": "2031-01-31"},
    "CO-06": {"amount_cents": 40000000, "rate_bp": 425, "term_months": 300,
              "decided_on": "2031-02-20"},
    "CO-07": {"amount_cents": 12000000, "rate_bp": 425, "term_months": 60,
              "decided_on": "2031-04-12"},
    "CO-09": {"amount_cents": 24000000, "rate_bp": 750, "term_months": 120,
              "decided_on": "2031-03-05"},
    "CO-10": {"amount_cents": 600000, "rate_bp": 1470, "term_months": 24,
              "decided_on": "2031-05-28"},
}


def _period_bp(rate_bp):
    """The price per monthly period: a month is thirty days, the bank's own."""
    return rate_bp * _DAYS_PER_PERIOD // _DAYS_PER_YEAR


def _level_payment(principal_cents, rate_bp, term_months):
    """The smallest whole-cent payment whose amortisation clears the loan.

    Searched, not solved, for the same reason stage 1's is: the balance is
    truncated at every step, so the instalment that clears it is the smallest
    integer one, and the walk the bank booked is the walk a reader with a pencil
    reproduces.
    """
    period = _period_bp(rate_bp)

    def walk(payment):
        balance = principal_cents
        for _ in range(term_months):
            balance -= payment - balance * period // _BP
        return balance <= 0

    low = max(1, principal_cents // term_months)
    high = principal_cents * 2 + _BP
    while low < high:
        middle = (low + high) // 2
        if walk(middle):
            high = middle
        else:
            low = middle + 1
    return low


def _booked(facility):
    """The facility's own ledger rows, dated on the month ends after first due."""
    payment = _level_payment(facility["amount_cents"], facility["rate_bp"],
                             facility["term_months"])
    period = _period_bp(facility["rate_bp"])
    first = dates.month_end(dates.add_months(facility["decided_on"],
                                             _FIRST_DUE_LAG))
    balance, rows = facility["amount_cents"], []
    for index in range(facility["term_months"]):
        interest = balance * period // _BP
        amount = payment if index < facility["term_months"] - 1 else balance + interest
        rows.append({"date": dates.add_months(first, index),
                     "amount_cents": amount})
        balance -= amount - interest
    if balance != 0:
        raise CaseError(CASE_ERROR + ("%r's own schedule closes at %d cents, "
                                      "not zero" % (facility["amount_cents"],
                                                    balance)))
    return rows


_ROW_BOOKS = {name: _booked(facility)
              for name, facility in sorted(_FACILITIES.items())}

_LEDGER_KINDS = ("applications", "obligations", "collateral", "history",
                 "projections", "scorecard_bands", "decisions", "offers",
                 "facilities")


class Cases:
    """The estate, as ten counted doors.

    Built fresh by :func:`build` on every call — no module-level state, two
    builds answer equal and read apart. Every accessor answers a frozen record
    (never a mutable reference into the facts) and moves its own counter; a
    refusal moves `lookups` and nothing else, so a check can prove a refused
    call reached no record.
    """

    __slots__ = ("_doors", "_seed")

    def __init__(self, seed):
        _whole(seed, "the build seed")
        self._seed = seed
        self._doors = {kind: 0 for kind in _LEDGER_KINDS}
        self._doors["lookups"] = 0

    @property
    def seed(self):
        """The seed the estate was built with — carried, never used."""
        return self._seed

    def _door(self, kind, identity):
        """One counted step: the door moves before the record is answered."""
        self._doors["lookups"] += 1

    def _identify(self, identity):
        _text(identity, "the application id")
        if identity not in _APPLICATIONS:
            raise CaseError(CASE_ERROR + ("%r is not an application this book "
                                          "holds" % (identity,)))

    def names(self):
        """Every application id the book holds, in the book's own order."""
        self._door("applications", None)
        return tuple(sorted(_APPLICATIONS))

    def application(self, identity):
        """The applicant's own facts, as the application states them."""
        self._door("applications", identity)
        self._identify(identity)
        self._doors["applications"] += 1
        return _Record(_APPLICATIONS[identity])

    def obligations(self, identity):
        """The obligations, stated at the frequency the applicant stated them."""
        self._door("obligations", identity)
        self._identify(identity)
        self._doors["obligations"] += 1
        return tuple(_Record(row) for row in _OBLIGATIONS[identity])

    def collateral(self, identity):
        """The collateral offered, and how far along it the lien reaches."""
        self._door("collateral", identity)
        self._identify(identity)
        self._doors["collateral"] += 1
        return tuple(_Record(row) for row in _COLLATERAL[identity])

    def history(self, identity):
        """The repayment history, as counts and flags."""
        self._door("history", identity)
        self._identify(identity)
        self._doors["history"] += 1
        return _Record(_HISTORY[identity])

    def projections(self, identity):
        """The borrower's own projections, one record per year, in order."""
        self._door("projections", identity)
        self._identify(identity)
        self._doors["projections"] += 1
        rows = _PROJECTIONS.get(identity, ())
        return tuple(_Record(row) for row in rows)

    def scorecard_bands(self, identity):
        """The band the estate answers for each scorecard attribute."""
        self._door("scorecard_bands", identity)
        self._identify(identity)
        self._doors["scorecard_bands"] += 1
        return dict(_BANDS[identity])

    def decision(self, identity):
        """The bank's own decision — the answer key stage 8 is held to."""
        self._door("decisions", identity)
        self._identify(identity)
        self._doors["decisions"] += 1
        record = _Record(dict(id=identity, **_DECISIONS[identity]))
        _need(record, DECISION_KEYS, "the decision of %r" % (identity,))
        return record

    def offer(self, identity):
        """The bank's own letter, or the refusal for an application without one."""
        self._door("offers", identity)
        self._identify(identity)
        if identity not in _OFFERS:
            raise CaseError(CASE_ERROR + ("%r carries no offer: the book does "
                                          "not hold one" % (identity,)))
        self._doors["offers"] += 1
        record = _Record(dict(id=identity, **_OFFERS[identity]))
        _need(record, OFFER_KEYS, "the offer of %r" % (identity,))
        return record

    def facility(self, identity):
        """The bank's own booked contract, or the refusal for an unbooked one."""
        self._door("facilities", identity)
        self._identify(identity)
        if identity not in _FACILITIES:
            raise CaseError(CASE_ERROR + ("%r carries no booked facility: the "
                                          "book does not hold one" % (identity,)))
        self._doors["facilities"] += 1
        facility = _FACILITIES[identity]
        record = _Record(
            id=identity, booked_cents=facility["amount_cents"],
            rate_bp=facility["rate_bp"], term_months=facility["term_months"],
            first_due=dates.month_end(
                dates.add_months(facility["decided_on"], _FIRST_DUE_LAG)),
            basis=BASIS,
            rows=tuple(_Record(date=row["date"],
                               amount_cents=row["amount_cents"])
                       for row in _ROW_BOOKS[identity]))
        _need(record, FACILITY_KEYS, "the facility of %r" % (identity,))
        for row in record["rows"]:
            _need(row, ROW_KEYS, "a row of the facility of %r" % (identity,))
        return record

    def stats(self):
        """The ledger of what was asked, as counts."""
        return dict(self._doors)


def build(seed=BUILD_SEED):
    """The estate, built fresh: ten applications and their counted doors.

    `build()` twice answers equal; a seed is carried and never draws — the
    estate is fixed data, and the seed only names the hand that pinned it.
    """
    return Cases(seed)

