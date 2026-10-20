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


def _whole(value, what):
    """A whole count of basis points, or the refusal naming the field."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScorecardError(SCORECARD_ERROR + ("%s is not a whole count of basis "
                                                "points: %r is a %s"
                                                % (what, value,
                                                   type(value).__name__)))
    return value


def _bands(cases, id):
    """The estate's own band facts for one application, checked in full.

    The facts are the estate's; the scoring vocabulary is the policy's. The
    whole validation runs before one row exists — an attribute no band reaches,
    an attribute that is not on the card, a band outside the policy's own
    points table, a weight that is not a whole count of basis points, and a
    weight table that does not sum to the whole are all refused by name here,
    so a refused attribute leaves no row behind to be half-added.

    An unknown application id is the estate's own refusal, raised at the door
    before anything is checked.
    """
    answer = cases.scorecard_bands(id)
    for attr in answer:
        if attr not in SCORE_ATTRIBUTES:
            raise ScorecardError(SCORECARD_ERROR + ("the estate answers a %r band, "
                                                    "and the card scores only %r"
                                                    % (attr, SCORE_ATTRIBUTES)))
    weights = policy.SCORE_WEIGHTS_BP
    points = policy.SCORE_POINTS_BP
    total_weight = 0
    for attr in SCORE_ATTRIBUTES:
        if attr not in answer:
            raise ScorecardError(SCORECARD_ERROR + ("the estate answers no %r "
                                                    "band for %r" % (attr, id)))
        band = answer[attr]
        if band not in points[attr]:
            raise ScorecardError(SCORECARD_ERROR + ("the band %r is not one the "
                                                    "policy scores the %r "
                                                    "attribute in %r"
                                                    % (band, attr,
                                                       tuple(sorted(points[attr])))))
        total_weight = total_weight + _whole(weights[attr],
                                             "the weight of the %r attribute"
                                             % (attr,))
    if total_weight != SCORE_SCALE_BP:
        raise ScorecardError(SCORECARD_ERROR + ("the weights sum to %d, not to "
                                                "the %d a weighted table is "
                                                "held to"
                                                % (total_weight, SCORE_SCALE_BP)))
    return answer


def _rows(bands):
    """One weighted row per attribute, in `SCORE_ATTRIBUTES` order.

    `attribute_bp` is points of the weight — `weight * points // 10000`,
    truncating, the card's own division at the scale the contract pins. The
    rows are a tuple in `SCORE_ATTRIBUTES` order, so an attribute scored twice
    (or a record that reorders itself) is a shape the record's own shape
    refuses, not a summary it hides.
    """
    rows = []
    for attr in SCORE_ATTRIBUTES:
        band = bands[attr]
        weight = policy.SCORE_WEIGHTS_BP[attr]
        points = policy.SCORE_POINTS_BP[attr][band]
        attribute_bp = weight * points // _BP
        rows.append((attr, weight, band, points, attribute_bp))
    return tuple(rows)


def _band_of(total_bp):
    """The scorecard's own band: the first threshold the total clears, walking down.

    `SCORE_BANDS` is written in descending threshold order and a total answers
    the first threshold it clears — `total >= threshold`, the threshold that is
    its own `band_bp`. A total below every threshold answers the last band,
    never an error: a band is a fact about the total, and the last row's own
    threshold travels with the band as the record's `band_bp`.
    """
    for threshold, band in policy.SCORE_BANDS:
        if total_bp >= threshold:
            return threshold, band
    threshold, band = policy.SCORE_BANDS[-1]
    return threshold, band


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
    bands = _bands(cases, id)
    rows = _rows(bands)
    total_bp = 0
    for row in rows:
        total_bp = total_bp + row[-1]
    threshold, band = _band_of(total_bp)
    return {"id": id, "scores": rows, "total_bp": total_bp, "band_bp": threshold,
            "band": band}


def score(cases, id):
    """The total the table answers: the whole scorecard, in one number.

    The same validated facts, the same rows, the same truncated sum — the
    scorecard's answer without its record. What the band makes of the total is
    the record's question; the total is the number the band reads.

    The same refusals as `scorecard` apply, by the same names.
    """
    return scorecard(cases, id)["total_bp"]
