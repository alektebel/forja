"""Credit Lifecycle From Scratch — stage 8: The provision roll-forward, line by line.

Two reporting dates and one number that moved between them: a bank's provision is never
explained by `closing − opening`, because that arithmetic answers *how much* and the
supervisor asks *why*. This stage is that why, decomposed into the nine movements a
provision actually has — loans that left, loans that arrived, loans that changed stage,
a model that changed, a scenario weighting, the passage of time, write-offs, recoveries —
and one honest line, `other`, for the part the first nine do not explain.

The decomposition is a waterfall and its order is the contract's, not a preference: at
each step one thing moves and everything else is held at the value the step before it
left. The stage-transfer line is therefore measured at the *end* date, under the *old*
model, in the base scenario, with the end stage against the start stage; the parameter
line then swaps the model at the end stage; the scenario line adds the weighting; and the
unwind carries the passage of time on the opening provision at the loan's own period
rate. Each of the nine lines is a sum of per-loan movements, so a line is never a
difference of totals that no loan owns.

The closing is *recomputed* and never obtained by adding the lines, and the lines are
held against it. That is the whole discipline of the stage: `closing_cents` is the total
provision at `end`, `other` is what the nine lines above it failed to explain, and
`difference_cents` is the gap between the two — which is zero exactly when the lines are
complete. A record that balances by construction has hidden its own gap; this one prints
it.

The P&L / OCI split is not a second calculation. Every line's cents already belong to a
loan, and a loan's `measured_at` says which side of the bank's income statement its money
lands on: `amortised-cost` is P&L, `fvoci` is OCI. So the split is a partition of the same
money — the same cents, counted on the other axis — and `opening_cents + pl_cents +
oci_cents` reaches `closing_cents` exactly as far as the lines do.

    ROLLFORWARD_KEYS    the eight fields of a roll-forward, in order
    LINES               the nine movements, in the order the record prints them
    rollforward(book, start, end) -> ROLLFORWARD_KEYS between two reporting dates

DESIGN DECISION — why is the closing recomputed rather than summed from the lines?
Because a sum of the lines is a restatement of the lines, not a fact: any gap the
decomposition cannot explain would vanish into the total and the report would be a
tautology. So `closing_cents` is the book's total provision at `end`, recomputed from the
loans the book holds at `end`, and the ten lines are held against it — the ninth of them,
`other`, being precisely what is left. The two are allowed to disagree, they just do not
here, and `difference_cents` is the field that says so.

DESIGN DECISION — why does `other` exist instead of being folded into a neighbour?
Because a provision movement a bank cannot explain is a fact about its report, and the
honest place for it is a line of its own with its own `why`, not a rounding difference
added to the parameter or the scenario line where nobody will see it. Folding it in makes
the deck look complete and the decomposition untrue; printing it invites exactly the
question a supervisor would ask. This stage refuses to decide whether the residual is
acceptable — that is a business question — it only refuses to hide it.

DESIGN DECISION — why is the P&L/OCI split a partition rather than a second calculation?
Because the two axes describe the same money: the movement is the same cents whether they
are read by *what caused it* or by *where it landed*. A second calculation would be a
second chance to disagree with the first, so the split is taken from the loans that own
each line — `measured_at` is the loan's own measurement election and the only thing that
decides the side — and the reader can add either axis up and reach the same closing.

DESIGN DECISION — why is `unwind` measured on the opening provision and not on the closing?
Because the passage of time is the interest the provision earned *while it was there*, and
at the start of the window that is the only provision there was. Measuring it on the
closing balance would let the other movements pay interest they never earned — the
parameter change would be unwound as if it had been outstanding for the window — and
measuring it on the exposure would unwind a number the bank does not discount. So it is
`Σ ecl(start) * period_rate_bp // 10000` over the months between the two dates, one loan
at a time, at each loan's own period rate, and nothing else accrues.

TODO: implement `rollforward` in this file: the two dates' loan sets, the nine movements
in `LINES` order each with its own `why`, the P&L/OCI split of the same cents by the
loans' `measured_at`, the recomputed closing, and `other` as the residual — refusing with
`BookError` on a start after an end, a date the book does not cover, and a loan whose
stage the book records inconsistently.
"""

import dates
import rules
import stage_01
import stage_06
from book import BookError, LAST_REPORTING_DATE, REPORTING_DATES

ROLLFORWARD_KEYS = ("start", "end", "opening_cents", "lines", "pl_cents", "oci_cents",
                    "closing_cents", "difference_cents")

LINES = ("derecognitions", "new-business", "stage-transfers", "parameter", "scenario",
         "unwind", "write-offs", "recoveries", "other")


def rollforward(book, start, end):
    """The provision's movement between two reporting dates, line by line.

    `opening_cents` is the total provision at `start` and `closing_cents` the total at
    `end`, each recomputed from the loans the book holds at that date. `lines` is one
    `(line, cents, why)` entry per name in `LINES`, in that order: `derecognitions` (the
    opening provision of the loans no longer on the books at `end`), `new-business` (the
    provision of the loans that arrived), `stage-transfers` and `parameter` and `scenario`
    (the waterfall at `end` over the loans in both dates, in the base scenario and under
    the model in force at each date), `unwind` (the opening provision of every loan the
    book held at `start` accreted over the months between the dates at that loan's own
    effective rate), `write-offs` (the provision the loans written off in the window last
    had on the book) and `recoveries` (the flows collected against the written-off stock),
    and `other` (whatever the eight before it left unexplained). `pl_cents` and `oci_cents`
    are the same cents split by each loan's `measured_at`, and `difference_cents` is
    `closing_cents` less the opening and the nine lines — zero when the decomposition is
    complete.

    A start after the end, a date outside the book's own reporting dates, a loan whose
    stage the book records inconsistently, or a loan whose `measured_at` is neither
    `amortised-cost` nor `fvoci`, raises `BookError` naming the offender.
    """
    raise NotImplementedError("stage 8: implement rollforward()")
