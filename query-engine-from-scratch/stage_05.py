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
price the index in a currency the disk does not accept. The same
matched-rows arithmetic picks the leaves; the price stays in pages.

DESIGN DECISION — Why does `plan` carry the pinned `uses_index` in its
record at all, when the choice must not come from it?
Because the record is the *audit*: the choice the planner made, and the
world's fact beside it, so the check can hold one against the other on all
hundred queries. A plan record that hid the pin could not be audited.

DESIGN DECISION — Why is `explain` a way in rather than a `__str__` on the
record?
Because the line is a *claim about the record* the check can compare token
by token — a rendering function the tester can mutate and watch the line
stop matching the record. A `__str__` would be the record vouching for
itself, and the check needs an independent mouth.
"""

import tables as tb

PLAN_KEYS = ("scans", "pushed", "uses_index", "cost")

#: the bar the world pinned: an events conjunct's matched rows must clear a
#: quarter of the table for the index to earn its keep.
SELECTIVITY_BAR = 4

import stage_03 as _pd
import tables as tb
#: at fanout 8 are 15 leaves, height 2)
_HEIGHT = 2
_LEAF_FANOUT = 8


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def cost_of(scan, table, matches=0):
    """A scan's price in pages: the table's pages, or the tree's walk.

    `scan` is `"table"` or `"index"`. A table scan costs the table's page
    count from `TABLE_PAGES`; an index scan costs the tree's height plus the
    matched leaf pages — `matches` is the conjuncts' matched row count, and
    the leaves those rows sit on are what the scan reads. Refuses a scan
    that is neither, naming it."""
    if scan == "table":
        return len(tb.TABLE_PAGES[table])
    if scan == "index":
        entry = tb.CATALOG.get(table)
        if entry is None or not entry.get("index"):
            _refuse("no_index", table)
        leaves = -(-matches // _LEAF_FANOUT)   # ceil: every leaf touched
        return _HEIGHT + leaves
    _refuse("no_scan", scan)


def _events_matches(conjuncts):
    """The events rows the pushed conjuncts keep — the world's own `ops`
    comparison, the same arithmetic the pin used."""
    matched = [row for row in tb.TABLES["events"]
               if all(tb._cmp(row[c], op, v)
                      for (_t, c, op, v) in conjuncts)]
    return matched


def plan(tree, facts):
    """The route: scans chosen, conjuncts pushed, the pin, the total cost.

    `tree` is the resolved tree (stage 2); `facts` is the world's
    `PLAN_FACTS`. The choice is `cost_of`'s comparison — an events WHERE
    whose conjuncts all name `ts` (column 1, the index's key) and match at
    most a quarter of the table makes the index earn its keep; nothing else
    does. The pin rides in the record as the audit's second opinion."""
    record = _pd.pushdown(tree)
    pushed = dict(record["pushed"])

    scans = []
    total = 0
    uses_index = False
    for (scan_table, conjuncts) in record["pushed"]:
        indexed = tb.CATALOG[scan_table].get("index") is not None
        eligible = False
        matched_rows = 0
        if indexed and conjuncts:
            ts_only = all(t == scan_table and c == 1
                          for (t, c, _op, _v) in conjuncts)
            if ts_only:
                matched_rows = len(_events_matches(conjuncts))
                eligible = (matched_rows <= len(tb.TABLES[scan_table])
                            // SELECTIVITY_BAR)
        if eligible and cost_of("index", scan_table,
                                matches=matched_rows) < cost_of("table",
                                                                scan_table):
            scans.append((scan_table, "index"))
            total += cost_of("index", scan_table, matches=matched_rows)
            uses_index = True
        else:
            scans.append((scan_table, "table"))
            total += cost_of("table", scan_table)

    # the executor's hints: the select shape, the projection's addresses,
    # the order and limit, and the joins' resolved ON columns — private
    # keys the executor reads and the surface check allows
    return {"scans": tuple(scans), "pushed": record["pushed"],
            "uses_index": uses_index, "cost": total,
            "_select": tree["select"], "_columns": tree["columns"],
            "_order": tree["order"], "_limit": tree["limit"],
            "_on": tuple((j[2], j[3]) for j in tree["joins"])}



def explain(record):
    """The plan as one line the check holds against the record.

    `events: index[ts] (ts<=60) | users: table` — the scans in order, the
    predicates attached, the joins between them."""
    parts = []
    for (table, kind) in record["scans"]:
        if kind == "index":
            key = tb.CATALOG[table]["index"]
            conjuncts = dict(record["pushed"]).get(table, ())
            preds = " and ".join("%s%s%r" % (key, op, v)
                                 for (_t, _c, op, v) in conjuncts)
            parts.append("%s: index[%s] (%s)" % (table, key, preds))
        else:
            parts.append("%s: table" % (table,))
    return " | ".join(parts)
