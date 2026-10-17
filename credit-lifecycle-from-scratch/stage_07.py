"""Credit Lifecycle From Scratch — stage 7: The three stages and the significant increase in credit risk.

Every stage before this one answers a question about a loan as if the whole life of
the loan were one regime: a schedule, a bucket, a PD, a loss, an exposure, a provision.
A bank does not report that way. The same loan, on the same day, provisions twelve
months of loss or its whole remaining life depending on one thing the bank has to
decide and defend — whether its credit risk has risen significantly since it was
granted. This stage is that decision, and it is the reason the provision of a portfolio
cannot be a single number.

The decision has an order, and the order is the point. A loan in default is stage 3,
full stop: the bank is not asking whether the risk rose, it is answering that the risk
has crystallised. A loan that is not in default is stage 2 when either half of the
policy's two-part test fires — a lifetime probability of default at twice what the loan
started with, or an absolute rise of three hundred basis points — or when the
days-past-due backstop is reached. Everything else is stage 1. The `reason` names which
of those fired, because a staging a reader cannot argue with is a staging nobody can
audit.

An uncured unlikeliness-to-pay flag gets no branch of its own. A standing flag is what
stage 2's own definition of default is made of, so a flagged loan is already in the
first branch on every date this book records — a branch nothing can reach is not a
rule, and the stage that owns the flags is stage 2. They are not idle, though: a date
that carries one is not a quiet date, and a quiet date is what a stage-2 loan owes
before it may return to stage 1.

Two things make this stage more than a lookup. The first is that the test compares the
loan with *itself*: the same PD term structure read at the loan's own origination grade
and at the grade the book records now, over the same horizon, so a portfolio-wide
average never decides one borrower's regime. The second is that a loan does not leave
stage 2 on the day it improves — it leaves after `SICR_RETURN_PERIODS` consecutive
reporting dates at which nothing fires, and that survivorship is part of the answer
rather than a convention added afterwards.

    STAGE_KEYS                                   the seven fields of a staging, in order
    TRANSFER_KEYS                                the five fields of a transfer, in order
    SICR_MULTIPLIER_BP                           the multiple of the origination PD that fires the test
    SICR_ABSOLUTE_BP                             the absolute rise, in basis points, that fires it
    SICR_DAYS_PAST_DUE                           the days-past-due backstop
    SICR_RETURN_PERIODS                          the quiet reporting dates a stage-2 loan owes
    stage(book, loan, date, model=None)          -> STAGE_KEYS: which regime, and why
    sicr(book, loan, date, model=None)           -> the two-part test, as a verdict
    transfers(book, start, end)                  -> TRANSFER_KEYS, one per loan that moved

DESIGN DECISION — why does the default speak before the test?
Because stage 2 already defined what a default is, and asking whether a defaulted
loan's credit risk has risen *significantly* is asking a question that has been
answered more strongly already. So the order is the policy's, not the arithmetic's: a
default is stage 3 whatever the PD term structure says, and the PD test is only reached
by a loan that is still expected to pay. A stage that let the PD test override a
default would move an impaired loan back to twelve-month provisioning on the strength
of a modelling artifact, which is exactly the kind of answer a supervisor asks to see
argued rather than assumed.

DESIGN DECISION — why is the loan compared with its own origination grade?
Because a significant increase in credit risk is a statement about *this* borrower, and
the only honest baseline is the one that borrower started with. So the same artifact's
term structure is read twice, once at the grade the book records at the date and once at
the loan's origination grade, over the same horizon — the same number of months on both
sides — and the two basis points are compared without a division, because a division
here would invent a rounding the policy never pinned. `pd_bp` and `origination_pd_bp`
are both printed in the record so a reader can run the test by hand.

DESIGN DECISION — why does the return rule count reporting dates rather than days?
Because the rule is about *reported* evidence, and a bank reports at month ends. A
borrower can be quiet for ninety days and still be a loan the bank has only seen once;
what the policy asks for is a run of reporting dates at which nothing fired, so the
count is over the book's own reporting dates and never over the calendar. That is also
why the survivorship lives inside `stage` rather than in a caller: the stage at a date
is a function of that date *and* the run of dates before it, and a stage that answered
from the date alone would return a loan to stage 1 a month too early.

DESIGN DECISION — why does the stage take a model it is not obliged to use?
Because the staging is the input to a decomposition, and a decomposition has to be able
to ask "what would this loan's regime have been under the older artifact?" without
re-deriving the whole test. With `model` given the two-part test reads that artifact's
PDs and nothing else moves; with it left out the stage uses the artifact in force at the
date — the greatest `as_of` not after it, the greater version breaking a tie. The
decision order, the reasons, the backstop and the return rule are the same either way,
so only the PDs move, which is what makes a re-rating a provision movement rather than
an assumption.

DESIGN DECISION — why is the `reason` part of the answer rather than a log line?
Because two loans in stage 2 are not the same loan. One is there because its lifetime
PD doubled against its own origination grade, another because it is thirty days past due
— and the provision, the cure period and the report that follows all depend on which.
So the reason is a field of the record, it names what fired in the policy's own
vocabulary, and a transfer carries the reason from the date it moved rather than the
reason at either end of the window.

TODO: implement `stage`, `sicr` and `transfers` in this file: the ordered decision with
its `reason`; the two-part test read off the artifact's own term structure at the
loan's origination grade and at the grade the book records, in basis points and without
a division; and the transfers, one row per loan that moved, with the date it moved and
the reason from that date's own record.
"""

import dates
import rules
import stage_02
from book import BookError

STAGE_KEYS = ("loan", "date", "stage", "reason", "sicr", "pd_bp", "origination_pd_bp")

TRANSFER_KEYS = ("loan", "date", "from_stage", "to_stage", "reason")

SICR_MULTIPLIER_BP = 20000

SICR_ABSOLUTE_BP = 300

SICR_DAYS_PAST_DUE = 30

SICR_RETURN_PERIODS = 2

REASON_CREDIT_IMPAIRED = "credit-impaired"

REASON_SIGNIFICANT_INCREASE = "significant-increase"

REASON_DAYS_PAST_DUE = "days-past-due"

REASON_NO_SIGNIFICANT_INCREASE = "no-significant-increase"

REASON_RETURN_NOT_YET = "return-not-yet"


def sicr(book, loan, date, model=None):
    """Whether the loan's credit risk has risen significantly at `date`: a verdict.

    The two-part test, in basis points and without a division: the lifetime PD the
    artifact gives the loan's grade at the date, over the loan's remaining months,
    against the same artifact's PD for the loan's *origination* grade over the same
    months. The first half fires when the current figure is at least
    `SICR_MULTIPLIER_BP` times the origination one, the second when it is at least
    `SICR_ABSOLUTE_BP` higher; either half is enough. `model` names the artifact to
    read, and the one in force at the date when it is left out.
    """
    raise NotImplementedError("stage 7: implement sicr()")


def stage(book, loan, date, model=None):
    """The loan's regime at `date`, and the reason it is in it: `STAGE_KEYS`.

    The decision order is the policy's: a defaulted loan is stage 3
    (`"credit-impaired"`); a loan that is not defaulted is stage 2 when the two-part
    test fires (`"significant-increase"`) or when the days past due reach the backstop
    (`"days-past-due"`); anything else is stage 1 (`"no-significant-increase"`). An
    uncured unlikeliness-to-pay flag has no branch here: a standing flag is what stage
    2's definition of default is made of, so a flagged loan is already stage 3 — but a
    date that carries one is not a quiet date.

    A loan that was in stage 2 does not leave it on a single quiet date: it returns to
    stage 1 only after `SICR_RETURN_PERIODS` consecutive reporting dates at which the
    test, the backstop and the flags all stayed silent, and until then it is stage 2
    for a reason the record has to carry. A default's cure is not this rule — stage 3
    ends when the default ends, and the loan is compared again at once.
    """
    raise NotImplementedError("stage 7: implement stage()")


def transfers(book, start, end):
    """One `TRANSFER_KEYS` row per loan whose stage moved between the two dates.

    In the book's own loan order, with the date the stage first differed from its
    value at `start` and the reason taken from that date's own record — never the
    reason at either end of the window. A loan whose stage is the same at both dates
    is not a transfer, whatever happened in between.
    """
    raise NotImplementedError("stage 7: implement transfers()")
