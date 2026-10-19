"""The stage 6 solution: the plan walked, one operator at a time."""

import disk as dk
import pages as pg
import tables as tb
import ops

EXEC_KEYS = ("rows", "pages", "operators")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


def seq_scan(pager, table):
    """A table's records, in row order, off its pinned pages."""
    if table not in tb.TABLE_PAGES:
        _refuse("no_table", table)
    for page in tb.TABLE_PAGES[table]:
        for row in tb.page_rows(pager, page):
            yield row


def index_scan(tree, lo, hi):
    """The entries whose keys fall in [lo, hi], in key order, off the chain."""
    import stage_04
    yield from stage_04.lookup(tree, (lo, hi))


def nested_loop(left, right, on):
    """Left outer, right inner, left order preserved.

    The inner side is materialized once — an iterator is consumed by its
    first pass, and the outer loop walks it forty times."""
    left_index, right_index = on
    right_rows = tuple(right)
    for left_row in left:
        for right_row in right_rows:
            if ops.compare(left_row[left_index], "=",
                           right_row[right_index]):
                yield left_row + right_row


def _rows_for(pager, table, kind, pushes_here, tree):
    """One scan's rows: the route the plan named, the conjuncts applied."""
    if kind == "index":
        lo, hi = 0, 10 ** 6
        for (_t, _c, op, v) in pushes_here:
            if not isinstance(v, int):
                continue
            if op == "<":
                hi = min(hi, v - 1)
            elif op == "<=":
                hi = min(hi, v)
            elif op == ">":
                lo = max(lo, v + 1)
            elif op == ">=":
                lo = max(lo, v)
            elif op == "=":
                lo = max(lo, v)
                hi = min(hi, v)
        entries = set(rid for (_k, rid) in index_scan(tree, lo, hi))
        rows = (r for r in seq_scan(pager, table) if r[0] in entries)
    else:
        rows = seq_scan(pager, table)
    for (_t, col, op, value) in pushes_here:
        rows = (lambda rows, col, op, value:
                (r for r in rows if ops.compare(r[col], op, value)))(
                    rows, col, op, value)
    return rows


def execute(plan, pager):
    """The pipeline the plan named, answering EXEC_KEYS."""
    import stage_04
    import stage_05
    scans = plan["scans"]
    pushes = dict(plan["pushed"])
    operators = []
    pages_read = 0
    # the index scan runs over the world's own tree, on its own disk: the
    # tree is the index's structure, not its storage, and the world's pages
    # are pinned — a tree built on this pager would overwrite them
    tree = stage_04.build(pg.Pager(dk.Disk()), tb.EVENTS_INDEX) \
        if any(kind == "index" for (_t, kind) in scans) else None
    streams = []
    for (table, kind) in scans:
        pushes_here = pushes.get(table, ())
        operators.append("%s_scan" % (kind,))
        pages_read += stage_05.cost_of(kind, table,
                                       matches=0 if kind == "table"
                                       else 10 ** 9)
        if pushes_here:
            operators.append("filter")
        streams.append(_rows_for(pager, table, kind, pushes_here, tree))
    rows = streams[0]
    ons = plan.get("_on", ())
    widths = [len(tb.CATALOG[t]["columns"]) for (t, _k) in scans]
    joined_widths = widths[0] if widths else 0
    for i, stream in enumerate(streams[1:]):
        operators.append("nested_loop")
        (lt, lcol), (rt, rcol) = ons[i]
        # the left ref's column sits at the accumulated offset of its table
        offset = 0
        for j in range(i + 1):
            if scans[j][0] == lt:
                offset += lcol
                break
            offset += widths[j]
        rows = nested_loop(rows, stream, (offset, rcol))
    out = tuple(rows)
    # the select's three shapes: whole rows, a projection, the count
    if plan.get("_select") == "columns":
        # the resolve turned the projection into (table, index) addresses
        col_index = [index for (_t, index) in plan.get("_columns", ())]
        out = tuple(tuple(r[c] for c in col_index) for r in out)
    elif plan.get("_select") == "COUNT(*)":
        out = ((len(out),),)
    order = plan.get("_order")
    if order:
        (ot, ocol), desc = order
        offset = 0
        for j, (t, _k) in enumerate(scans):
            if t == ot:
                offset += ocol
                break
            offset += widths[j]
        out = tuple(sorted(out, key=lambda r: (r[offset], r[0]),
                           reverse=desc))
    limit = plan.get("_limit")
    if limit is not None:
        out = out[:limit]
    return {"rows": out, "pages": pages_read,
            "operators": tuple(operators)}
