"""Credit Origination From Scratch — stage 4: The rating and the hard gates.

The scorecard answers what the application scores; the rating answers what the
bank calls it. Two things stand between a band and the name the credit committee
writes down: the policy's `GRADE_OF` table, which assigns the scorecard's band a
grade out of M1's own alphabet, and the policy's `GATES`, the questions a score
is never asked — a prior default, a bankruptcy — whose answers the estate keeps
as history flags, not as scorecard facts. A gate is a decline no score passes:
when one fires, the record answers `"F"` and says who ordered it, and the
scorecard's own answer stays on the record beside it so a reviewer can see both
the verdict and what it overruled.

    RATING_KEYS                     the seven fields of a rating record, in order
    RatingError                     the refusal this stage raises
    rating(cases, id)               -> RATING_KEYS: the score, the band, the
                                       grade the policy assigns, the gate that
                                       fired, and whether the grade was the
                                       band's own or the gate's

DESIGN DECISION — why does `rating` take the estate, the way stage 2's
`scorecard` does?
Because the record is answered *for* an application the stage was handed, and a
refusal is only checkable against a ledger the stage was actually given: the
estate's counters can prove what a refused call asked, only if the same estate
the call went through is the one the record is built on. The contract's stage-4
row wrote `rating(id)` before the course first ran; the stage-6 amendment
settled the same question for the limit — *the estate handed to it, the way
stage 1's `affordability(cases, id)` is* — and this stage follows that shape,
like stage 2's delivered `scorecard(cases, id)` before it.

DESIGN DECISION — why are the gates answered off the history door, in the
policy's `GATES` order, and not off the scorecard?
Because a gate is a fact about the applicant's past — `prior_default`,
`bankruptcy` — that no table of points can speak for, and the policy pins both
the questions (`GATES`) and their order. The stage walks `GATES` and answers the
*first* gate that fires; a later gate burning while an earlier one already
answered the record would make the reasons line name a gate the policy did not
ask first. Each gate's own field is the gate's name with underscores where the
policy writes hyphens, so the stage carries no second vocabulary of gate names:
reorder `GATES`, and the stage reorders with it.

DESIGN DECISION — why does the gated record keep its score, and answer `"F"`
anyway?
Because the gate and the scorecard are two different opinions, and the record
their disagreement produces must carry both: `grade` "F" is the opinion the
policy forced, `score_bp` and `band` are the opinion the card reached before it
was overruled. A gate that overwrites the score leaves the committee a record
that cannot show what the applicant's own card said — the reasons line stage 8
cites both "rating" and "gate", and a rating that swallowed its own score could
not tell the two apart. The score is still visible; it just did not win.

DESIGN DECISION — why is the ungated grade read off `policy.GRADE_OF` and never
off the band's own letter?
Because a band and a grade are two vocabularies the policy happens to spell
alike today, and a stage that passes the band through as the grade has hardwired
the table's current entries into its arithmetic. `GRADE_OF` is the policy's
decision — identity here by design — and the stage uses the table whatever its
entries say: move the table, and the grade moves with it, the way the band moved
with the thresholds in stage 2. What the policy did not spell — a band no
`GRADE_OF` row answers — is refused, not guessed.

DESIGN DECISION — why does an ungated rating answer `voluntary` True and `why`
empty, and never a refusal?
Because the record's last two fields are the gate's story, and a gate that never
fired has none: `voluntary` True means the applicant was graded by their own
band with nobody's hand on it, and an empty `why` means there is no gate to
name. A passed gate is never reported as fired — the shape a passed gate would
take is the ungated shape — and a refusal for the ordinary case would make
every clean applicant's rating an exception. The `why` line a decline letter
reads is stage 8's to write; this stage hands over the gate's name and stops.
"""

import policy
import stage_02

RATING_KEYS = ("id", "score_bp", "band", "grade", "gate", "voluntary", "why")

RATING_ERROR = "rating: "

#: The grade the policy answers for an application its own gate caught: `"F"`,
#: not the band's own letter, whatever the scorecard said.
_FORCED_GRADE = "F"

#: Whoever caught the applicant owns the grade: a fired gate is the opposite of
#: voluntary, and a clean history is the band's own choice.
_VOLUNTARY = True

_FORCED = False

#: An ungated record cites nothing: the gate is empty, the why is empty.
_NO_GATE = ""

_UNSaid = ""


class RatingError(ValueError):
    """The refusal this stage raises: an application that cannot be rated.

    It names the offender — the gate whose history field is missing, the gate
    whose history field is not a yes-or-no answer, the band the policy assigns
    no grade to — because a rating the committee cannot trace back to the
    policy's own two tables is a rating nobody signs.
    """


def _flag_of(gate):
    """The history field a gate is answered on: the gate's name, underscores in."""
    return gate.replace("-", "_")


def _fires(history, id, gate):
    """The gate's own answer, from the history the estate keeps.

    The gate's field is the gate's name hyphens-for-underscores, and a history
    that names no such field — or answers it with anything but a decision —
    is refused by name, the gate and the field both, before any grade is
    answered. A gate is a yes-or-no question; a maybe is not an answer.
    """
    flag = _flag_of(gate)
    if flag not in history:
        raise RatingError(RATING_ERROR + ("%r carries no %r field, and the %r "
                                          "gate is answered on it" % (id, flag,
                                                                      gate)))
    answer = history[flag]
    if isinstance(answer, bool) is False:
        raise RatingError(RATING_ERROR + ("the %r field in %r's history answers "
                                          "%r, not a yes-or-no the %r gate can "
                                          "be decided on" % (flag, id, answer,
                                                             gate)))
    return answer


def _gate_of(history, id):
    """The first gate the policy's order sees fire, or the empty pass.

    The gates are the policy's, in the order the policy pins them in: the
    earlier gate is answered first, and the first gate that fires is the one
    the record names. An application every gate passes answers the empty gate
    — a pass is a fact the reasons line leaves out, not a gate worth naming.
    """
    for gate in policy.GATES:
        if _fires(history, id, gate):
            return gate
    return _NO_GATE


def _grade_of(band):
    """The grade the policy assigns the band, off the policy's own table.

    `GRADE_OF` is one opinion about a band, whatever its entries are: the stage
    reads the row and refuses to guess one for a band the table does not carry,
    because a grade found anywhere but the policy's own table is a grade the
    bank did not assign.
    """
    if band not in policy.GRADE_OF:
        raise RatingError(RATING_ERROR + ("the policy assigns no grade to the "
                                          "band %r, and the scorecard answers "
                                          "it" % (band,)))
    return policy.GRADE_OF[band]


def rating(cases, id):
    """The score, the band, and the grade the bank assigns, as a `RATING_KEYS`
    record.

    The scorecard's own answer — stage 2's total and the band it reads into —
    travels onto the record whatever happens next: `score_bp` is stage 2's
    total, `band` is stage 2's band, and the gates read off
    `cases.history(id)` decide what they are worth. In the policy's `GATES`
    order, the first gate whose history flag fires takes the record: `grade`
    answers `"F"`, `gate` and `why` name it, and `voluntary` answers False —
    the applicant was forced to their grade. An application no gate fires is
    graded by its band off the policy's `GRADE_OF` table: `gate` and `why` are
    empty, `voluntary` answers True, and the grade is the band's own, at the
    table's word.

    An unknown application id is the estate's own refusal, and a gate whose
    history field is missing or is not a yes-or-no answer is refused by name
    before any grade is answered.
    """
    history = cases.history(id)
    gate = _gate_of(history, id)
    scorecard = stage_02.scorecard(cases, id)
    score_bp = scorecard["total_bp"]
    band = scorecard["band"]
    if gate:
        return {"id": id, "score_bp": score_bp, "band": band,
                "grade": _FORCED_GRADE, "gate": gate, "voluntary": _FORCED,
                "why": gate}
    return {"id": id, "score_bp": score_bp, "band": band,
            "grade": _grade_of(band), "gate": _NO_GATE,
            "voluntary": _VOLUNTARY, "why": _UNSaid}
