"""The stage 5 solution: the route the costs choose, and the pin audited."""

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


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


#: the pairs one leaf page holds: a (ts, id) pair is at worst a 3-byte and a
#: 2-byte varint; the page spends two bytes on tag and next-pointer. The
#: worst case is the honest count — the planner does not guess a page full.
_LEAF_CAPACITY = (pg.PAGE_SIZE - 2) // 5


def _tree_shape():
    """The events tree's shape, from the world's arithmetic."""
    entries = len(tb.EVENTS_INDEX)
    leaves = -(-entries // _LEAF_CAPACITY)
    height = 1 if leaves == 1 else 2
    return height, leaves


def cost_of(scan, table, matches=0):
    """A scan's price in pages: the table's pages, or the tree's walk."""
    if scan == "table":
        if table not in tb.TABLE_PAGES:
            _refuse("no_table", table)
        return len(tb.TABLE_PAGES[table])
    if scan == "index":
        if table != "events":
            _refuse("no_index", table)
        height, _leaves = _tree_shape()
        matched_rows = min(matches, len(tb.TABLES["events"]))
        matched_leaves = -(-matched_rows // _LEAF_CAPACITY)
        return height + matched_leaves
    _refuse("no_scan", scan)


def _ts_matches(conjuncts):
    """The rows the events conjuncts match — the world's own arithmetic."""
    matched = [r for r in tb.TABLES["events"]
               if all(ops.compare(r[1], op, value)
                      for (_t, _c, op, value) in conjuncts)]
    return matched


def plan(tree, facts):
    """The route the costs choose, with the pin carried for the audit."""
    pushed = dict()
    if "pushed" in tree:            # a stage-3 pushdown record
        for scan, conjuncts in tree["pushed"]:
            pushed[scan] = conjuncts
        both = tree["both"]
    else:                           # a bare resolved tree: nothing pushed yet
        import stage_03
        record = stage_03.pushdown(tree)
        for scan, conjuncts in record["pushed"]:
            pushed[scan] = conjuncts
        both = record["both"]

    scans = []
    total = 0
    uses_index = False
    for scan in pushed:
        conjuncts = pushed[scan]
        if scan == "events" and conjuncts and all(
                table == "events" and col == 1
                for (table, col, _op, _value) in conjuncts):
            # the index is over (ts, id): a WHERE the index cannot serve
            # whole — any non-ts conjunct — is not eligible
            matched = _ts_matches(conjuncts)
            # the choice: the cost comparison, not the pin
            table_cost = cost_of("table", scan)
            index_cost = cost_of("index", scan, matches=len(matched))
            if index_cost < table_cost and \
                    len(matched) <= len(tb.TABLES["events"]) // SELECTIVITY_BAR:
                scans.append(("events", "index"))
                total += index_cost
                uses_index = True
                continue
        scans.append((scan, "table"))
        total += cost_of("table", scan)
    if both:
        total += 0                  # the join's own work is stage 6's price

    return {"scans": tuple(scans), "pushed": tuple(pushed.items()),
            "uses_index": uses_index, "cost": total}


def explain(record):
    """The plan as one line the check holds against the record."""
    parts = []
    for (table, kind) in record["scans"]:
        conjuncts = dict(record["pushed"]).get(table, ())
        if kind == "index":
            conds = " ".join("%s%s%r" % (c, op, v)
                             for (_t, _col, op, v) in conjuncts
                             for c in [""])
            parts.append("events: index[ts] (%s)" %
                         " AND ".join("ts%s%s" % (op, _fmt(v))
                                      for (_t, _col, op, v) in conjuncts))
        else:
            parts.append("%s: table" % (table,))
    return " | ".join(parts)


def _fmt(value):
    """A literal as the SQL wrote it: strings quoted, ints bare."""
    if isinstance(value, str):
        return "'%s'" % (value,)
    return str(value)
