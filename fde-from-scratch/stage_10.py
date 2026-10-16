"""FDE From Scratch — stage 10: Shadow traffic and a verdict.

A generic benchmark convinces nobody: it was not their tickets, not their
invoices and not their customers. So the candidate model is put on the
customer's own cases — and while it is there it must be *invisible*. Shadow
traffic is the discipline of measuring a model without letting it answer
anybody: every case goes to the incumbent and to the candidate, the user keeps
seeing what the user always saw, and the candidate's answer is filed beside the
incumbent's instead of being served. The first thing this stage can prove is
the one thing that must never happen: nothing the candidate answered reached
the user.

The second half is the part an eval project usually skips. A score is a
measurement, and a measurement is only as good as its instrument and its
sample: `grade` counts a model's accuracy over the cases that model *answered*
(a model that skipped the hard cases does not get to call them correct, and it
does not get them in its denominator either), `calibrate` measures the judge
itself against a sample a human labelled, and `verdict` refuses to decide until
the judge is trustworthy and the sample is large enough — before it looks at
the number everybody wanted to ship on.

    CASE_KEYS                          a customer case: its id, team, text, expected answer, class
    SHADOW_KEYS                        a shadow row: the case, both models' answers, what the user saw, whether they agreed
    GRADE_KEYS                         one model's marks: correct, total answered, accuracy in basis points
    AGREEMENT_KEYS                     the judge's calibration: agree, disagree, agreement in basis points
    VERDICTS                           the three words a verdict can be: "ship", "hold", "reject"
    VERDICT_REASONS                    why it is that word: "below-target", "judge-unreliable", "sample-too-small", "candidate-worse"
    MIN_SAMPLE                         the smallest sample a verdict may be based on
    MIN_AGREEMENT_BP                   the agreement a judge must reach before its verdicts count
    EvalError                          the shape refusal of this stage, a kind of estate.EstateError
    shadow(cases, incumbent, candidate, replay) -> tuple of SHADOW_KEYS, in case order
    grade(rows, cases) -> tuple of GRADE_KEYS, sorted by model
    calibrate(judge, labelled) -> AGREEMENT_KEYS
    verdict(grades, agreement, sample, target_bp) -> (verdict, reason or None)
    user_visible(rows) -> (case id, answer) per case, in case order

`shadow` calls `incumbent`, `candidate` and `replay` once per case, with the
case's own `text`, and each answers a string or `None` for a case it did not
answer. `grade` marks the two models against the labelled sample it is handed;
`calibrate` marks the judge against the labels a human wrote; `verdict` turns
both marks and a sample size into one of `VERDICTS` and, when the answer is not
a clean ship, into one reason from `VERDICT_REASONS`.

DESIGN DECISION — why does `user_sees` record the replay's answer and not the
candidate's?
Because a shadow run that leaks is worse than no eval at all: the candidate is
unproven, and the customer's users would be the ones finding out. So the row
does not merely *claim* the user was served by the incumbent — it carries the
answer the replay actually produced, which is the third callable's own answer
and never a copy of whatever the candidate said. A run whose `user_sees` equals
the candidate's answer is a run that served the candidate, and no amount of
accuracy makes that acceptable.

DESIGN DECISION — why is the accuracy denominator the cases a model answered,
and not the labelled sample?
Because the two are different questions, and only one of them is honest. Over
the labelled sample, a model that answered the four easy cases and skipped the
two hard ones is scored on six and punished for work it never did; over the
cases it answered, it is scored on four and the skipped cases are visible in
`total`, where a reader can see that the denominator moved. A model that
answered nothing is `total` 0 and `accuracy_bp` 0: the sample it was measured
on is empty, and an empty sample has no accuracy to report.

DESIGN DECISION — why are the judge's reliability and the sample size decided
before the target is consulted?
Because a decision has to be able to say "not yet" before it says "no". If the
target were consulted first, a candidate that missed it would come back
`reject` on a judge nobody calibrated and twenty cases nobody can generalize
from — a confident wrong answer, which is the expensive kind. Judge first (the
instrument), sample second (the measurement), target last (the comparison): a
verdict is only as trustworthy as the weakest thing it rests on.

DESIGN DECISION — why does a judge that gave no verdict count as a
disagreement rather than being skipped?
Because a judge that abstains on the cases it is unsure about would otherwise
look better the more it abstains: skip the misses and the agreement rises
toward certainty. The labelled sample is the denominator, the judge was asked
about every case in it, and "I have no verdict" is not an agreement with the
human's label — it is a failure to reach one, and it is counted as one.

DESIGN DECISION — why does `verdict` return a reason rather than a bare word?
Because "hold" means nothing on its own. The person who has to decide whether
to spend another two weeks needs to know which of the four things is the
blocker: the candidate is worse than an incumbent that was already good enough,
the whole project is below what the customer asked for, the judge cannot be
trusted, or there is simply not enough evidence yet — and the last two are the
reasons that send you back to collect more rather than back to the drawing
board.

TODO: implement `shadow`, `grade`, `calibrate`, `verdict` and `user_visible` in
this file: the shadow run that serves the replay's answer and files both
models', the marks over the cases a model answered, the calibration of the
judge against a human's labels, the verdict with its precedence, and the list
of what the user actually saw.
"""

import estate

CASE_KEYS = ("id", "team", "text", "expected", "class")

SHADOW_KEYS = ("id", "incumbent", "candidate", "user_sees", "same")

GRADE_KEYS = ("model", "correct", "total", "accuracy_bp")

AGREEMENT_KEYS = ("agree", "disagree", "agreement_bp")

VERDICTS = ("ship", "hold", "reject")

VERDICT_REASONS = ("below-target", "judge-unreliable", "sample-too-small",
                   "candidate-worse")

MIN_SAMPLE = 30

MIN_AGREEMENT_BP = 8000


class EvalError(estate.EstateError):
    """An eval this course cannot run: a shape that is not the shape it takes."""


def shadow(cases, incumbent, candidate, replay):
    """Two models on the customer's own cases, and what the user actually saw."""
    raise NotImplementedError("stage 10: implement shadow()")


def grade(rows, cases):
    """The two models' marks on the customer's cases, sorted by model."""
    raise NotImplementedError("stage 10: implement grade()")


def calibrate(judge, labelled):
    """How far the judge can be trusted, against a sample a human labelled."""
    raise NotImplementedError("stage 10: implement calibrate()")


def verdict(grades, agreement, sample, target_bp):
    """The one-word answer, with the reason it is that word."""
    raise NotImplementedError("stage 10: implement verdict()")


def user_visible(rows):
    """`(case id, answer)` per case, in the cases' own order: what the user saw."""
    raise NotImplementedError("stage 10: implement user_visible()")
