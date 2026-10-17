"""Credit Lifecycle From Scratch — stage 2: The bucket, the materiality threshold and the new definition of default.

A loan does not go bad by a label: it goes bad by an arithmetic the supervisor can
reproduce. So this stage answers four questions about one loan and one date — how many
days past due it is, which delinquency bucket that puts it in, what makes it a default,
and when a default that was signalled actually ended — and every one of them is a
reading of the book's own facts rather than an opinion about the borrower.

The days are counted from the oldest instalment the money received has not covered. An
instalment payment is booked against the due it names, a due is uncovered while the
payments booked against it on or before the date do not cover it, and the oldest due
still uncovered is the one the days run from. That is the whole of days past due, and it
is why a partial payment moves the count by nothing until it clears a whole instalment,
while an overpayment on one due does not reach forward to cover the next.

The materiality threshold is the policy's own two-part test, and both halves have to
hold before arrears reach the days count at all: at least `MATERIALITY_ABSOLUTE_CENTS`
and at least `MATERIALITY_RELATIVE_BP` of the loan's exposure. The relative half is
measured against the drawn balance — the instalments the borrower has paid, less what
was prepaid — because that is the exposure this stage can see without stage 5's
undrawn limit, and because a threshold that used a denominator nobody had computed
would be a threshold nobody could reproduce. Arrears below either half are recorded as
arrears and forgiven of their days: `material` is the verdict, and it says which case it
was.

A default is not a bucket; it is a set of triggers. The 90-days-past-due backstop is one
of them, and the policy's flags — forbearance, distressed restructuring, cross-default,
bankruptcy — are the rest; they are named in `UTP_FLAGS` order, so the same loan answers
the same tuple however its events happen to be filed. A flag stands until a cure clears
it, and a cure only clears anything when it lands at or after the probation the policy
imposes on the default it would end: a default must survive `CURE_MONTHS` months before
its cure counts, and a cure that arrives earlier is a no-op, not an early exit.

    BUCKET_KEYS      the seven fields of a bucket record, in order
    DEFAULT_KEYS     the five fields of a signalled default, in order
    BUCKETS          the delinquency buckets a bucket record can name
    UTP_FLAGS        the policy's own flags, in the order a trigger tuple names them
    dpd(book, loan, date)                 -> the materially unpaid days
    bucket(book, loan, date)              -> BUCKET_KEYS
    defaults(book)                        -> tuple of DEFAULT_KEYS
    triggers(book, loan, date)            -> tuple of trigger names

DESIGN DECISION — why is days past due counted from the oldest uncovered due and not
from the first missed payment? Because the bank lends a schedule, not a sequence of
receipts: a payment of kind `instalment` is booked against the due it names, a due is
uncovered while those payments do not cover it, and the oldest uncovered due is the one
the days run from. So `days_between(oldest uncovered due, date)` is the count a
supervisor would reproduce by hand, and a payment that clears an instalment moves the
reference due forward exactly one step. A count taken from the first missed `paid_on`, or
reset by every partial payment, would disagree with the book on the same facts.

DESIGN DECISION — why are both halves of the materiality test required? Because they
measure two different things and either alone would be wrong. The absolute half is a
policy floor — a bank does not count days past due over arrears too small to be worth a
process — and the relative half is a proportionality test against the exposure, so a
large facility is not pushed into default by the same cents that default a small one.
Arrears clear the threshold only when they are at least the floor **and** at least the
relative share; arrears that clear one half and not the other are recorded as arrears
with `material` false, and the days count stays at zero. The record keeps `arrears_cents`
either way, so a reader can see what failed and not just that something did.

DESIGN DECISION — why is the exposure the drawn balance rather than the exposure at
default? Because this stage must answer about any date without stage 5's undrawn limit
and conversion factor, and a materiality test whose denominator arrives from a later
stage is a test that cannot be reproduced where it is applied. The drawn balance is the
money already advanced and not yet prepaid, it is a fact the book holds for every date,
and it is the denominator the policy's own relative test is written against. Where the
loan has no undrawn limit, the drawn balance and the book's exposure at default are the
same number, so the two readings meet.

DESIGN DECISION — why does a cure before the probation not end a default? Because the
policy's cure is not the arrival of money, it is the survival of a period: a default
cured the month it was signalled would let a bank relabel a distressed borrower as
healthy too quickly, and the probation exists to price that. So the signalled default
carries `probation_until = add_months(signalled_on, CURE_MONTHS)`, `cured_on` is the
first cure event at or after that date, and a cure that lands earlier clears nothing —
the loan stays in the default bucket between its cure events, exactly as the book
records, and a default with no valid cure is still standing at the last reporting date.

DESIGN DECISION — why are the triggers a tuple and not a set of booleans? Because a
default has to be explainable, and the explanation is an ordered list of the things that
made it one: `days-past-due` when the backstop is crossed, then each uncured flag in
`UTP_FLAGS` order, whatever order the events were filed in. A set would lose the order a
report prints; a boolean would lose the reason. The tuple is also what makes the bucket
record answerable: the default bucket is the bucket of a loan whose trigger tuple is not
empty, so a loan signalled as a default with a small balance stays in the default bucket
at zero days rather than disappearing into `performing`: a default the bank signalled
that has not validly cured is still a default, whether or not a flag is standing today.

TODO: implement `dpd`, `bucket`, `defaults` and `triggers` in this file: the days counted
from the oldest materially unpaid due, the bucket they fall in, the ordered triggers that
make a loan a default, and the signalled defaults with the probation that decides when
their cure counts.
"""

import dates
import rules

BUCKET_KEYS = ("loan", "date", "dpd", "bucket", "arrears_cents", "material", "triggers")

DEFAULT_KEYS = ("loan", "signalled_on", "triggers", "cured_on", "probation_until")

BUCKETS = ("performing", "1-30", "31-60", "61-90", "default")

UTP_FLAGS = ("forbearance", "distressed-restructuring", "cross-default", "bankruptcy")

#: The backstop's own name in a trigger tuple: it is not a `UTP_FLAGS` event, it is
#: the days count crossing `rules.DEFAULT_DAYS_PAST_DUE`.
_DAYS_PAST_DUE = "days-past-due"


def dpd(book_, loan, date):
    """The days from the oldest materially unpaid instalment to `date`.

    An instalment is uncovered while the instalment payments received by `date` do not
    cover the schedule up to it, and the arrears those payments leave behind are material
    when they are at least `MATERIALITY_ABSOLUTE_CENTS` **and** at least
    `MATERIALITY_RELATIVE_BP` of the drawn balance. Arrears below either half leave the
    days at zero. A loan the book does not hold raises `BookError` naming it.
    """
    raise NotImplementedError("stage 2: implement dpd()")


def bucket(book_, loan, date):
    """The delinquency bucket of `loan` at `date`, with the arrears that put it there.

    `BUCKET_KEYS` in order: the loan, the date, the days, the bucket `BUCKET_DAYS` maps
    those days to, the arrears the days were measured against, whether those arrears
    cleared the policy's two-part test, and the triggers that make the loan a default.
    The bucket is `"default"` whenever the loan is a default — a trigger holds, or a
    default the bank signalled has not validly cured — so a signalled default speaks at
    zero days.
    """
    raise NotImplementedError("stage 2: implement bucket()")


def triggers(book_, loan, date):
    """What makes `loan` a default at `date`, in `UTP_FLAGS` order under the backstop.

    `days-past-due` first when the days reach `DEFAULT_DAYS_PAST_DUE`, then every policy
    flag an event raised by the date and no valid cure has cleared. An empty tuple is the
    verdict that the loan is not a default.
    """
    raise NotImplementedError("stage 2: implement triggers()")


def defaults(book_):
    """Every default the book records, with the probation that decides its cure.

    `DEFAULT_KEYS` in order: the loan, the date it was signalled,
    `probation_until = add_months(signalled_on, CURE_MONTHS)`, and `cured_on` — the first
    cure event at or after the probation, or `None` while the default still stands.
    """
    raise NotImplementedError("stage 2: implement defaults()")
