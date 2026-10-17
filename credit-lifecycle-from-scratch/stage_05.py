"""Credit Lifecycle From Scratch — stage 5: The drawn balance, the undrawn limit and the exposure at default.

A loan's loss is not computed on what the borrower owes at origination: it is computed
on what the bank is exposed to when the borrower stops paying, and for a committed
facility that exposure is larger than the balance. Part of the limit has not been drawn
yet, and a borrower who is about to default draws the rest of it first — which is the
one fact about default no amortisation schedule can see. This stage measures that part,
turns it into a credit conversion factor out of the bank's own defaults, and answers the
exposure at default every later stage provisions against.

The drawn amount is the stage's first reading, and it is a reading of the *payments*,
not of the contract: the schedule's instalments the borrower has actually paid up to the
date, less anything prepaid, and never negative. A loan in arrears has drawn less than
its plan, a loan that paid ahead has drawn more, and the difference between the two is
what the undrawn limit is measured against: the part of the limit the borrower has
already used without the schedule expecting it. Nothing is assumed about the facility —
the limit is a number the application carries, and where there is no limit there is
nothing to convert.

The factor itself is not a policy number and not a vendor's table: it is estimated from
the book's own defaulted loans of a segment, as the ratio of what those loans drew
between origination and default over what was undrawn at origination. And it is one
ratio, not an average of ratios: the drawdowns are summed, the undrawn amounts are
summed, and the division happens once, because the ratio of two sums is the ratio the
bank's book exhibits and the mean of per-loan ratios is a different, biased number. A
segment whose defaults have all been observed answers its own ratio, clamped to the
policy's floor and cap; a segment that has never defaulted answers the floor, which is
the policy's own statement about a conversion factor nobody has measured yet.

The exposure is then the pinned sum: what is drawn, plus the undrawn part converted at
the segment's own factor, truncated once. `ead_at_default` is the same number at the
date the default was signalled — the date the loss is measured from — and a loan that
never defaulted has no exposure at default to answer: the stage refuses rather than
invent one.

    EAD_KEYS        the five fields of an exposure, in order
    CCF_FLOOR_BP    the policy's floor for a conversion factor, in basis points
    CCF_CAP_BP      the policy's cap for a conversion factor, in basis points
    ccf(book, segment)      -> the segment's conversion factor, in basis points
    ead(book, loan, date)   -> EAD_KEYS at a date
    ead_at_default(book, loan) -> the exposure at the loan's default date

DESIGN DECISION — why is the conversion factor aggregate rather than an average?
Because a bank's factor is a property of the segment and not of a loan, and a mean of
per-loan ratios is a different number from the ratio of the segment's sums whenever the
loans are not the same size: a small loan that drew a great deal would weigh as much as
a large one that drew a little. The contract pins the aggregate form — sum the
drawdowns, sum the undrawn amounts at origination, divide once — so the factor answers
"of the limit this segment's defaulters had available, how much did they use", which is
the question a capital number needs, and so two calls of the same segment agree exactly.

DESIGN DECISION — why is the factor clamped rather than reported raw?
Because the ratio is estimated from a handful of defaults and not from a law of nature:
a loan whose undrawn limit is small next to what it drew between origination and default
can push the raw ratio over 100%, and a segment whose defaults repaid more than they
drew — a prepayment larger than the instalments paid in between — can push it below
zero. Neither is a conversion factor a bank may book. So the policy's floor and cap are
applied to the *result*, after the division, which is the only order that keeps a
segment with a negative raw ratio from booking a negative exposure; and a segment with
no defaults at all answers the floor directly, because the honest answer to "what did
your defaulters convert" is "we have not observed one". A segment whose defaults had
nothing undrawn at origination to convert answers the floor for the same reason and
not a division by zero: there is no limit to convert, so there is nothing to book.

DESIGN DECISION — why is the drawn amount read off the payments and not off the book?
Because the payment rows are the only record of what actually happened: the schedule
says what was expected and `book.status` says what the bank booked, and a stage that
read either of those back would be reproducing an answer rather than computing one. So
the drawn amount sums the instalment payments up to the date, subtracts the prepayments
up to the date, and floors at zero; the schedule is consulted only for its *plan* — the
instalments it expected by that date — so that the part of the limit drawn above plan is
the difference between what the borrower did and what the contract said. A loan whose
payments arrive on schedule therefore has nothing above its plan, and its whole limit is
undrawn.

DESIGN DECISION — why does the exposure never refuse a date, but refuse a healthy loan?
Because a date is not a claim about the loan: the exposure at any date is a function of
the payments up to it, the plan up to it and the loan's own limit, and the records cover
every date from origination onwards whether or not the bank reports on it — the
origination date itself is a date no reporting calendar holds, and the factor needs the
drawn amount there. A default date is a different matter: it is a fact the book either
records or does not, and a loan that never defaulted has no exposure at default, so
`ead_at_default` refuses with `BookError` naming the loan instead of answering the
exposure at the last reporting date and calling it a default.

DESIGN DECISION — why does the stage re-export the policy's floor and cap?
Because the numbers a factor is clamped to are the bank's policy and not this stage's
invention, and the surface a reader meets should name them where they are used. The
constants are the policy's own (`rules.CCF_FLOOR_BP` and `rules.CCF_CAP_BP`) read once
at import, so a reader can see the clamp in the code without opening the rulebook, and a
policy that moves its floor moves this stage's answer with it rather than silently
disagreeing with it.

TODO: implement `ccf`, `ead` and `ead_at_default` in this file: the aggregate factor a
segment's own defaults exhibit, the exposure at a date as the drawn amount plus the
converted undrawn part, and the same number at the date a default was signalled.
"""

import dates
import rules

EAD_KEYS = ("loan", "date", "drawn_cents", "undrawn_cents", "ccf_bp", "ead_cents")

CCF_FLOOR_BP = rules.CCF_FLOOR_BP

CCF_CAP_BP = rules.CCF_CAP_BP


def ccf(book, segment):
    """The credit conversion factor the book's own defaults of `segment` exhibit.

    The factor is one ratio and not an average: over that segment's defaulted loans,
    the drawdown between origination and default is summed, the amount undrawn at
    origination is summed, and the division happens once. The result is truncated and
    clamped to `CCF_FLOOR_BP`..`CCF_CAP_BP`; a segment with no defaults — or with
    nothing undrawn at origination to convert — answers the policy's floor.

    A segment that is not one of `rules.SEGMENTS` raises `BookError` naming it.
    """
    raise NotImplementedError("stage 5: implement ccf()")


def ead(book, loan, date):
    """The exposure at `date`: what is drawn, plus the undrawn limit converted.

    `drawn_cents` is the schedule's instalments paid up to `date` less any prepayment,
    floored at zero; `undrawn_cents` is the loan's limit less the part of that drawn
    amount which sits above the schedule's own plan for `date`, also floored at zero;
    `ead_cents` is `drawn_cents + undrawn_cents * ccf_bp // 10000`, truncated once, and
    `ccf_bp` is the loan's segment's own factor. A date whose shape is not an ISO date
    raises `DateError` naming it, and a loan the book does not hold raises `BookError`
    naming it.
    """
    raise NotImplementedError("stage 5: implement ead()")


def ead_at_default(book, loan):
    """The exposure at the loan's default date, as `ead` answers it there.

    A loan the book does not hold raises `BookError` naming it, and a loan that never
    defaulted raises `BookError` naming it too: an exposure at default is a fact about
    a default, and the stage refuses to invent one for a loan that has not had any.
    """
    raise NotImplementedError("stage 5: implement ead_at_default()")
