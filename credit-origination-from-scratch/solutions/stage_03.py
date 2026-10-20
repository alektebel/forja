"""Credit Origination From Scratch — stage 3: The collateral and its advance.

One line of the application says what the borrower wants; the estate's own
collateral record says what stands behind the ask. This stage cuts the bank's
single haircut table across the assets the applicant put on the table, reads
what each asset's lien really covers, and answers the two numbers the decision
stage reads: the advance rate the request takes against the collateral, and
whether the collateral carries the request. Nothing here is a model — the
haircut table is somebody else's decision, and the record answers it as fact,
asset by asset, in the estate's own order.
"""

import cases as _cases
import policy

RETURN_KEYS = ("id", "collateral", "value_cents", "haircut_cents",
               "net_value_cents", "lien_cents", "advance_bp", "eligible")

_PLEDGED = ("collateral_id", "kind", "value_cents", "lien_share_bp", "haircut_bp",
            "net_value_cents", "lien_cents")

_NONE = "none"

_BP = 10000

_CAP = policy.ADVANCE_CAP_BP

_STAGE = "stage 3: "


class ReturnError(ValueError):
    """The stage's refusal: an offer the collateral arithmetic cannot carry."""


def _whole(value, what):
    """Refuse a count that is not a whole number of its unit, naming the field."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReturnError(_STAGE + "%s is %r, not a whole number" % (what, value))
    return value


def _book(cases):
    """The estate the answer is computed on: the one handed in, or a fresh build."""
    if cases is None:
        return _cases.build(_cases.BUILD_SEED)
    return cases


def _row(offer):
    """One asset as the record reports it: cut, net and covered, in that order.

    The haircut comes off the value first — `value * haircut // 10000`
    truncated, the policy's own single table for the kind — and what is left of
    the asset is its net value. The lien covers only the share it is pledged
    for, on the asset's own worth; a `none` row is unsecured by choice and
    covers nothing, whatever share the estate states for it.
    """
    identity = offer["collateral_id"]
    asset = "the collateral %r" % (identity,)
    kind = offer["kind"]
    if kind not in policy.COLLATERAL_KINDS:
        raise ReturnError(_STAGE + "%r is not a kind the policy underwrites, "
                                    "in %s" % (kind, asset))
    value = _whole(offer["value_cents"], "%s's worth" % (asset,))
    if value < 0:
        raise ReturnError(_STAGE + "%s holds %d cents of worth, and worth is not "
                                    "negative" % (asset, value))
    share = _whole(offer["lien_share_bp"], "%s's lien share" % (asset,))
    if not 0 <= share <= _BP:
        raise ReturnError(_STAGE + "%s is pledged at %d bp, beyond the scale"
                          % (asset, share))
    haircut = policy.HAIRCUT_BP[kind]
    trimmed = value * haircut // _BP
    net = value - trimmed
    lien = 0 if kind == _NONE else value * share // _BP
    return (identity, kind, value, share, haircut, net, lien)


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
    wanted = _whole(requested_cents, "the requested amount")
    if wanted < 0:
        raise ReturnError(_STAGE + "the request of %r is going the wrong way"
                          % (requested_cents,))
    book = _book(cases)
    offers = book.collateral(id)
    rows = tuple(_row(offer) for offer in offers)
    double = tuple(row for row in rows if row[1] == _NONE)
    if len(double) > 1:
        raise ReturnError(_STAGE + "the collateral %r and %r both say unsecured "
                                    "by choice, and a book is unsecured once"
                          % (double[0][0], double[1][0]))
    keeps = tuple(row for row in rows if row[1] != _NONE)
    value = sum(row[2] for row in keeps)
    net = sum(row[5] for row in keeps)
    lien = sum(row[6] for row in rows)
    haircut_cents = value - net
    advance_bp = 0 if value == 0 else _BP * wanted // value
    unbacked = not keeps
    covered = lien >= wanted
    eligible = not unbacked and covered and advance_bp <= _CAP
    return {"id": id, "collateral": rows, "value_cents": value,
            "haircut_cents": haircut_cents, "net_value_cents": net,
            "lien_cents": lien, "advance_bp": advance_bp, "eligible": eligible}


def advance(id, requested_cents, cases=None):
    """The advance rate in bp the estate's own collateral supports for the request.

    The record's `advance_bp` and nothing else: `10000 * requested_cents //
    total` of the value the offered assets are declared at, truncated, and `0`
    against a book of nothing — a `none`-kind offer advancing at nothing
    rather than refusing. The refusals `return_of` makes are this one's too.
    """
    return return_of(id, requested_cents, cases)["advance_bp"]
