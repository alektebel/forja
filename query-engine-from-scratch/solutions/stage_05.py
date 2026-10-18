"""The stage 5 solution: the choice the costs made, on the plan's own account."""

import disk as dk
import pages as pg
import tables as tb
import ops

PLAN_KEYS = ("scans", "pushed", "uses_index", "cost")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


def _tree_height():
    """The events tree's height, built the way stage 4 builds it."""
    import stage_04
    pager = pg.Pager(dk.Disk())
    return stage_04.build(pager, tb.EVENTS_INDEX)["height"]


def cost_of(scan, table, matched):
    """A scan's price in pages: the table's pages, or height plus leaves."""
    if scan not in ("table", "index"):
        _refuse("no_scan", scan)
    if table not in tb.TABLE_PAGES:
        _refuse("no_table", table)
    if scan == "table":
        return len(tb.TABLE_PAGES[table])
    # the index prices its height plus the leaves the matches spread over
    import stage_04
    matched = max(matched, 1)
    return _tree_height() + -(-matched // stage_04.LEAF_FANOUT)


def plan(tree, facts):
    """The choice the costs made; the pin carried for the audit to judge.

    `facts` is the world's `PLAN_FACTS`. The choice is `cost_of`'s
    comparison — the pin is never read to decide, and the check proves the
    choice agrees with it on all hundred."""
    import stage_03
    pushdown = stage_03.pushdown(tree)
    conjuncts = pushdown["conjuncts"]

    scans = []
    total = 0
    for (scan_table, mine) in pushdown["pushed"]:
        if scan_table == "events" and mine \
                and all(c[1] == 1 for c in mine):  # every conjunct on ts
            matched = sum(
                1 for r in tb.TABLES["events"]
                if all(ops.compare(r[c[1]], c[2], c[3]) for c in mine))
            if cost_of("index", scan_table, matched) \
                    < cost_of("table", scan_table, matched):
                scans.append((scan_table, "index", mine))
                total += cost_of("index", scan_table, matched)
                continue
        cost = cost_of("table", scan_table, 0)
        scans.append((scan_table, "table", mine))
        total += cost

    return {"scans": tuple(scans), "pushed": pushdown["pushed"],
            "uses_index": any(scan == "index" for (_t, scan, _c) in scans),
            "cost": total}


def explain(plan_record):
    """One line: `events: index[ts] (ts<=60) | users: table`."""
    parts = []
    for (table, scan, conjuncts) in plan_record["scans"]:
        if scan == "index":
            where = " ".join("(ts%s%s)" % (c[2], _fmt(c[3]))
                             for c in conjuncts)
            parts.append("%s: index[ts] %s" % (table, where))
        else:
            parts.append("%s: table" % (table,))
    return " | ".join(parts)


def _fmt(value):
    """The value as the explain line spells it: bare ints, quoted strings."""
    if isinstance(value, str):
        return "'%s'" % (value,)
    return str(value)
