"""IRB and Regulatory Capital — stage 5: Downturn LGD, the multiplier and the haircut.

M1's stage 4 turned a loan's recovery flows into the loss the default cost:
haircut first on the collateral, each flow discounted to the default date at
the loan's own contract rate, the recovery capped at the balance the loan
still owed, the complement clamped to the policy's floor and cap. That
arithmetic answered the bank's own books. A capital requirement prices a
*worse* day: the downturn.

The policy orders the steps and the order is the policy's. The best estimate
is computed first — the haircut inside the recovery arithmetic, the discount
inside it, the clamp inside it — and the downturn multiplier is applied to the
**finished** estimate, never to a raw flow: multiplying before the haircut or
before the discount produces a different integer, and the reversed order is a
bug the aged press of a spreadsheet produces more often than any typo. The
multiplied estimate is then held between the policy's own walls: a floor that
refuses to believe an over-collateralised loan loses nothing, and a cap at the
whole cycle.

One class is `refrigerate` — the estate's leasing booking — and the multiplier
does not touch it: its downturn treatment is frozen at the best estimate while
its own calibration is under review. The artifact's rows price every loan the
bank has not yet signalled as defaulted; the recoveries price the ones it has.
A loan with no recoveries behind its default — nothing came back — answers the
cap, and a loan whose grade row the artifact has since re-rated answers at the
version in force.
TODO: implement `best_estimate_lgd` and `downturn_lgd` in this file: the
workout loss the book's own flows measured, and the stressed loss the policy's
haircut, discount and downturn multiplier leave it at."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)


import dates
import irb
import rules
from book import BookError
from irb import PolicyError

#: The asset classes the multiplier is keyed on, in their own order.
CLASSES = irb.CLASSES

#: The two treatments a booking can enter; only `treat` is multiplied.
TREATMENTS = irb.REFRIGERATE_KINDS

#: The asset class a booking prices to, in their own order.
ASSET_CLASS_OF = irb.ASSET_CLASS_OF

#: The wish the discount steps hold: one basis point per step of a year.
ANNUAL_SCALE = 10000


class DownturnError(PolicyError):
    """The refusal this stage raises: something that cannot be a downturn LGD.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the collateral kind the policy holds no haircut for, the
    date the book does not cover, the asset class the multiplier does not key —
    because a loss the policy cannot stand behind must say what it was asked
    for rather than answer one the arithmetic cannot reproduce.
    """


def best_estimate_lgd(book, loan, at):
    """The loan's own loss given default, M1's recovery arithmetic recomputed.

    The balance the loan still owed on the day it defaulted — instalments and
    prepayments applied once each, floored at zero — is the denominator, and
    the recovery is each flow haircut on `collateral` first, discounted to the
    default date at the loan's own period rate, capped at the balance. The loss
    is `10000 - recovered * 10000 // balance`, truncated, then clamped to the
    world's own `LGD_FLOOR_BP..LGD_CAP_BP`.

    A loan the book does not hold, one not on the book at `at`, one that has
    never defaulted, a collateral kind the policy holds no haircut for, or a
    date the book does not cover is refused by name.
    """
    raise NotImplementedError("stage 5: implement best_estimate_lgd()")


def downturn_lgd(book, loan, at):
    """The downturn loss: the multiplier on the best estimate, held inside the walls.

    The **order is the policy's**. The best estimate is finished first — the
    haircut inside it, the discount inside it, the clamp inside it — and the
    class's multiplier is applied to the *result*, truncated once, so a reversed
    order (the multiplier on a raw flow, the haircut after the discount) answers
    a different integer and is exactly the kind of bug this stage refuses to
    produce. The multiplied estimate is then held between the policy's own
    walls, the floor refusing to hand a well-collateralised loan a loss of
    nothing and the cap ending it at the whole cycle.

    A `refrigerate` booking is not multiplied at all: its downgrade treatment is
    frozen at the best estimate while its own calibration is under review, and
    the answer is `be_bp` unchanged.

    A loan the book does not hold or is not on at `at` fails the stage by name;
    so does a collateral kind the policy holds no haircut for. A defaulted loan
    with nothing behind it — no recovery row came back — answers the cap, not a
    refusal: losing everything is the arithmetic's own honest answer. A
    **not-defaulted** loan answers at the artifact's row for the grade in
    force, the same rows every stage below prices with.
    """
    raise NotImplementedError("stage 5: implement downturn_lgd()")
