"""Agentic Retrieval From Scratch — stage 4: The reranker that must earn its place.

Stage 3 answered *which scorer* with the customer's own labelled questions, and it
answered with a measurement rather than an opinion. This stage is the next thing
somebody will ask for, and it is asked for the same way: a reranker is added, and
then somebody has to say whether it helped. The honest answer is not "the reranker
is better" — it is a comparison of two measurements of the *same* questions over
the *same* candidate set, and a threshold below which the difference is not a
difference at all. A reranker that cannot clear that threshold is removed, and
saying so is this stage's output.

The reranker itself is deliberately small and deliberately explainable. It never
looks at the fusion's score; it looks at the query and at the chunk, and it writes
down what it saw: how much of the query the chunk covers, how tightly the query's
terms sit together inside it, and whether the clause is a top-level one. Those
three numbers are the hit's `signals`, sorted by name, and the score is a fixed
point arithmetic over them and nothing else — so a reader who doubts a rank can
recompute it from the tuple that was printed beside it, and a check can too.

The measurement is stage 3's, not this stage's: `before` is literally stage 3's
`measure(..., "hybrid")`, and `after` is the same counting over the same questions
with the reranker in the same place the fusion left it. The only number this stage
adds is their difference, and the only judgement is where that difference falls
against `NOISE_BP` — under it the change is noise, at or above it the reranker has
earned its place. `keep` is that verdict spelled as a decision for the person who
has to decide.

    RERANK_KEYS          the three fields of a reranked hit, in order
    COMPARE_KEYS         the four fields of the verdict, in order
    COVERAGE_WEIGHT      what the coverage carries of a rerank score, out of WEIGHT_TOTAL
    PROXIMITY_WEIGHT     what the proximity carries of it
    WEIGHT_TOTAL         what the two weights add up to
    PROXIMITY_WINDOW     how near another distinct query term has to be, in positions
    LEVEL_BONUS_BP       what a top-level clause's own level is worth, in basis points
    NOISE_BP             a coverage gain below this many basis points is noise
    rerank(index, query, hits, limit)   -> the hits, rescored and reordered
    compare(index, questions, limit)    -> COMPARE_KEYS: hybrid against hybrid-reranked
    keep(index, questions, limit)       -> "keep" | "remove"

DESIGN DECISION — why is the reranker shown everything the fusion scored, rather
than the page the caller asked for?
Because a reranker that only ever sees the page the fusion already chose can only
reorder that page, and a reordering of a fixed set cannot change `hit_bp` — the
measurement would come back identical every time and the stage would be theatre.
The reranker's whole claim is that it can look further down than the page and pull
something better to the top, so `compare` hands it the *whole* fused ranking (the
same `search`, at the index's own size) and cuts the result to the caller's limit.
The measurement's limit never moves: both sides are counted over the `limit` the
caller asked for, which is why the comparison is about the reranker and not about
how deep somebody fetched.

DESIGN DECISION — why is a rerank score an int built from named signals rather
than the fusion's own score?
Because a score that cannot be recomputed from what was printed beside it is a
number the reader has to trust, and this course exists so that a rank can be
doubted and checked. The fusion's score is not carried in at all: coverage,
proximity and the level bonus are each an int in basis points, the score is
`coverage * COVERAGE_WEIGHT // WEIGHT_TOTAL` plus the same for proximity plus the
bonus, and the `signals` tuple is sorted by name so that two answers with the same
numbers read the same. Everything is a fixed-point division with the scale written
out — no float literal exists anywhere in this course.

DESIGN DECISION — why is the verdict a vocabulary of three rather than the delta
itself?
Because the caller is deciding whether to keep the reranker, and "the delta is
plus a hundred and eighty basis points" is not a decision. `NOISE_BP` is the same
threshold idea stage 3 used for its two scorers: a gain below it is inside the
noise of a small labelled set and reads `"within-noise"`, a gain at or above it
reads `"earned"`, and a loss reads `"hurt"`. The three are the whole vocabulary,
the comparison is the only place they are decided, and `keep` is nothing more than
`"earned"` spelled for somebody who wants a plain answer.

DESIGN DECISION — why is proximity a share of distinct terms that have a neighbour,
rather than a distance?
Because a distance is unbounded and a score is not. The window is a fixed number
of positions, a term counts once however many times it occurs, and it counts only
if *another distinct query term* sits within that window of one of its occurrences
— so a chunk that says one query term twelve times has perfect coverage and no
proximity at all, and a neighbour that is merely the same word again is not a
neighbour. The comparison is `<=` the window, because a window of twelve positions
that excluded the twelfth would be a window of eleven wearing a twelve's name. A
chunk that covers nothing answers `0` rather than dividing by zero.

DESIGN DECISION — why is the level bonus paid to one level only?
Because it is not a measure of importance — it is the one structural fact the
customer's lawyers printed, and stage 1 is where it was recorded: a clause opening
`1.` is the outermost clause of its document, and a clause opening `1.1` or
`1.1(a)` is inside one. Paying it to every level is paying it to every chunk and
therefore paying it to none; paying it to the outermost level only is a small tie
break in favour of the clause a reader would find first, and it is a constant
(`LEVEL_BONUS_BP`) rather than a taste.

TODO: implement `rerank`, `compare` and `keep` in this file: the cross-scorer whose
score is the sum of its own printed signals, the comparison of stage 3's own
measurement against the same measurement with the reranker in it, and the plain
decision that comparison implies.
"""

import stage_03

RERANK_KEYS = ("chunk", "score", "signals")

COMPARE_KEYS = ("before", "after", "delta_bp", "verdict")

COVERAGE_WEIGHT = 3

PROXIMITY_WEIGHT = 2

WEIGHT_TOTAL = 5

PROXIMITY_WINDOW = 12

LEVEL_BONUS_BP = 500

NOISE_BP = 200


def rerank(index, query, hits, limit):
    """The hits, rescored from their own signals and reordered, cut to `limit`.

    `query` is the question's own text; `hits` are stage 3's hits
    (`HIT_KEYS` records), and `index` is the stage 3 index they came from — it
    answers `terms(text)` with the customer's own analyzer, and `of(chunk_id)`
    with the chunk a hit names. Every hit is a mapping naming a chunk the index
    holds, or the refusal names the offender before anything else happens.

    For each hit, `signals` is a tuple of `(name, int)` pairs sorted by name —
    `("coverage", coverage_bp)`, `("level-bonus", LEVEL_BONUS_BP if the chunk's
    level is the outermost one else 0)` and `("proximity", proximity_bp)` — where
    `coverage_bp` is the basis-point share of the query's *distinct* analyzed terms
    that the chunk's text holds (`0` when the query has no terms) and
    `proximity_bp` is the share of those covered terms that have another distinct
    covered term within `PROXIMITY_WINDOW` positions of one of their occurrences in
    the chunk's token list (`0` when nothing is covered).

    `score` is `coverage * COVERAGE_WEIGHT // WEIGHT_TOTAL` plus
    `proximity * PROXIMITY_WEIGHT // WEIGHT_TOTAL` plus the level bonus, so it is
    recomputable from `signals` alone. The ranking is by score descending, a tie
    keeps the input order (which is stage 3's, already broken by chunk id), and the
    answer is cut to `limit`.
    """
    raise NotImplementedError("stage 4: implement rerank()")


def compare(index, questions, limit):
    """The measurement without the reranker against the measurement with it.

    `before` is stage 3's own `measure(index, questions, limit, "hybrid")`;
    `after` is the same counting, by stage 3's own `answered`/`hit_bp`/`missed`
    rules, over each question's retrieval with the reranker applied to the whole
    fused ranking and cut to the same `limit`. `delta_bp` is
    `after["hit_bp"] - before["hit_bp"]`, and `verdict` is `"hurt"` when the delta
    is negative, `"within-noise"` when it is below `NOISE_BP`, and `"earned"` when
    it reaches it. A question that cannot be measured is refused, naming it.
    """
    raise NotImplementedError("stage 4: implement compare()")


def keep(index, questions, limit):
    """`"keep"` exactly when `compare` says `"earned"`, and `"remove"` otherwise.

    The same comparison, answered as the decision somebody actually has to make:
    a reranker inside the noise was not shown to help, and a reranker that hurt was
    shown to hurt, so only a gain that reaches `NOISE_BP` earns its place.
    """
    raise NotImplementedError("stage 4: implement keep()")
