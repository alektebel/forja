"""Credit Origination From Scratch — stage 5: The price at origination.

A list of prices is not a number a committee can audit; it is a build-up, and the
build-up is the audit. The bank does not price a loan out of the air: it charges
the money it borrows, the loss it expects to eat, the capital the loan consumes,
the cost of running the desk, and a margin that keeps the doors open — and it can
name each of those to the basis point. This stage rebuilds that build-up for the
estate's own applications and lays the five named legs beside the bank's own
recorded price, so a reader sees not only what was charged but why, and where the
bank's own record sits above or below what the legs explain.

The estate carries no grade. What it carries is the facts the grade comes from —
the scorecard's band per attribute — and the policy carries the weights, the
points, the thresholds, the table that turns a band into a grade, and the price's
own leg tables per grade. So the stage walks the policy's tables against the
estate's bands to name the grade the application is, builds each leg at that
grade — funding and the margin the floor are flat, capital is the grade's own,
and the expected-loss leg is the product of the grade's probability of default
and its loss given default, truncated to the basis point — and answers exactly
what the build-up says. It refuses to price anything the bank did not price: a
declining application carries a grade that prices nothing, so its record is a
refusal naming it, and its banked price of zero is the only zero the stage owns.

The bank's own recorded price, read from the estate's decision, is the anchor the
build-up is laid against. The difference between them is `residual_bp`: the gap
the policy left behind. On this estate the legs re-add to the record on every
application but one — the residual is the data, not a rounding artifact, and the
stage reports it rather than hiding it, fudging a leg to force a match, or
claiming the build-up replaces the bank's price. A price whose legs cannot be
re-added is a price nobody can decompose; a price whose legs re-add but whose
residual is data is a price somebody has to explain.

    PRICE_KEYS                    the seven fields of one price, in order
    PRICE_LEG_NAMES               the five legs, named, in the order they re-add
    PriceError                    the refusal this stage raises
    price(id, book=None)          -> PRICE_KEYS: the price built from its legs
    leg(bp_table, grade)          -> a leg's own basis points at one grade

DESIGN DECISION — why is the price five named legs re-added, not one formula?
Because a number is not a price until its legs are named and the named legs re-add
to it. The policy carries the five legs in a fixed order — funding (flat),
expected loss (computed), capital (per grade), opcost (flat) and margin (flat) —
and the stage answers the legs first and the sum second, with no rounding trick
between them: `price_bp` is the exact sum of the legs the record carries, so any
reader can take the record apart and put it back together. A closed-form price or
a leg dropped into the sum is a price whose legs will not re-add, and a record
whose legs re-add to something else than the bank charged is a price the
committee cannot trace.

DESIGN DECISION — where does the grade come from, if this stage imports no
earlier stage?
From the world, not from a stage. The estate answers the scorecard's band per
attribute, and the policy carries the weights, the points per band and the
thresholds the total clears — the grade is the table's own answer, walked once
here the way the policy states it, named with the grade the policy's own
`GRADE_OF` table assigns the band. Nothing of the scorecard's or the rating's
arithmetic is re-decided: the stage reads the same tables and applies the same
first-clearing-threshold rule, because pricing is held to the grade the facts
name and a pricing stage that fit a grade of its own would be a rating stage in
disguise. The weight table that does not sum to the whole is stage 2's audit; the
band that is walked here is the same one walked there.

DESIGN DECISION — why is the residual the bank's gap and not a reconciliation?
Because the bank's record is the answer key, not the build-up's. The stage builds
its legs from the policy and the facts, sums them, and answers the bank's own
recorded price minus that sum as `residual_bp` — an application whose record sits
above what the legs explain keeps the gap in the record with its sign and its
size, data a reader can question, not an error to eat. Forcing a leg to close the
gap, or flooring the residual at zero, or reporting the residual as the price
itself, all erase the one piece of evidence this stage exists to produce: where
the bank's own price has come apart from what its policy's legs say.

DESIGN DECISION — why does a declined application refuse to price, and why is
that refusal a record-shape exception and not a zero price?
Zero is a price — it is what the margin leg costs a loan the bank gives away —
and the estate's declines carry price 0 in the bank's own record. But an
application the bank declined is not a loan priced at zero: it is one whose grade
prices nothing, and the honest record for a grade that prices nothing is a
refusal that names the application. So `price` refuses every application whose
bank decision carries no price, before any leg is built, and the check holds the
refusal to the estate's own declines — the estate answers a priced grade for
every application the stage may read a price from.

DESIGN DECISION — why does `price` take the book as an argument and build it when
nobody hands it one?
Because the stage reads the world, and the world is the estate's to hand over: a
call that names only the application builds the estate fresh — the estate is a
deterministic build and two builds answer equal — while a caller that already
holds one (the check, and any stage that follows) can pass it and be answered out
of the same counted doors it walks itself. No module-level estate is kept: the
estate's counters move when its doors are opened, and a stage that owned one
would be module-level mutable state wearing a read-only coat.
"""

import cases
import policy

PRICE_KEYS = ("id", "grade", "legs", "price_bp", "residual_bp", "floor", "basis")

PRICE_LEG_NAMES = ("funding", "expected-loss", "capital", "opcost", "margin")

STAGE_ERROR = "stage 5: "


class PriceError(ValueError):
    """The price's own refusal: a grade, a leg or a table it cannot answer."""


def leg(bp_table, grade):
    """One leg's basis points at one grade.

    A flat leg (the policy's `FUNDING_BP`, `OPCOST_BP` and `MARGIN_BP`) is
    echoed whatever the grade, because a flat leg charges nothing by grade; a
    per-grade table is read at the grade, and a grade the table does not carry
    is refused by name. Anything that is neither a count nor such a table is
    refused by name too.
    """
    if isinstance(bp_table, bool) or not isinstance(bp_table, (int, dict)):
        raise PriceError(STAGE_ERROR +
                         ("the leg table %r is a %s, not a count of basis points "
                          "or a table keyed by grade"
                          % (bp_table, type(bp_table).__name__)))
    if isinstance(bp_table, int):
        return bp_table
    if isinstance(grade, bool) or not isinstance(grade, str):
        raise PriceError(STAGE_ERROR +
                         ("the grade %r is a %s, not a text the tables are keyed "
                          "by" % (grade, type(grade).__name__)))
    if grade not in bp_table:
        raise PriceError(STAGE_ERROR +
                         ("the leg table %r carries no %r entry" % (bp_table, grade)))
    value = bp_table[grade]
    if isinstance(value, bool) or not isinstance(value, int):
        raise PriceError(STAGE_ERROR +
                         ("the leg table's %r entry is %r, a %s, not a count of "
                          "basis points" % (grade, value, type(value).__name__)))
    return value


def _grade_of(bands, identity):
    """The grade the application's own bands name, on the policy's own tables.

    The weights, the points per band and the thresholds the total clears are the
    policy's; the bands are the estate's. The total is the sum of every
    attribute's weighted points, truncated per attribute, and the band is the
    first threshold the total clears, walking the policy's descending table —
    which is the scorecard's own answer carried to the grade the policy assigns it.
    """
    if isinstance(bands, bool) or not isinstance(bands, dict):
        raise PriceError(STAGE_ERROR +
                         ("the bands of %r are a %s, not the scorecard's band "
                          "facts" % (identity, type(bands).__name__)))
    total = 0
    for attr in policy.SCORE_ATTRIBUTES:
        if attr not in bands:
            raise PriceError(STAGE_ERROR +
                             ("the bands of %r answer no %r band" % (identity, attr)))
        band = bands[attr]
        if attr not in policy.SCORE_POINTS_BP:
            raise PriceError(STAGE_ERROR +
                             ("the policy carries no %r points" % (attr,)))
        if band not in policy.SCORE_POINTS_BP[attr]:
            raise PriceError(STAGE_ERROR +
                             ("the %r band of %r is %r, a band the policy's points "
                              "table does not answer" % (attr, identity, band)))
        total += policy.SCORE_WEIGHTS_BP[attr] * policy.SCORE_POINTS_BP[attr][band] // 10000
    for threshold, band in policy.SCORE_BANDS:
        if total >= threshold:
            return policy.GRADE_OF[band]
    raise PriceError(STAGE_ERROR +
                     ("the total %d of %r clears no threshold the policy carries"
                      % (total, identity)))


def price(identity, book=None):
    """The application's price: five named legs, their exact sum, and the gap.

    Answers one :data:`PRICE_KEYS` record: the grade the facts name, the five
    legs built at that grade in the policy's own order, `price_bp` their exact
    sum, `residual_bp` the bank's own recorded price minus what the legs built,
    `floor` the policy's margin — the smallest price the bank's own build-up
    carries — and `basis`, the grade the legs were taken from. An application
    whose bank decision carries no price is refused by name.
    """
    if isinstance(identity, bool) or not isinstance(identity, str):
        raise PriceError(STAGE_ERROR +
                         ("the application id %r is a %s, not a text naming an "
                          "application" % (identity, type(identity).__name__)))
    if book is None:
        book = cases.build(cases.BUILD_SEED)
    try:
        bands = book.scorecard_bands(identity)
    except ValueError as refused:
        raise PriceError(STAGE_ERROR +
                         ("the scorecard bands of %r were not handed over: %s"
                          % (identity, refused)))
    try:
        decision = book.decision(identity)
    except ValueError as refused:
        raise PriceError(STAGE_ERROR +
                         ("the bank's own decision of %r was not handed over: %s"
                          % (identity, refused)))
    grade = _grade_of(bands, identity)
    if isinstance(decision, bool) or not isinstance(decision, dict) \
            or "price_bp" not in decision:
        raise PriceError(STAGE_ERROR +
                         ("the bank's own decision of %r carries no price: %r"
                          % (identity, decision)))
    recorded = decision["price_bp"]
    if isinstance(recorded, bool) or not isinstance(recorded, int):
        raise PriceError(STAGE_ERROR +
                         ("the bank's own price of %r is %r, a %s, not a count of "
                          "basis points" % (identity, recorded,
                                            type(recorded).__name__)))
    if recorded == 0:
        raise PriceError(STAGE_ERROR +
                         ("the application %r prices nothing: the bank's own "
                          "decision carries a price of 0, so there is no priced "
                          "grade to build its legs from" % (identity,)))
    if recorded < 0:
        raise PriceError(STAGE_ERROR +
                         ("the bank's own price of %r is below zero: %d"
                          % (identity, recorded)))
    legs = (
        (PRICE_LEG_NAMES[0], leg(policy.FUNDING_BP, grade)),
        (PRICE_LEG_NAMES[1], leg(policy.PD_BP, grade) * leg(policy.LGD_BP, grade)
         // 10000),
        (PRICE_LEG_NAMES[2], leg(policy.CAPITAL_BP, grade)),
        (PRICE_LEG_NAMES[3], leg(policy.OPCOST_BP, grade)),
        (PRICE_LEG_NAMES[4], leg(policy.MARGIN_BP, grade)),
    )
    built = sum(one for _, one in legs)
    return dict(id=identity, grade=grade, legs=legs, price_bp=built,
                residual_bp=recorded - built, floor=policy.MARGIN_BP, basis=grade)
