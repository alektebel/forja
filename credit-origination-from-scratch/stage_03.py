"""Credit Origination From Scratch — stage 3: The collateral and its advance.

One line of the application says what the borrower wants; the estate's own
collateral record says what stands behind the ask. This stage cuts the bank's
single haircut table across the assets the applicant put on the table, reads
what each asset's lien really covers, and answers the two numbers the decision
stage reads: the advance rate the request takes against the collateral, and
whether the collateral carries the request. Nothing here is a model — the
haircut table is somebody else's decision, and the record answers it as fact,
asset by asset, in the estate's own order.

DESIGN DECISION — why is the haircut applied asset by asset, from the policy's
own table, before anything else is measured?
Because the bank keeps one haircut policy for the whole book — M1's own table,
the one the estate's `HAIRCUT_BP` carries — and a stage that re-invented
haircuts per report would invent a policy nobody wrote. So each asset is cut
the same way the bank's records are: `value * haircut // 10000` of the value
comes off the asset, truncated to the cent, and what is left of it is the
asset's net value. The record reports the cut as fact — every per-asset row
carries the kind's haircut, the cents taken off and the worth left over — and
the record's totals re-add the rows, so a reviewer can audit the cut instead of
trusting it.

DESIGN DECISION — what is the advance rate measured against, and where does the
cap bite?
The record answers for what was offered, so the advance rate is measured
against the value the assets are declared at: `10000 * requested // total`,
truncated — and the policy's `ADVANCE_CAP_BP` holds after it, a request a
basis point over the cap not carried. The cap check runs against the recomputed
rate, never against the request against some other number: a request whose
rate is 8000.9bp reads 8000 and is carried, and one a whole basis point over
reads 8001 and is not. What the cut announced itself in is the per-asset rows
and the record's `haircut_cents`, and the estate's own decision records are
the answer the whole course is held to: the deduction the policy makes to the
value of an asset is a fact about what an asset will fetch, and the bank's
advance and lien clauses sit on top of the worth the assets are offered at.

DESIGN DECISION — why does an unsecured offer answer instead of refusing?
Because the borrower may offer nothing and be told so: one `none`-kind listing
is unsecured by choice — it counts nothing at all, whatever value the estate
states for it — and a request against nothing advances at nothing, which is a
record with reasons in it, not an exception. The offer that is unsecured is a
fact the record reports; only a book that says so twice refuses, because a
book that is unsecured by choice twice has stated something the arithmetic
cannot carry. A book of no listings at all is answered too: a total of nothing
advances at nothing and carries nothing.

DESIGN DECISION — why does the record report a shortfall instead of refusing
it, and when is the application not carried?
Because the committee can price a shortfall or ask for more of it off, and a
refusal would take both choices away. A mortgage or an equipment asset whose
lien share does not reach the amount is still counted into the totals and
carries its row; the record answers `eligible` False and the reader can see
from `lien_cents` alone what the gap was. `eligible` is three clauses held at
once — no `none`-kind book unsecured by choice alone, the lien covering the
amount, and the advance rate inside the cap — and every clause is a number the
record already carries, so the answer is auditable clause by clause.

DESIGN DECISION — why does the stage take the estate as it goes, building one
of its own when none is handed in?
Because a check is what proves a stage asked the world for nothing beyond its
question, and that proof needs `cases.stats()` of the estate the stage actually
read: the estate is rarely handed in, the stage builds `Cases.build(7)` of its
own for the call and answers from it, and a refused call reaches no record —
the counters other than `lookups` stand exactly where they stood.

The stage answers, in the shapes the contract pins:

    RETURN_KEYS                                       the eight fields of an answer, in order
    return_of(id, requested_cents, cases=None)        -> a RETURN_KEYS record, per-asset rows and all
    advance(id, requested_cents, cases=None)          -> the advance rate the collateral supports
    ReturnError(ValueError)                           the stage's refusal, naming the offender

TODO: implement `RETURN_KEYS`, `return_of` and `advance` in this file: the cut
the bank's own table makes per asset, the worth and the cover the liens carry,
and the advance rate the cap holds after.
"""

import cases as _cases
import policy

RETURN_KEYS = ("id", "collateral", "value_cents", "haircut_cents",
               "net_value_cents", "lien_cents", "advance_bp", "eligible")

_PLEDGED = ("collateral_id", "kind", "value_cents", "lien_share_bp", "haircut_bp",
            "net_value_cents", "lien_cents")


class ReturnError(ValueError):
    """The stage's refusal: an offer the collateral arithmetic cannot carry."""


def return_of(id, requested_cents, cases=None):
    """The collateral of `id`, cut and covered, against `requested_cents`.

    The record carries the eight `RETURN_KEYS` fields: `collateral` is one row
    per asset the estate offered, in the estate's own order, each row answering
    `(collateral_id, kind, value_cents, lien_share_bp, haircut_bp,
    net_value_cents, lien_cents)`; the record's `value_cents`, `haircut_cents`,
    `net_value_cents` and `lien_cents` are the totals those rows re-add to,
    the `none`-kind rows reporting themselves and counting nothing at all in
    the totals; `advance_bp` is `10000 * requested_cents // total`, truncated,
    where the total is the worth the assets are declared at, and the policy's
    `ADVANCE_CAP_BP` holds after it; and `eligible` is the three clauses held
    at once — no book the policy underwrites nothing of, whether a book of no
    assets at all or a single `none`-kind listing alone, the lien covering the
    amount, and the advance inside the cap. One `none`-kind
    listing is unsecured by choice, counts nothing at all, and is answered;
    more than one refuses by name, and so does a kind, a worth or a pledge the
    policy does not carry.

    The estate is the one handed in, or a build of this stage's own: a refused
    call reaches no record, and the answer is a function of the estate's facts
    alone.
    """
    raise NotImplementedError("stage 3: implement return_of()")


def advance(id, requested_cents, cases=None):
    """The advance rate in bp the estate's own collateral supports for the request.

    The record's `advance_bp` and nothing else: `10000 * requested_cents //
    total` of the value the offered assets are declared at, truncated, and `0`
    against a book of nothing — a `none`-kind offer advancing at nothing
    rather than refusing. The refusals `return_of` makes are this one's too.
    """
    raise NotImplementedError("stage 3: implement advance()")
