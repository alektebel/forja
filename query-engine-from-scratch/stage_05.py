"""Query Engine From Scratch — stage 5: The plan: pushdown, selectivity, and
the earned index.

Stages 1–4 built the machinery; the plan is where a query earns its route.
`cost_of` prices a scan in pages — the currency the storage floor deals in:
a table scan costs the table's page count, a fact the world pinned in
`TABLE_PAGES`; an index scan costs the tree's height plus the matched leaf
pages, where *matched* is the world's own arithmetic — the conjuncts run
against the rows, and a quarter of the table is the bar the index must clear.
`plan` answers the whole route per query: the scans chosen, the conjuncts
stage 3 pushed to each, the pinned `uses_index` fact, and the total cost.
The choice is the cost comparison's answer, never a lookup of the pin — a
planner that read `uses_index` and echoed it back would be a pin with a
title, and the check proves the two agree on all hundred queries exactly
because they are computed separately.

`explain` renders the plan as one line the check holds against the plan's
own record — the scans in order, the predicates attached, the joins between
them — because a plan the operator cannot read is a plan nobody can argue
with.

DESIGN DECISION — Why does the index scan's cost count *matched leaf pages*
rather than matched rows?
Because the storage floor reads pages, not rows: the index scan's real cost
is the leaves it touches plus the height it descends. Counting rows would
price the index in a currency the disk does not accept, and the comparison
against a table scan — priced in pages — would be arithmetic over two
currencies. The same matched-rows arithmetic picks the leaves; the price
stays in pages.

DESIGN DECISION — Why does `plan` carry the pinned `uses_index` in its
record at all, when the choice must not come from it?
Because the record is the *audit*: the choice the planner made, and the
world's fact beside it, so the check can hold one against the other on all
hundred queries. A plan record that hid the pin could not be audited — the
agreement would be unfalsifiable.

DESIGN DECISION — Why is `explain` a way in rather than a `__str__` on the
record?
Because the line is a *claim about the record* the check can compare
token by token — a rendering function the tester can mutate and watch the
line stop matching the record. A `__str__` would be the record vouching for
itself, and the check needs an independent mouth.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

PLAN_KEYS = ("scans", "pushed", "uses_index", "cost")

#: the bar the world pinned: an events conjunct's matched rows must clear a
#: quarter of the table for the index to earn its keep.
SELECTIVITY_BAR = 4


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def cost_of(scan, table, matches=0):
    """A scan's price in pages: the table's pages, or the tree's walk.

    `scan` is `"table"` or `"index"`. A table scan costs the table's page
    count from `TABLE_PAGES`; an index scan costs the tree's height plus the
    matched leaf pages — `matches` is the conjuncts' matched row count, and
    the leaves those rows sit on are what the scan reads. Refuses a scan
    that is neither, naming it."""

    raise NotImplementedError("stage 5: implement cost_of()")


def plan(tree, facts):
    """The route: scans chosen, conjuncts pushed, the pin, the total cost.

    `tree` is the resolved tree (stage 2) with its predicates (stage 3);
    `facts` is the world's `PLAN_FACTS`. The choice is `cost_of`'s
    comparison — an events WHERE whose conjuncts match at most a quarter of
    the table makes the index earn its keep, and nothing else does."""

    raise NotImplementedError("stage 5: implement plan()")


def explain(record):
    """The plan as one line the check holds against the record.

    `events: index[ts] (ts<=60) | users: table` — the scans in order, the
    predicates attached, the joins between them."""

    raise NotImplementedError("stage 5: implement explain()")
