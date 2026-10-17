"""Agentic Retrieval From Scratch — stage 9: What the checking cost, against the naive answer.

The last stage before the customer's own failures. A pipeline that checks itself
has to be worth what the checking cost, and the null hypothesis it has to beat is
the pipeline nobody would write a book about: retrieve the hybrid top `limit` and
answer from all of it. No critique, no rewrite, no abstention — the naive row
cannot abstain, because there was never a gate for it to fail, so its `answered`
is every question it was shown.

Against it stands the loop of stage 8, priced round by round out of the meter's own
log. The checked row's `answered` is the questions it did not abstain on, and its
coverage is measured over what its answers cite: an abstention cites nothing, which
is the honest way for checking to lose coverage it never had.

Nothing here is a model of the customer's business. The two rows are counts of
questions and basis points of coverage, and the verdict between them is a
comparison of one number against another with the noise floor the plan pinned.
`where_it_lost` is the part an average would have hidden — the questions where the
checked pipeline paid more and handed over no more of what was expected.

The surface:

    BASELINE_KEYS         one row of the comparison: its kind, its cents, its answers,
                          its coverage
    ROLLUP_KEYS           the two rows added up: cost, answers, cents per answer, and
                          the two deltas
    MIN_WORTH_IT_GAIN_BP  the coverage gain, in basis points, that checking has to
                          reach to have paid for itself
    price                 both pipelines over one question set, the naive row first,
                          each row priced by the meter it was handed
    rollup                the two rows summed, with `None` cents per answer when
                          nothing was answered
    where_it_lost         the questions the checked pipeline paid more for and brought
                          no more expected ids to the customer
    worth_it              the verdict: worth it, not worth it, or inside the noise

DESIGN DECISION — what is the null hypothesis, and who answers from it?

The naive pipeline is the one without a checking stage: one hybrid retrieval at
`limit`, and one generation that quotes everything the retrieval handed back. It
has no critique to consult, so it never abstains, and no rewrite, so it retrieves
once per question. Its `answered` is therefore `len(questions)` by construction
rather than by luck: an abstention would be a gate it does not have.

DESIGN DECISION — whose number is a row's cost?

The meter's. A row reads `Meter.total_cents()` before it starts and subtracts it
when it is done, so a row's cost is the delta the ledger shows and not an
arithmetic the stage believes. The rows run in the order the contract pins — naive
first, checked second — because a delta means one thing only while the charges are
contiguous.

DESIGN DECISION — what is coverage measured over, row by row?

Stage 3's rule, over the ids each row brings to the customer: expected ids brought
over every expected id, in basis points. The naive row brings what it retrieved —
it has nothing else — and the checked row brings what its answers cite, which is
nothing at all on an abstention. The two numbers are deliberately not the same
measurement: the checked row is charged for the ids it was willing to stand behind.

DESIGN DECISION — where does the tick come from, when `price` is handed no clock?

The question's own position in the list the caller supplied: one call, one tick. A
run is a function of the questions' order — the only order this course has — and the
meter's log can still say which question paid rather than just how much a run paid.

DESIGN DECISION — whose budget is it, when one meter runs many questions?

A price charges one meter for the whole workload, so the caller's `budget_cents` is
the budget of one question's loop: the loop is handed it on top of what the meter
already holds, or the second question would be judged against the first one's
spending. A question whose budget buys no round at all answered nothing and cost
nothing — a price is not a promise that every question was looked at.

DESIGN DECISION — what does a price over no questions answer?

Two rows of zeros, a rollup of `None` cents per answer rather than a division by
nothing, no charges at all in the meter, and an empty `where_it_lost`. `worth_it`
on those rows is `"within-noise"`: the checked pipeline neither cost more nor
covered more, which is exactly what a comparison of nothing to nothing says.

TODO: implement `BASELINE_KEYS`, `ROLLUP_KEYS`, `MIN_WORTH_IT_GAIN_BP`, `price`,
`rollup`, `where_it_lost` and `worth_it`.
"""

import stage_01
import stage_03
import stage_07
import stage_08

BASELINE_KEYS = ("kind", "cost_cents", "answered", "hit_bp")
ROLLUP_KEYS = ("cost_cents", "answered", "cents_per_answer", "delta_cents",
               "delta_answered")
MIN_WORTH_IT_GAIN_BP = 400


def price(index, corpus, meter, questions, limit, budget_cents, round_cap):
    """Both rows over one question set, the naive pipeline first and the checked second.

    Each row is a `BASELINE_KEYS` record: its `kind`, the cents the meter charged
    while that row ran, how many questions it answered, and the share of every
    expected id it brought to the customer, in basis points. The meter is never
    reset — a row's cost is its own delta — and the tick of a question's charges is
    its position in `questions`. A `questions` that is not a tuple of question
    records, or a `limit` that is not a count of hits, is refused by name. The
    budget is one question's, and a question whose budget buys no round at all
    answered nothing.
    """
    raise NotImplementedError("stage 9: implement price()")


def rollup(rows):
    """The two `BASELINE_KEYS` rows added up, in `ROLLUP_KEYS` order.

    `cost_cents` and `answered` are the two rows' sums; `cents_per_answer` is what
    one answer cost over both rows and `None` when nothing was answered at all;
    `delta_cents` and `delta_answered` are the checked row's minus the naive one's.
    Anything but exactly the two rows of a price, naive first, is refused by name.
    """
    raise NotImplementedError("stage 9: implement rollup()")


def where_it_lost(index, corpus, meter, questions, limit, budget_cents, round_cap):
    """The qids the checked pipeline paid more for and answered no better.

    One entry per question, in the questions' own order: the checked row charged
    more cents for it than the naive row did, and its answers brought the customer
    no more of the question's expected ids than the naive row's retrieved hits did.
    Priced the way `price` prices both rows, against the meter it was handed.
    """
    raise NotImplementedError("stage 9: implement where_it_lost()")


def worth_it(rows):
    """The verdict on the checked row against the naive one.

    `"within-noise"` when the checked row's `hit_bp` is within
    `MIN_WORTH_IT_GAIN_BP` of the naive one's either way; `"worth-it"` when it is at
    least that much better *and* answered no fewer questions; `"not-worth-it"`
    otherwise.
    """
    raise NotImplementedError("stage 9: implement worth_it()")
