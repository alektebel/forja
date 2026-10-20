"""IRB and Regulatory Capital — stage 6: BE-EAD and its CCFs.

A capital requirement prices an *exposure*, and the exposure of a loan that has
not been drawn down entirely is bigger than its balance: the bank is committed
to lending further, and the policy converts that commitment at a product's own
credit conversion factor. The best-estimate exposure at `at` is
`drawn + undrawn * ccf // 10000` — the drawn cash the loan has received so far
(instalments paid less prepayments, floored at zero, exactly the drawn-cash
arithmetic the book records), the undrawn limit the loan still carries after
the plan the contract schedules is subtracted, and the product row of
`irb.CCF_BY_PRODUCT_BP` converting the undrawn part, truncated once.

The other half of the stage is the estimator — what the bank's *own defaults*
have already taught it about those factors. For each product the bank has
defaults recorded in, the CCF the bank earns is the drawdowns the book records
at the default dates over the open commitments that were there at origination:
`Σ drawn(default) // Σ open(origination)`, truncated, and clamped to the
policy's own floor and cap. A product the bank has never defaulted on, and a
product whose defaults all sat on limits of zero, are outside the estimator's
support — refused by name, because a factor with no exposure behind it is not
an estimated factor but a guess.
TODO: implement `be_ead` and `ccf` in this file: the exposure at default a
loan's own drawn and open amounts add to, and the conversion factor the
segment's own defaults have realised so far."""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import dates
import irb
from book import BookError
from irb import PolicyError

#: The products the CCF table is keyed on, in the policy's own order.
PRODUCTS = tuple(sorted(irb.CCF_BY_PRODUCT_BP, key=irb.CCF_BY_PRODUCT_BP.get))

#: The drawn/undrawn conversion factors, as the policy carries them.
CCF_BY_PRODUCT_BP = irb.CCF_BY_PRODUCT_BP

#: The clamps the bank's own estimate of a factor is held between.
CCF_FLOOR_BP = irb.CCF_FLOOR_BP

CCF_CAP_BP = irb.CCF_CAP_BP

#: The scale every factor and basis point measure is held at.
BP_SCALE = 10000


class EadError(PolicyError):
    """The refusal this stage raises: something that cannot be an exposure.

    It names the offender — the loan the book does not hold or is not on at the
    reporting date, the product outside the policy's table, the segment the
    estimator has no default in, the segment whose defaults sat on zero open
    commitments — because an exposure the arithmetic cannot stand behind must
    say what it was asked for rather than answer one divided by nothing.
    """


def drawn_cents(book, loan, at):
    """The cash `loan` has drawn by `at`: instalments paid, less prepayments.

    The world's own drawn-cash arithmetic — every instalment the borrower
    actually paid by `at` counted, every prepayment taken back off, then
    floored at zero. The scheduled plan is independent of this: a borrower that
    paid ahead of the plan is drawn for what it paid, not for what the plan
    said it should have paid by now.
    """
    raise NotImplementedError("stage 6: implement drawn_cents()")


def plan_cents(book, loan, at):
    """What the contract says should have been paid by `at`: the schedule's own sum."""
    raise NotImplementedError("stage 6: implement plan_cents()")


def undrawn_cents(book, loan, at):
    """The limit `loan` still carries at `at`, after what paying ahead consumed.

    The undrawn limit less what the borrower has drawn *above* the plan — the
    part of the limit paying ahead has already eaten is not available to draw
    again — floored at zero, so a limit that has been fully consumable is
    answered as nothing rather than as a negative commitment.
    """
    raise NotImplementedError("stage 6: implement undrawn_cents()")


def be_ead(book, loan, at):
    """The best-estimate exposure of `loan` at `at`, in cents, at its product row.

    `drawn + undrawn * ccf // 10000` — the drawn cash, the undrawn limit after
    paying ahead is accounted for, and the product's own conversion factor
    applied to the undrawn part with one truncated division. The limit's own
    size sets the exposure far more than the factor does: the factor converts a
    commitment, and the answer commits to no more of one than the limit holds.

    A loan the book does not hold or is not on at `at`, or a product whose row
    the policy does not carry, is refused by name.
    """
    raise NotImplementedError("stage 6: implement be_ead()")


def ccf(book, segment):
    """The conversion factor the bank's own defaults of `segment` estimate, in bp.

    Over every loan the book signalled as default in `segment` — a default that
    has since cured is still one the bank earned a factor from — at its first
    signalled day, the drawdowns the book records between origination and that
    day are the numerator, each defaulted loan taken at
    `max(0, drawn(default) - drawn(origination))`, floored. The open
    commitments that were there at origination are the denominator, floored the
    same way. The quotient is `drawn * 10000 // open`, truncated once, then
    clamped to the policy's own floor and cap. The weight is the limit, not the
    count: a product whose one defaulted borrower had a big limit out-weighs
    one with a small limit.

    A segment outside the policy's products, a segment the bank has never
    defaulted on, and a segment whose defaults all sat on limits of zero are
    refused by name — the estimator answers only inside its support, and a
    factor with no open exposure behind it is a guess, not an estimate.
    """
    raise NotImplementedError("stage 6: implement ccf()")
