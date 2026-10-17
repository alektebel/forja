"""Agentic Retrieval From Scratch — stage 2: Ten million documents, and the index that is a decision.

Ten million documents are a number before they are a system. Before anything can
be retrieved, the corpus is an estate — clauses, terms, postings, vectors, and
the bytes all of it weighs — and this stage is the arithmetic that turns that
estate into a decision. The numbers are the customer's: `corpus.SCALE` says how
many documents, clauses, terms and bytes-per-clause there are, and every figure
reported here is that scale's arithmetic, recomputed rather than believed.

The estate does not fit as one flat index, and not every plan fits its budget. A
flat index pays one dictionary and every vector, and a query scans all of it.
Sharding by document pays a dictionary per shard and scans only its own shard:
memory bought with memory, spent on the scan. A two-tier layout keeps the
dictionary whole and pays vectors only for the hot clauses, so memory drops and
a query still touches the hot tier whatever it scans. A plan is therefore a
search — over the layouts and the shard counts, keep what the memory budget and
the scan budget both allow, and answer the smallest memory, ties by the order
`LAYOUTS` spells them and then fewest shards.

What happens when nothing fits is the point. A plan that cannot pay is not
promised and not quietly rounded down: it is returned as `verdict = "refused"`,
with the reason and the offending number, because the customer is entitled to
know which constraint broke. Memory is rounded *up* for the same reason — a plan
that rounds down is a plan that does not fit.

The last thing this stage owns is the price. Indexing is charged per million
postings and a query per million clauses scanned, so the scan a layout buys is
also the cost a query pays: a flat plan indexes once and pays for the whole
estate on every query, and a sharded one pays a dictionary per shard to scan a
fraction of it. `explain` hands back every number a plan rests on as
`(claim, number)` pairs, so a caller can recompute the decision rather than
trust it.
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

_FULL_SCAN_BP = 10000


class PlanError(ValueError):
    """A shape this stage cannot accept, or an estate it will not plan.

    A kind of `ValueError`, which is what the world's own refusals are, so a
    caller that already catches a broken library catches a broken plan too.
    """


def _mapping(value, what):
    """`value` as a mapping, or the mistake naming what arrived."""
    if not isinstance(value, dict):
        raise PlanError("the %s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _estate(scale):
    """An estate with every number a plan needs, or the refusal naming the keys.

    The keys are `corpus.SCALE_KEYS`, so the only source of truth for what an
    estate is is the customer's own scale. A key that is missing is named, all
    of them if there is more than one, because "the scale is malformed" tells a
    caller nothing they can fix.
    """
    scale = _mapping(scale, "estate")
    missing = [key for key in corpus.SCALE_KEYS if key not in scale]
    if missing:
        raise PlanError("the estate carries no %s, and a plan needs them all"
                        % (", ".join(repr(key) for key in missing),))
    return scale


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlanError("the %s is %r, not a whole number" % (what, value))
    return value


def _layout(layout):
    """A layout the plan knows, or the refusal naming what was asked for."""
    if layout not in LAYOUTS:
        raise PlanError("%r is not one of the layouts %r" % (layout, LAYOUTS))
    return layout


def _shards(shards):
    """A whole number of shards, at least one, or the refusal naming it."""
    shards = _whole(shards, "shard count")
    if shards < 1:
        raise PlanError("the shard count is %d, and a layout has at least one shard"
                        % (shards,))
    return shards


def _to_mb(byte_count):
    """Bytes as whole megabytes, rounded up: a plan that rounds down does not fit."""
    return (byte_count + BYTES_PER_MB - 1) // BYTES_PER_MB


def weigh(scale):
    """The estate's flat figures, every one of them an `int`.

    `postings` is the clauses' own postings, `posting_bytes`, `dictionary_bytes`
    and `vector_bytes` are the three bills the estate runs, `bytes` is their sum
    and `memory_mb` is that sum rounded **up** to whole megabytes. `hot_clauses`
    is the share of the clauses the hot tier keeps, in basis points of the
    estate's own `hot_bp`.
    """
    scale = _estate(scale)
    clauses = scale["clauses"]
    terms = scale["terms"]
    postings = clauses * POSTINGS_PER_CLAUSE
    posting_bytes = postings * POSTING_BYTES
    dictionary_bytes = terms * TERM_BYTES
    vector_bytes = clauses * corpus.VECTOR_DIM * VECTOR_BYTES
    total = posting_bytes + dictionary_bytes + vector_bytes
    return {"clauses": clauses, "terms": terms, "postings": postings,
            "posting_bytes": posting_bytes, "dictionary_bytes": dictionary_bytes,
            "vector_bytes": vector_bytes, "bytes": total, "memory_mb": _to_mb(total),
            "hot_clauses": clauses * scale["hot_bp"] // 10000}


def bytes_of(layout, shards, scale):
    """The bytes a layout holds, in total, for an estate cut into `shards`.

    A flat index pays one dictionary and every vector. Sharding by document pays
    a dictionary per shard — that is the whole price of sharding — and still
    every vector. A two-tier layout pays one dictionary and only the hot
    clauses' vectors, whatever the shard count.
    """
    scale = _estate(scale)
    layout = _layout(layout)
    shards = _shards(shards)
    figures = weigh(scale)
    if layout == "flat":
        return (figures["posting_bytes"] + figures["dictionary_bytes"]
                + figures["vector_bytes"])
    if layout == "sharded-by-doc":
        return (figures["posting_bytes"] + shards * figures["dictionary_bytes"]
                + figures["vector_bytes"])
    return (figures["posting_bytes"] + figures["dictionary_bytes"]
            + figures["hot_clauses"] * corpus.VECTOR_DIM * VECTOR_BYTES)


def scan_of(layout, shards, scale):
    """The basis points of the estate a query scans under this layout.

    A flat index scans all of it. Sharding divides that share by the shard
    count and never below a shard's own share. A two-tier layout scans at least
    the hot tier — the hot clauses are always touched — and otherwise the same
    divided share as a sharded one.
    """
    scale = _estate(scale)
    layout = _layout(layout)
    shards = _shards(shards)
    if layout == "flat":
        return _FULL_SCAN_BP
    if layout == "sharded-by-doc":
        return _FULL_SCAN_BP // shards
    return max(scale["hot_bp"], _FULL_SCAN_BP // shards)


def _problems(chosen, budget_mb):
    """Every reason the chosen refusing plan is refused, in `PLAN_PROBLEMS` order.

    Each reason carries the plan's own offending number rather than the budget it
    missed: the customer asked which of the plan's own figures broke, and the two
    reasons a plan of this estate can break are its memory and its scan.
    """
    memory_mb, _, shards, _, scan_bp = chosen
    found = []
    if memory_mb > budget_mb:
        found.append(("over-budget", memory_mb))
    if scan_bp > SCAN_BUDGET_BP:
        found.append(("scan-too-wide", scan_bp))
    return tuple(found)


def _candidates(scale):
    """Every layout cut every way the plan may propose, in a decision's order.

    One row per `(layout, shards)`: its memory, the layout's own position in
    `LAYOUTS`, the shard count, the layout and the scan. Sorted by memory and
    then by that position and the fewest shards, so the first row is the
    smallest memory the contract would choose.
    """
    figures = weigh(scale)
    rows = []
    for layout in LAYOUTS:
        for shards in range(1, MAX_SHARDS + 1):
            memory_mb = _to_mb(bytes_of(layout, shards, scale))
            scan_bp = scan_of(layout, shards, scale)
            rows.append((memory_mb, LAYOUTS.index(layout), shards, layout, scan_bp))
    rows.sort()
    return figures, rows


def plan(scale, budget_mb):
    """The cheapest plan this estate and budget buy, or a refusal that names why.

    The plans are every layout cut `1..MAX_SHARDS` ways. A plan is kept when it
    holds the estate in `budget_mb` megabytes **and** a query scans at most
    `SCAN_BUDGET_BP`; among the kept, the smallest memory wins, ties by the
    order `LAYOUTS` spells them and then the fewest shards. When nothing is
    kept, the smallest-memory plan of all is answered as `verdict = "refused"`,
    with every reason in `PLAN_PROBLEMS` order and each reason's own number.
    """
    scale = _estate(scale)
    budget_mb = _whole(budget_mb, "budget in megabytes")
    if budget_mb < 1:
        raise PlanError("the budget is %d MB, and a plan needs at least one"
                        % (budget_mb,))
    figures, rows = _candidates(scale)
    kept = [row for row in rows
            if row[0] <= budget_mb and row[4] <= SCAN_BUDGET_BP]
    if kept:
        chosen = kept[0]
        verdict, problems = "fits", ()
    else:
        chosen = rows[0]
        verdict, problems = "refused", _problems(chosen, budget_mb)
    memory_mb, _, shards, layout, scan_bp = chosen
    clauses_scanned = scale["clauses"] * scan_bp // 10000
    return {"layout": layout, "shards": shards, "postings": figures["postings"],
            "memory_mb": memory_mb, "scan_bp": scan_bp,
            "index_cents": figures["postings"] * INDEX_CENTS_PER_MILLION_POSTINGS
            // 1000000,
            "query_cents": clauses_scanned * QUERY_CENTS_PER_MILLION_SCANNED
            // 1000000,
            "verdict": verdict, "problems": problems}


def _plan_record(plan):
    """A plan with every `PLAN_KEYS` field, or the refusal naming the missing one."""
    plan = _mapping(plan, "plan")
    for key in PLAN_KEYS:
        if key not in plan:
            raise PlanError("the plan carries no %r, so it cannot be explained" % (key,))
    return plan


def explain(plan):
    """Every number a plan rests on, as `(claim, number)` pairs, in a fixed order.

    The claims are the plan's own fields — its layout, its shard count, its
    postings, its memory, its scan — plus the two figures a caller cannot read
    off the record: the clauses a query actually scans, and the two prices. Each
    one is recomputed from the plan rather than copied, so a caller who
    recomputes them this way arrives at the plan's own verdict.
    """
    plan = _plan_record(plan)
    clauses_scanned = plan["postings"] // POSTINGS_PER_CLAUSE * plan["scan_bp"] // 10000
    return (("layout", plan["layout"]),
            ("shards", plan["shards"]),
            ("postings", plan["postings"]),
            ("memory_mb", plan["memory_mb"]),
            ("scan_bp", plan["scan_bp"]),
            ("clauses-scanned", clauses_scanned),
            ("index_cents", plan["index_cents"]),
            ("query_cents", plan["query_cents"]))
