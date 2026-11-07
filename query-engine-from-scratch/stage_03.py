"""Query Engine From Scratch — stage 3: The predicates: conjuncts, and where
they go.

A WHERE is a list the parse kept in order; the predicates stage gives each
conjunct its address and its destination. `conjuncts_of` splits the resolved
WHERE into `(table, column, op, value)` — every conjunct now names the table
it applies to. `pushdown` answers where each one goes: a conjunct on one side
of a join belongs to that side's scan, where it filters rows *before* the join
does its quadratic work; a conjunct two scans could claim cannot move and
stays above, recorded in `both`. `referenced` is the question pushdown asks
per conjunct — does this conjunct name this side? — and is a way in of its own
so the check can hold the answer against the shape of the join the tree
declares.

The economics are the point: a predicate left where the user wrote it scans
both tables of a join and filters after; a predicate pushed below the join
may scan a quarter of one table. The stage's product is PRED_KEYS — the
conjuncts with their tables, where they were pushed, and the ones that could
not move — and stage 5's planner reads exactly that record.

DESIGN DECISION — Why does `conjuncts_of` take the *resolved* WHERE rather
than re-deriving tables itself?
Because the resolve already answered which table every column belongs to —
re-deriving it would be the resolve smuggled into the predicates stage. The
resolved conjunct is `((table, index), op, value)`; `conjuncts_of` turns the
address into a name.

DESIGN DECISION — Why is `referenced` a public way in rather than a private
helper?
Because its answer is the stage's whole claim about a conjunct — it names one
side, or it does not — and a check that cannot ask the question directly can
only test the aggregate.

DESIGN DECISION — Why does a both-sides conjunct stay above rather than
splitting into two?
Because splitting a conjunct changes its meaning: `orders.total >
users.credit` is one comparison over the joined row, not two filters. The
record keeps the conjunct whole in `both`, and the join above it applies it —
a planner that silently split it would answer a different query.
"""

PRED_KEYS = ("conjuncts", "pushed", "both")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def conjuncts_of(where):
    """The resolved WHERE as (table, column, op, value), in order.

    `where` is the resolved form — every conjunct `((table, index), op,
    value)`. Refuses a conjunct the resolve never produced."""
    out = []
    for conjunct in where:
        (address, op, value) = conjunct
        if not (isinstance(address, tuple) and len(address) == 2
                and isinstance(address[0], str)
                and isinstance(address[1], int) and address[1] >= 0):
            _refuse("unresolved", conjunct)
        out.append((address[0], address[1], op, value))
    return tuple(out)


def referenced(conjunct, side, tree):
    """Whether one conjunct names one side of the tree's join.

    `side` is `"left"` or `"right"`; the tree's join names the two tables.
    Answers True when the conjunct's table is that side's table."""
    if side == "left":
        return bool(tree["joins"]) and tree["joins"][0][0] == conjunct[0]
    if side == "right":
        return bool(tree["joins"]) and tree["joins"][-1][1] == conjunct[0]
    _refuse("no_side", side)


def pushdown(tree):
    """Where each conjunct goes: PRED_KEYS.

    Answers `("conjuncts", "pushed", "both")` — the conjuncts with their
    tables, per scan the conjuncts pushed below the join, and the conjuncts
    naming both sides that stayed above. The scans are the join fold's tables
    in fold order; a conjunct whose table exactly one scan owns is pushed to
    that scan, and one two scans could claim stays above whole."""
    conjuncts = conjuncts_of(tree["where"])
    # the scans in source order: the fold's first left table, then each
    # join's right — the base table is joins[0][0] when a fold exists
    scans = ([tree["joins"][0][0]] if tree["joins"] else [tree["table"]]) \
        + [right for (_l, right, _ol, _or) in tree["joins"]]

    pushed = [(scan, []) for scan in scans]
    both = []
    for conjunct in conjuncts:
        owners = [scan for scan in scans if scan == conjunct[0]]
        if len(owners) == 1:
            pushed[scans.index(owners[0])][1].append(conjunct)
        else:
            both.append(conjunct)

    return {"conjuncts": conjuncts,
            "pushed": tuple((scan, tuple(cs)) for (scan, cs) in pushed),
            "both": tuple(both)}
