"""Credit Lifecycle From Scratch — stage 4: The recovery cash flows and the loss given default.

A default is not the end of a loan's arithmetic; it is where the arithmetic gets
harder. The collateral is realised, the collectors are paid, and what comes back
arrives over months or years after the day the loan stopped performing. This stage
turns those observed flows into the two integers a provision is then built from: what
was recovered, and what was lost.

Everything here is the book's own facts read through the contract's one fixed point.
Each recovery flow is discounted to the loan's default date at the loan's own effective
rate — stage 1's rate, stepped one period at a time with stage 1's own truncation — so a
euro recovered two years after the default is worth fewer cents than the same euro
recovered next month. A cost is a negative flow and reduces what came back, and the
collateral's own realisation is discounted from the date it was collected, net of the
policy's haircut on the collateral alone.

The loss given default is the complement of that recovery against the balance the loan
still owed on the day it defaulted, clamped to the policy's floor and cap; a recovery
above the balance is capped at the balance and reported as capped rather than silently
truncated. A loan that never defaulted is refused by name: an LGD is a fact about a
default, not a prediction about a healthy loan. A default that has since cured is still
a default — the loss was measured at the date it was signalled, whatever happened to the
loan afterwards — so only a loan the book records no default at all for is refused.
`lgd_by_segment` turns one segment's defaults into the
exposure-weighted loss that segment has realised, and answers `None` for a segment that
has not had a default yet — the honest answer is that there is nothing to weigh.

    RECOVERY_KEYS                                the four fields of a recovery record, in order
    LGD_KEYS                                     the six fields of a loss-given-default record, in order
    LGD_FLOOR_BP                                 the lowest loss the policy books
    LGD_CAP_BP                                   the highest loss the policy books
    COLLATERAL_HAIRCUT_BP                        the policy's haircut, by collateral kind
    recoveries(book, loan)                       -> RECOVERY_KEYS, the flows discounted to the default
    lgd(book, loan)                              -> LGD_KEYS, the loss one default cost
    lgd_by_segment(book, segment)                -> the exposure-weighted LGD, or None

DESIGN DECISION — why is every flow discounted to the default date rather than to the
reporting date? Because the LGD is a fact about the default, not about the month the
report is printed in: the loss was fixed the day the loan stopped performing, and what
follows is the recovery of a part of it. Discounting to a moving reporting date would
make one default's LGD change as the months pass, which is the kind of reporting
artefact this course exists to refuse. The default date comes from the book's own
default record and the rate is the loan's own effective rate — the same rate stage 1
searched for — so one loan discounts at one rate for its whole life.

DESIGN DECISION — why is a cost a negative flow rather than a separate field? Because
the collectors' bill is money that did not come back, and a recovery total that quietly
ignored it would overstate what the bank collected. Keeping it a negative amount in the
same stream means the recovery total is one sum over one list, the `costs` source stays
visible in `flows`, and there is no second place a stage could forget to subtract. A
cost paid later is discounted from its own date, exactly like any other flow.

DESIGN DECISION — why is a recovery above the balance capped with the cap visible?
Because an LGD below zero is a policy statement the bank has not made — the floor is
zero — and truncating silently would hide a real disagreement between the flows the book
holds and the balance it says the loan owed. Capping the recovery at the balance lets
the record show `recovered_cents == balance_cents`, which a reader can see, and leaves
the clamp to do its own work on the basis points rather than having the division do it
by accident.

DESIGN DECISION — why does a segment with no defaults answer `None` rather than zero?
Because zero is a number a bank would book, and it would be a lie: the segment has
simply not produced a default yet, and there is nothing to weigh. `None` is the record
saying so, and the caller has to decide what the absence means rather than reading a
zero as "no loss".

DESIGN DECISION — why is the haircut on the collateral alone? Because the policy's
haircut is a statement about what a pledged asset will fetch, not about the cash the
borrower's own collectors handed over; applying it to cash would tax a euro the bank
already has. So the haircut reduces the `collateral` source alone, the cash and the
costs pass at face, and `haircut_bp` records the rate that was applied so the arithmetic
can be replayed by hand.

TODO: implement `recoveries`, `lgd` and `lgd_by_segment` in this file: the loan's
recovery flows discounted to its default date at its own effective rate, the loss given
default that complement leaves once it is clamped to the policy, and the
exposure-weighted loss of a whole segment of defaults.
"""

import dates
import rules
import stage_01
from book import BookError

RECOVERY_KEYS = ("loan", "flows", "recovered_cents", "undiscounted_cents")

LGD_KEYS = ("loan", "balance_cents", "recovered_cents", "lgd_bp", "workout_months",
            "haircut_bp")

LGD_FLOOR_BP = rules.LGD_FLOOR_BP

LGD_CAP_BP = rules.LGD_CAP_BP

COLLATERAL_HAIRCUT_BP = rules.COLLATERAL_HAIRCUT_BP


def recoveries(book, loan):
    """The loan's recovery flows, discounted to the day the loan defaulted.

    `flows` is the book's own recovery rows in their own order, `undiscounted_cents`
    their plain sum, and `recovered_cents` each flow discounted to the loan's default
    date at the loan's own effective rate: the `collateral` source net of the policy's
    haircut, a `costs` source negative, and every flow discounted from its own date so
    collateral collected later is worth less than collateral collected sooner. A loan
    the book does not hold, and a loan that never defaulted, raise `BookError` naming
    it.
    """
    raise NotImplementedError("stage 4: implement recoveries()")


def lgd(book, loan):
    """The loss one default cost: `10000` less the recovery over the balance it owed.

    `balance_cents` is the loan's outstanding principal at its default date — the
    principal less the instalments and prepayments it had repaid by then, floored at
    zero — and `recovered_cents` is `recoveries`'s discounted total capped at that
    balance, so a recovery above the balance is capped and reported as capped.
    `lgd_bp` is `10000 - recovered_cents * 10000 // balance_cents`, truncated, then
    clamped to `LGD_FLOOR_BP`..`LGD_CAP_BP`; `workout_months` is the months from the
    default date to the last recovery flow, by `dates.add_months` arithmetic, and
    `haircut_bp` is the policy's haircut for the loan's collateral kind. A loan the
    book does not hold, a loan that never defaulted, a collateral kind the policy does
    not hold or a balance that is not positive raise `BookError` naming it.
    """
    raise NotImplementedError("stage 4: implement lgd()")


def lgd_by_segment(book, segment):
    """The exposure-weighted loss the book's own defaults of `segment` have realised.

    The weight is the balance at default and not the loan count: `Σ(lgd_bp *
    balance_cents) // Σ(balance_cents)`, truncated, over the segment's defaulted loans.
    A segment with no defaults answers `None`, and a segment the policy does not hold
    raises `BookError` naming it.
    """
    raise NotImplementedError("stage 4: implement lgd_by_segment()")
