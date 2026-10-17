"""Agentic Retrieval From Scratch — stage 2: Ten million documents, and the index that is a decision.

Ten million documents are a number before they are a system, and this stage is
the arithmetic that number forces. Before anything can be retrieved, the corpus
is an estate — clauses, terms, postings, vectors, and the bytes all of it weighs
— and the estate's own numbers are the only numbers that matter. `corpus.SCALE`
is the customer's answer to how big their corpus is, and every figure a plan
reports is that scale's arithmetic, recomputed rather than believed.

The estate does not fit as one flat index, and not every plan fits its budget. A
flat index pays one dictionary and every vector, and a query scans all of it.
Sharding by document pays a dictionary per shard and scans only its own shard:
memory bought with memory, spent on the scan. A two-tier layout keeps the
dictionary whole and pays vectors only for the hot clauses, so memory drops and
a query still touches the hot tier whatever it scans. A plan is therefore a
search — over the layouts and the shard counts, keep what the memory budget and
the scan budget both allow, and answer the smallest memory, ties by the order
`LAYOUTS` spells them and then fewest shards.

What happens when nothing fits is the point of the stage. A plan that cannot pay
is not promised and not quietly rounded down: it is returned as
`verdict = "refused"`, with the reason and the offending number, because the
customer is entitled to know which constraint broke and by how much. Memory is
rounded *up* for the same reason — a plan that rounds down is a plan that does
not fit. Both prices are the customer's: indexing is charged per million
postings, a query per million clauses scanned, so the scan a layout buys is also
the cost a query pays.

    LAYOUTS                              the three layouts a plan may choose, in order
    PLAN_PROBLEMS                        the closed vocabulary a refusal is spelled in
    PLAN_KEYS                            the nine fields of a plan, in order
    POSTING_BYTES                        the bytes one posting takes
    TERM_BYTES                           the bytes one dictionary term takes
    VECTOR_BYTES                         the bytes one vector component takes
    BYTES_PER_MB                         the bytes in one megabyte
    POSTINGS_PER_CLAUSE                  the postings one clause contributes
    SCAN_BUDGET_BP                       the widest scan a query may make, in basis points
    MAX_SHARDS                           the most shards a plan may be cut into
    INDEX_CENTS_PER_MILLION_POSTINGS     what a million postings cost to index
    QUERY_CENTS_PER_MILLION_SCANNED      what a million clauses scanned cost to query
    PlanError                            the shape this stage will not accept
    weigh(scale)                         -> the estate's flat figures, as a dict
    bytes_of(layout, shards, scale)      -> the bytes that layout holds, in total
    scan_of(layout, shards, scale)       -> the basis points of the estate a query scans
    plan(scale, budget_mb)               -> PLAN_KEYS, the cheapest layout that pays
    explain(plan)                        -> the (claim, number) pairs the plan rests on

DESIGN DECISION — why is memory rounded up rather than to the nearest megabyte?
Because a plan is a promise about what will fit, and a promise rounded down is
a promise the machine cannot keep. `memory_mb` is the ceiling of the estate's
bytes over a megabyte, so a plan whose true weight is 5997 megabytes and a
fraction is reported as 5997 and only fits a budget of 5997 or more. A caller
who rounds down saves a megabyte on paper and watches the index spill in
production; the arithmetic here is deliberately unkind.

DESIGN DECISION — why does sharding pay a dictionary per shard?
Because that is the price of sharding and this stage refuses to hide it. A
sharded index scans only its own shard, which is what the scan budget wants, but
each shard needs its own term dictionary to answer a query at all, and the plan
shows the whole bill rather than a per-shard average a reader would have to
multiply back out. The tension is the design: more shards buy a narrower scan
and cost more memory, so the plan searches rather than assumes.

DESIGN DECISION — why is the layout chosen by memory while the scan is a
separate budget?
Because the two are different promises to different people. Memory is what the
customer buys once; the scan is what every query pays forever. A layout that
holds the estate but scans too wide is not a cheaper plan, it is a plan whose
query budget is broken, so both constraints are applied and a plan that fails
either is not kept. Keeping the scan in basis points means query cost is priced
by the same fraction that decides the plan.

DESIGN DECISION — why is a plan that does not fit returned rather than raised?
Because a plan that cannot pay is still a decision, and the useful part of it is
*why*. Raising would say "no" and hide which of the two budgets broke and by how
much; returning `verdict = "refused"` with `("over-budget", memory_mb)` or
`("scan-too-wide", scan_bp)` lets a caller sizes the machine or the query budget
against a number rather than a mood. Only a shape that cannot be a plan at all —
no budget, an estate missing its numbers — raises, because there is nothing to
decide about it.

DESIGN DECISION — why does the search vary the shard count at all?
Because the shard count is the one dial that trades the two budgets against each
other, and leaving it at one would decide the question this stage exists to
answer. `plan` walks every layout cut `1..MAX_SHARDS` ways, keeps only the plans
that pay both budgets, and answers the smallest memory; `MAX_SHARDS` is the
point past which sharding has stopped being worth its dictionaries.

TODO: implement `weigh`, `bytes_of`, `scan_of`, `plan` and `explain` in this
file: the estate's flat figures with memory rounded up, the three layouts' own
bytes and scan shares, the search that keeps only the plans that pay and refuses
the rest by number, and the `(claim, number)` pairs a caller recomputes it from.
"""

import corpus

LAYOUTS = ("flat", "sharded-by-doc", "two-tier")

PLAN_PROBLEMS = ("over-budget", "scan-too-wide")

PLAN_KEYS = ("layout", "shards", "postings", "memory_mb", "scan_bp", "index_cents",
             "query_cents", "verdict", "problems")

POSTING_BYTES = 8
TERM_BYTES = 64
VECTOR_BYTES = 2
BYTES_PER_MB = 1048576
POSTINGS_PER_CLAUSE = 4
SCAN_BUDGET_BP = 2500
MAX_SHARDS = 64
INDEX_CENTS_PER_MILLION_POSTINGS = 40
QUERY_CENTS_PER_MILLION_SCANNED = 60


class PlanError(ValueError):
    """A shape this stage cannot accept, or an estate it will not plan.

    A kind of `ValueError`, which is what the world's own refusals are, so a
    caller that already catches a broken library catches a broken plan too.
    """


def weigh(scale):
    """The estate's flat figures, every one of them an `int`.

    `postings` is the clauses' own postings, `posting_bytes`, `dictionary_bytes`
    and `vector_bytes` are the three bills the estate runs, `bytes` is their sum
    and `memory_mb` is that sum rounded **up** to whole megabytes. `hot_clauses`
    is the share of the clauses the hot tier keeps. The answer is a dict whose
    keys are `("clauses", "terms", "postings", "posting_bytes",
    "dictionary_bytes", "vector_bytes", "bytes", "memory_mb", "hot_clauses")`,
    in that order. A scale missing a key of `corpus.SCALE_KEYS` is refused,
    naming every key it lacks.
    """
    raise NotImplementedError("stage 2: implement weigh()")


def bytes_of(layout, shards, scale):
    """The bytes a layout holds, in total, for an estate cut into `shards`.

    A flat index pays one dictionary and every vector. Sharding by document pays
    a dictionary per shard — that is the whole price of sharding — and still
    every vector. A two-tier layout pays one dictionary and only the hot
    clauses' vectors, whatever the shard count. A layout not in `LAYOUTS`, a
    shard count that is not a whole number of at least one, or an estate missing
    a key is refused, naming the offender.
    """
    raise NotImplementedError("stage 2: implement bytes_of()")


def scan_of(layout, shards, scale):
    """The basis points of the estate a query scans under this layout.

    A flat index scans all of it. Sharding divides that share by the shard count
    and never below a shard's own share. A two-tier layout scans at least the
    hot tier — the hot clauses are always touched — and otherwise the same
    divided share as a sharded one. The same three shapes `bytes_of` refuses are
    refused here, by the same names.
    """
    raise NotImplementedError("stage 2: implement scan_of()")


def plan(scale, budget_mb):
    """The cheapest plan this estate and budget buy, or a refusal that names why.

    The plans are every layout cut `1..MAX_SHARDS` ways. A plan is kept when it
    holds the estate in `budget_mb` megabytes **and** a query scans at most
    `SCAN_BUDGET_BP`; among the kept, the smallest memory wins, ties by the order
    `LAYOUTS` spells them and then the fewest shards. When nothing is kept, the
    smallest-memory plan of all is answered as `verdict = "refused"` with every
    reason in `PLAN_PROBLEMS` order and each reason's own number. The answer is
    `PLAN_KEYS`. A budget below one raises, naming it; an estate missing a key
    raises, naming the key.
    """
    raise NotImplementedError("stage 2: implement plan()")


def explain(plan):
    """Every number a plan rests on, as `(claim, number)` pairs, in a fixed order.

    The claims are `"layout"`, `"shards"`, `"postings"`, `"memory_mb"`,
    `"scan_bp"`, `"clauses-scanned"`, `"index_cents"` and `"query_cents"`, in
    that order; each number is recomputed from the plan rather than copied, so a
    caller who recomputes them arrives at the plan's own verdict. A shape
    missing a `PLAN_KEYS` field is refused, naming the field.
    """
    raise NotImplementedError("stage 2: implement explain()")
