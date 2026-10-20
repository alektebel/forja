"""Distressed Debt Investing From Scratch — stage 4: Merton distance-to-default.

The recovery views so far all read the book. This stage reads the identity: is
the borrower actually going to be in the waterfall? The Merton machinery asks
it in one ratio — how far the borrower's assets stand above its debt, in units
of the volatility band the identity books it at — and this stage computes that
ratio in whole units, no floats, no standard deviations, no simulator.

The inputs are data: the asset value the borrower's path records, the debt the
identity's debt table books, and a volatility band in basis points that must be
one of the tabulated bands' own upper bounds — `calm` ends at fifteen hundred,
`normal` at thirty-two, `stressed` at fifty-four hundred, and a borrower is
booked at a band, not between two of them. The distance is

    dd_units = (asset - debt) * DD_SCALE * DD_SCALE // (asset * band_bp)

— the equity cushion over the par of the assets, measured in band units, at
the same fixed-point scale the bank's arithmetic already ran at. A borrower
whose debt stands at or above its assets answers a negative distance: the
waterfall is already deciding, and the distance says so honestly.

`to_pd(dd_units)` maps the distance to a cumulative probability of default,
and refuses to invent a row: the mapping is the `PD_LADDER` the world carries,
walked exactly like the bank's own migration buckets — the row whose
`from_dd` is the greatest lower bound of the distance answers — and a distance
below the ladder's first bound or above its last is refused by name. The
Merton view of recovery is then `10000 - pd_bp`, what the model expects the
par to be worth if it is not all wiped out.

    DD_SCALE                      the fixed-point scale the distance runs at
    MertonError                   the refusal this stage raises
    dd(asset_value, debt, band_bp)
                                  -> the distance in whole band units
    to_pd(dd_units)               -> the cumulative PD in basis points, off the
                                     world's own ladder

DESIGN DECISION — why must the band be a tabulated upper bound?
Because a band the identity books but the table does not hold is not a band —
it is a shrug. The bands table is the volatility the model knows how to mean:
three rows, three upper bounds, and a borrower's own bookings are exactly such
values. A distance computed at some in-between band (twenty-five, say) would
be an answer the ladder cannot grade and the check cannot recompute from the
world, so it is refused by name — the band the caller meant is in the
message, and the fix is to book the borrower properly.

DESIGN DECISION — why is the distance an integer fixed-point ratio instead of
a signed float with a normal distribution?
Because a float distance invites a float probability — a curve fitted to a
ladder — and this course's probabilities are tabulated, walked like the bank's
own buckets. The integer ratio keeps the monotone behaviour the identity
claims (more debt, or a wider band, pushes the distance down) with arithmetic
a reviewer reproduces, and it lands in the same units the PD ladder is walked
in. Where a real model would smooth the ends, the ladder refuses: the ends
are the world's, not this stage's.

DESIGN DECISION — why does the distance allow debt above assets instead of
refusing it?
Because negative distance is information, not a broken input: an asset value
the path recorded below the borrower's debt means the option is already
exercised and the waterfall is deciding, and `to_pd` will answer the ladder's
worst row for it (or refuse if the distance sinks past even that row). Only a
nonsense input — a non-positive asset, a non-positive debt — is refused at
`dd` itself, since a borrower with no assets or no debt is not a credit.

DESIGN DECISION — why is `to_pd` a separate walk rather than a column of `dd`?
Because the mapping from distance to probability is the world's data and not
this stage's arithmetic: the ladder arrives from the world, the greatest
lower-bound walk is the bank's own bucket semantics, and a check that wants to
prove the stage is honest walks the same ladder itself. Keeping the two
functions apart also lets the check pin the ladder's edges from both sides —
at each `from_dd` the row's own probability answers, one unit below the
previous row's does — which is exactly where a hand-rolled mapping would
drift off the accumulated rows.

TODO: implement `MertonError`, `dd` and `to_pd` in this file: the integer
distance over a tabulated band, and the world's own ladder walked by greatest
lower bound.

    `dd` refuses by name a band that is not one of the tabulated bands' upper
    bounds, a non-positive asset or debt, and an input that is not a whole
    number. `to_pd` refuses by name a distance below the ladder's first bound
    or above its last, and a distance that is not a whole number.
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

import claims as market

DD_SCALE = market.DD_SCALE


class MertonError(ValueError):
    """The refusal this stage raises: a credit the identity cannot measure.

    It names the offender — the band the table does not hold, the asset or
    debt that is not a count of cents, the distance the ladder does not walk
    to — because a distance nobody can grade must say what it was asked for
    rather than answer a probability nobody booked.
    """


def _whole(value, what):
    """A whole number, and a `bool` is not one here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise MertonError("the %s %r is a %s, not a whole number"
                          % (what, value, type(value).__name__))
    return value


def dd(asset_value, debt, band_bp):
    """The distance to default in whole band units, computed in integers.

    `(asset - debt) * DD_SCALE * DD_SCALE // (asset * band_bp)`: the equity
    cushion over the assets, measured against the band the identity books the
    borrower at. A borrower whose debt stands at or above its assets answers
    a negative distance and says so.

    A band that is not one of the tabulated bands' upper bounds, a
    non-positive asset or debt, or an input that is not a whole number, is
    refused by name.
    """
    raise NotImplementedError("stage 4: implement dd()")


def to_pd(dd_units):
    """The cumulative probability of default the distance maps to, in bp.

    The world's own `PD_LADDER`, walked the bank's way: the row whose
    `from_dd` is the greatest lower bound of the distance answers its
    `pd_bp`. A distance below the first bound or above the last is refused by
    name — the ladder's ends are the world's, not the stage's, and a
    probability invented beyond them would smooth what the world measured.
    """
    raise NotImplementedError("stage 4: implement to_pd()")
