"""policy.py — the origination rulebook, as data.

Provided, frozen, and never written by the course. Nothing here prices a loan,
scores an applicant or decided anything — it is somebody else's *decision*, and the
whole course is held to it. The policy's own tables are what make the ten stages
answerable at all: the affordability halves, the scorecard's weights and points and
bands, the collateral haircuts and advance cap, the gates no score passes, the
price's legs grade by grade, the purpose limits, the committed share, the covenants
and their floors, the committee threshold and the letter's clauses.

Three tables deserve a word before they are used:

* `SCORE_WEIGHTS_BP` sums to exactly `10000` — an application's score is a
  weighted table, and a weight table that does not sum to the whole is a score
  nobody can audit. A stage that never checks the sum has accepted a card the
  committee would bounce.
* `HAIRCUT_BP` is **the same table M1 carries** (the bank has one haircut policy,
  not one per report), and `ADVANCE_CAP_BP` is the cap the advance rate is held
  to *after* the haircut — a request a basis point over it is styled, not waved
  through.
* The price's legs are **five named legs, in order** — funding, expected loss,
  capital, opcost, margin — and the recorded price is their exact sum. A price
  whose legs cannot be re-added to it is a price nobody can decompose, which is
  the opposite of the lesson.

`scale_bp` is the one function here: `10000 * a // b`, truncated, because the
zähler/count structure every ratio in this course takes — a ratio in basis points
is a numerator, a denominator and a policy — is one line, and a house that
re-derives it per stage derives it differently each time.
"""

POLICY_VERSION = "credit-origination-v1"

PURPOSES = ("consumer", "mortgage", "sme", "corporate")

#: An obligation is stated at the frequency the applicant states it: a monthly
#: rent and an annual club fee are both obligations, and the course turns the
#: annual one into monthly cash — the turning is stage 1's, not this table's.
FREQUENCIES = ("monthly", "annual")

COLLATERAL_KINDS = ("cash", "receivables", "property", "equipment", "none")

LIENS = ("pledged", "first-lien", "mortgage", "unsecured")

#: M1's own alphabet, without `"default"`: a default is what a *booked* loan
#: becomes, and an origination grade is chosen before anything is booked.
GRADES = ("A", "B", "C", "D", "E", "F")

DECISIONS = ("approve", "counter", "decline")

ROLES = ("underwriter", "committee")

#: The legs a decision cites, in the order the reasons line is written in.
REASONS = ("affordability", "scorecard", "collateral", "rating", "limit",
           "covenant", "gate")

#: The affordability test is two halves, and both must pass: the debt-service
#: ratio — payment plus obligations over verified income — may not clear the
#: cap, and the leftover — income minus all debt service — may not fall below
#: the floor. A high earner with a thin leftover fails the second half, an
#: applicant whose ratio is a hair over fails the first, and the estate holds
#: one of each.
DSR_CAP_BP = 4500

AFFORD_FLOOR_CENTS = 100000

#: What each month-30 period charges, per purpose, at the terms the *applicant
#: proposed* — stage 1 prices the fit at these, stage 5 may do better.
PROPOSED_RATE_BP = {"consumer": 1050, "mortgage": 480, "sme": 890,
                    "corporate": 780}

#: The scorecard: four attributes, weights that sum to the whole, and a points
#: table per attribute over the band texts the estate answers.
SCORE_ATTRIBUTES = ("dsr", "stability", "history", "collateral")

SCORE_WEIGHTS_BP = {"dsr": 3500, "stability": 1500, "history": 3000,
                    "collateral": 2000}

SCORE_POINTS_BP = {
    "dsr": {"low": 10000, "mid": 5000, "high": 1000},
    "stability": {"long": 10000, "settled": 6000, "short": 2000},
    "history": {"clean": 10000, "spotted": 4000, "impaired": 0},
    "collateral": {"strong": 10000, "adequate": 7000, "weak": 2000},
}

#: The scorecard's own bands, *descending threshold order*; a total below the
#: last threshold reads the last band, and a band is never an error.
SCORE_BANDS = ((7700, "A"), (6800, "B"), (5600, "C"), (4400, "D"),
               (2500, "E"), (0, "F"))

#: The rating the bank assigns: the table, not a limit. Identity here by design
#: — and the stage uses the table whatever its entries are.
GRADE_OF = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F"}

#: The gates: a gate is a decline no score passes, and the gates answer in this
#: order. The estate's own history facts (`prior_default`, `bankruptcy`) are
#: what fire them.
GATES = ("prior-default", "bankruptcy")

#: The collateral: the bank has one haircut table (M1's), and the advance the
#: loan may take against it is capped after the haircut.
HAIRCUT_BP = {"cash": 0, "receivables": 3000, "property": 2000,
              "equipment": 5000, "none": 10000}

ADVANCE_CAP_BP = 8000

#: The price's legs. Funding, opcost and margin are flat; capital and the loss
#: the expected one is computed from are grade tables. The order is the
#: corridor the record reads.
FUNDING_BP = 220

OPCOST_BP = 25

MARGIN_BP = 150

CAPITAL_BP = {"A": 20, "B": 25, "C": 35, "D": 55, "E": 80, "F": 120}

PD_BP = {"A": 30, "B": 80, "C": 200, "D": 600, "E": 1800, "F": 10000}

LGD_BP = {"A": 3500, "B": 4000, "C": 4500, "D": 5000, "E": 5500, "F": 10000}

#: The limit structure: per-purpose caps on amount and term, and the share of
#: the approved amount the bank commits.
PURPOSE_MAX_CENTS = {"consumer": 2000000, "mortgage": 40000000,
                     "sme": 15000000, "corporate": 60000000}

PURPOSE_MAX_MONTHS = {"consumer": 60, "mortgage": 300, "sme": 84,
                      "corporate": 120}

COMMITTED_BP = 8000

#: The covenants: `(covenant name, kind, floor)` per purpose, in policy order.
#: A `max-leverage` covenant reads its measure the tall way (net debt over
#: EBITDA, in bp) and breaches over its floor; a `min-dscr` and a `min-cash`
#: covenant breach under theirs. The floor of a `min-cash` covenant is *cents*;
#: the others are basis points.
COVENANTS = {
    "sme": (("leverage", "max-leverage", 40000),
            ("service", "min-dscr", 12000),
            ("liquidity", "min-cash", 300000000)),
    "corporate": (("leverage", "max-leverage", 35000),
                  ("service", "min-dscr", 10000)),
    "consumer": (),
    "mortgage": (),
}

#: Approved amounts from here up need the committee's role; below it the
#: underwriter owns the number.
COMMITTEE_CENTS = 5000000

#: The letter: one month after the decision, clamped by the calendar, and the
#: clause order the letter states itself in.
OFFER_EXPIRY_MONTHS = 1

OFFER_CLAUSES = ("commitment", "pricing", "term", "security", "covenants",
                 "expiry")

POLICY_ERROR = "policy: "

_BP = 10000


class PolicyError(ValueError):
    """The rulebook's refusal: a shape the policy does not answer for."""


def scale_bp(numerator, denominator):
    """The ratio of two whole numbers, in basis points, truncated."""
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise PolicyError(POLICY_ERROR + ("the numerator %r is a %s, not a whole "
                                          "number" % (numerator,
                                                      type(numerator).__name__)))
    if isinstance(denominator, bool) or not isinstance(denominator, int):
        raise PolicyError(POLICY_ERROR + ("the denominator %r is a %s, not a whole "
                                          "number" % (denominator,
                                                      type(denominator).__name__)))
    if denominator <= 0:
        raise PolicyError(POLICY_ERROR + ("the denominator %d is not a positive "
                                          "number" % (denominator,)))
    return numerator * _BP // denominator
