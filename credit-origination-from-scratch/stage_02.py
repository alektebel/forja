"""Credit Origination From Scratch — stage 2: The application scorecard.

Before a loan is priced or gated, the committee asks a quieter question: what
does the application *score*? This stage answers it as a **weighted table, not a
model** — the estate states the band each attribute sits in
(`cases.scorecard_bands`), the policy states what that band earns
(`policy.SCORE_POINTS_BP`) and what the attribute counts for
(`policy.SCORE_WEIGHTS_BP`), and the stage does the arithmetic a reviewer with a
pencil reproduces: points of the weight, truncated, one row per attribute, the
rows added, and the total then read into a band off the scorecard's own
thresholds.

Every number in the record is auditable from the two tables: the row carries the
attribute, the weight, the band, the points and the weighted points, so the
committee can re-add the total from the rows and re-read the band from the
total. A weight table that does not sum to the whole is refused — a scorecard
weighted out of anything but 10000bp reads as a different card than the one the
policy wrote, and no total built on it is the bank's.

    POINTS_KEYS                    the five fields of a points record, in order
    SCORE_ATTRIBUTES               the four attributes, in the order the record answers
    SCORE_SCALE_BP                 the whole the weights sum to — 100% written in bp
    ScorecardError                 the refusal this stage raises
    scorecard(cases, id)           -> POINTS_KEYS: one row per attribute, the
                                      total, and the band the total reads into
    score(cases, id)               -> int: the total the table answers

DESIGN DECISION — why is the score a weighted table rather than a model?
Because the policy's own words pin it: four attributes, weights that sum to the
whole, a points value per band, and a threshold table the total reads into. A
model — a fitted coefficient, a hidden interaction — would answer the *business*
question this course refuses to decide (which applicants to court is data the
committee owns). The table is somebody else's decision; the stage is held to
reproducing its arithmetic, and `cases.stats()` can prove the stage asked the
estate for exactly one thing: the bands.

DESIGN DECISION — why is the weights' sum checked when the policy is frozen?
Because the sum is what makes the card auditable, and a frozen world is not an
excuse for accepting a broken one: `SCORE_WEIGHTS_BP` sums to exactly 10000bp,
and the stage refuses anything else *before* it scores. A weight table that
summed to 9900 would owe 100bp to no attribute — every total built on it would
be short, every band under it wrong, and nothing in the record would say so.
The refusal names the number the weights must reach, not the table's author.

DESIGN DECISION — why does `attribute_bp` truncate instead of round?
Because the contract pins truncation for every ratio this course takes, and
this stage's division — points of the weight at the 10000 scale — is one:
`weight_bp * points_bp // 10000`. Half-up would answer a basis point more on
some attributes, the total would drift off the number the next threshold sees,
and the rerun would not be byte-identical to the walk a reviewer does. The
dropped fraction is the table's own shape, not noise the stage hides.

DESIGN DECISION — why does a refused attribute leave no row behind?
Because a points record is the table re-added: five fields per attribute, four
attributes, a total, a band. An application whose bands are incomplete — an
attribute the estate answers nothing for, or a band the policy does not score —
leaves the table unfinished, and half a table added up is a total nobody can
audit. The facts are validated whole before one row exists: the stage refuses
by name and returns nothing, and the estate's own counters can prove no record
was reached.

DESIGN DECISION — why does the total read its band off a descending table,
taking the first threshold it clears?
Because `SCORE_BANDS` is written top-down — 7700 for an A, 6800 for a B, down
to the last — so the band a total earns is the *first* threshold it clears
walking down: `total >= threshold`. Reading the table as ascending, or keeping
the last threshold cleared instead of the first, answers a band the total never
earned. A total below every threshold answers the last band rather than an
error — a band is a fact about the total, never a rejection of it — with that
band's own threshold travelling with it as the record's `band_bp`.

TODO: implement `ScorecardError`-refusing `scorecard` and `score` in this file:
one validated row per attribute in `SCORE_ATTRIBUTES` order — attribute, weight,
band, points, points of the weight — added to the total, and the total read
into the scorecard's own band off the first threshold it clears.

    A scorecard is refused by name when the application id is unknown to the
    estate (the estate's own refusal), when the weights do not sum to
    `SCORE_SCALE_BP`, when the estate answers no band for an attribute, when it
    answers an attribute the scorecard does not score, when a band outside the
    policy's own points table arrives, and when a weight is not a whole count
    of basis points.
"""

import policy

POINTS_KEYS = ("id", "scores", "total_bp", "band_bp", "band")

SCORE_ATTRIBUTES = ("dsr", "stability", "history", "collateral")

SCORE_SCALE_BP = 10000

_BP = SCORE_SCALE_BP

SCORECARD_ERROR = "scorecard: "


class ScorecardError(ValueError):
    """The refusal this stage raises: something that cannot be a points record.

    It names the offender — the attribute the estate answers no band for, the
    attribute the estate answers *besides* the ones the card scores, the band
    outside the policy's own points table, the weight table that does not sum
    to the whole, and a weight that is not a whole count of basis points —
    because a score the committee cannot re-add from its own rows is a score
    nobody signs.
    """


def scorecard(cases, id):
    """The weighted table, added up, as a `POINTS_KEYS` record.

    The estate's band facts for the application are validated whole against the
    policy's own tables, then one row is answered per attribute, in
    `SCORE_ATTRIBUTES` order: `(attr, weight_bp, band, points_bp,
    attribute_bp)`, where `attribute_bp` is points of the weight —
    `weight_bp * points_bp // 10000`, truncating. `total_bp` is the rows' sum,
    `band_bp` and `band` are the first threshold the total clears on the
    scorecard's own descending table.

    A weight table that does not sum to `SCORE_SCALE_BP`, an attribute the
    estate answers no band for (or answers *besides* the card's own), a band
    outside the policy's points table, or a weight that is not a whole count
    of basis points is refused by name, and no record is answered. An unknown
    application id is the estate's own refusal.
    """
    raise NotImplementedError("stage 2: implement scorecard()")


def score(cases, id):
    """The total the table answers: the whole scorecard, in one number.

    The same validated facts, the same rows, the same truncated sum — the
    scorecard's answer without its record. What the band makes of the total is
    the record's question; the total is the number the band reads.

    The same refusals as `scorecard` apply, by the same names.
    """
    raise NotImplementedError("stage 2: implement score()")
