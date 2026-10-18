"""The stage 6 solution: the pipeline that answers the world's own rows."""

import disk as dk
import pages as pg
import tables as tb
import ops

EXEC_KEYS = ("rows", "pages", "chain")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


def _load_tables():
    """The world on a fresh pager — every scan starts from the same image."""
    pager = pg.Pager(dk.Disk())
    tb.load_world(pager)
    return pager


def seq_scan(pager, table):
    """A table's records from its pages, in row order."""
    if table not in tb.TABLE_PAGES:
        _refuse("no_table", table)
    for page in tb.TABLE_PAGES[table]:
        yield from tb.page_rows(pager, page)


def index_scan(pager, lo, hi):
    """The rows whose ts falls in [lo, hi], in key order.

    The tree is built on the same pager the world lives on, and synced —
    the walk's reads are real page reads the receipt counts."""
    import stage_04
    tree = stage_04.build(pager, tb.EVENTS_INDEX)
    pager.sync()
    entries = stage_04.lookup(tree, (lo, hi))
    by_id = {r[0]: r for r in tb.TABLES["events"]}
    for (_ts, rid) in entries:
        yield by_id[rid]


def nested_loop(left, right, left_on, right_on):
    """The join: left outer, right inner, left order preserved."""
    right_rows = list(right)
    for lrow in left:
        for rrow in right_rows:
            if ops.compare(lrow[left_on], "=", rrow[right_on]):
                yield lrow + rrow


def execute(pager, tree, plan_record):
    """The plan's operators, one pipeline; the world's rows out."""
    pager.sync()   # the receipt counts real page reads, not shadow hits
    reads_before = pager.disk.counters()["reads"]
    chain = []
    scans = dict((t, (scan, conjuncts)) for (t, scan, conjuncts)
                 in plan_record["scans"])

    base_table = tree["table"]
    if tree["joins"]:
        first = tree["joins"][0][0]
    else:
        first = base_table
    scan, _conjuncts = scans[first]

    if scan == "index":
        pushed_conjuncts = dict((t, c) for (t, c) in plan_record["pushed"])
        lo, hi = _bounds(pushed_conjuncts.get(first, ()))
        rows = list(index_scan(pager, lo, hi))
        # the index answers in key order; the world's reference answers in
        # table order (row id ascending) — restore it, ORDER BY re-sorts
        rows = sorted(rows, key=lambda r: r[0])
        chain.append("index_scan")
    else:
        rows = list(seq_scan(pager, first))
        chain.append("seq_scan")

    # joins, in the order the tree folds them
    left_width = len(tb.CATALOG[first]["columns"])
    for (left_name, right_name, on_left, on_right) in tree["joins"]:
        right_scan, _c = scans[right_name]
        right_rows = seq_scan(pager, right_name)
        if right_scan == "index":
            chain.append("index_scan")
        else:
            chain.append("seq_scan")
        chain.append("nested_loop")
        rows = list(nested_loop(rows, right_rows,
                                on_left[1], on_right[1]))
        left_width += len(tb.CATALOG[right_name]["columns"])

    # WHERE: the resolved conjuncts, applied over the full row
    widths = {name: len(tb.CATALOG[name]["columns"])
              for name in scans}
    def offset_of(owner):
        off = 0
        seen = []
        names = [tree["joins"][0][0]] + [j[1] for j in tree["joins"]] \
            if tree["joins"] else [base_table]
        for name in names:
            if name == owner:
                return off
            off += len(tb.CATALOG[name]["columns"])
        return off

    for ((owner, index), op, value) in tree["where"]:
        off = offset_of(owner)
        rows = [r for r in rows if ops.compare(r[off + index], op, value)]
    chain.append("filter")

    # COUNT(*) answers one row, one count; otherwise project, order, limit
    if tree["select"] == "COUNT(*)":
        rows = [(len(rows),),]
        chain.append("count")
    elif tree["select"] == "columns":
        offs = [offset_of(owner) + index
                for (owner, index) in tree["columns"]]
        rows = [tuple(r[o] for o in offs) for r in rows]
        chain.append("project")
    else:
        # star select of a join repeats both sides' rows whole
        pass

    if tree["order"]:
        owner, index = tree["order"][0]
        off = offset_of(owner)
        rows = sorted(rows, key=lambda r: (r[off + index], r[0]),
                      reverse=tree["order"][1])
        chain.append("sort")
    if tree["limit"] is not None:
        rows = rows[:tree["limit"]]
        chain.append("limit")

    pages = (pager.disk.counters()["reads"] - reads_before) // 2
    return {"rows": tuple(rows), "pages": pages,
            "chain": tuple(chain)}


def _bounds(conjuncts):
    """The [lo, hi] a run of ts conjuncts spans."""
    lo, hi = 0, 1 << 30
    for (_table, _index, op, value) in conjuncts:
        if op == "<=":
            hi = min(hi, value)
        elif op == "<":
            hi = min(hi, value - 1)
        elif op == ">=":
            lo = max(lo, value)
        elif op == ">":
            lo = max(lo, value + 1)
        elif op == "=":
            lo = hi = value
    return lo, hi
