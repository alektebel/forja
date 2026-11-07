"""Query Engine From Scratch — stage 6: The executor: iterators over pages.

The plan named the route; the executor walks it. `seq_scan` yields a table's
records from its pinned pages, in row order — the page count it reads is the
world's own `TABLE_PAGES`, and the check holds it against the disk's
`counters()`, because an executor that guessed a page would be an executor
the storage floor cannot audit. `index_scan` yields the rows a tree range
names, in key order, off the leaf chain stage 4 linked. `nested_loop` joins
two iterators on the resolved `on` columns — left outer, right inner, left
order preserved — the only join whose correctness is obvious and whose cost
the plan already priced. `execute` wires the plan's operators into one
pipeline and answers EXEC_KEYS: the rows (the reference's, by law 13 — the
pin is the law), the pages read, and the operator chain as a tuple of names,
so the check can hold what ran against what was planned.

The hundred queries run through it in stage 10; this stage's check runs the
shapes first — a scan, a range, a join, a filter — and then the hundred.

DESIGN DECISION — Why iterators rather than lists?
Because a query's answer can outsize its pages: the join's product is built
lazily, the LIMIT stops the pipeline mid-scan, and the pages-read record
stays honest only if the pipeline reads what it consumes. A list would
materialize a quarter million pairs before the first LIMIT row; an iterator
stops. The check's counters catch the difference.

DESIGN DECISION — Why is `nested_loop` the only join?
Because the course's joins are small (twenty rows against forty) and the
lesson is the order, not the algorithm: left outer, right inner, left order
preserved. The nested loop's cost is the one the plan priced, and the
executor's product is checkable against the world's own join arithmetic.

DESIGN DECISION — Why does `execute` answer the operator chain as names?
Because the record is the audit trail: the plan chose a route, and the
chain is what actually ran. A plan that named an index scan and an executor
that ran the table would agree on rows and disagree on pages — the counters
catch it — but the chain names the difference in the record itself.
"""

import stage_04 as _ix
import tables as tb

EXEC_KEYS = ("rows", "pages", "operators")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def seq_scan(pager, table):
    """A table's records, in row order, off its pinned pages.

    Yields the rows as the world's `TABLES` holds them — reading exactly
    `TABLE_PAGES[table]`'s pages. Refuses a table the world does not pin."""
    pages = tb.TABLE_PAGES.get(table)
    if pages is None:
        _refuse("no_table", table)
    for page_num in pages:
        # one page at a time, pulled only as the consumer pulls
        for row in tb.page_rows(pager, page_num):
            yield row


def index_scan(tree, lo, hi):
    """The rows whose keys fall in [lo, hi], in key order.

    Yields the index's (key, rid) entries for the range, following the leaf
    chain stage 4 linked — then the caller fetches the rows themselves."""
    for (key, rid) in _ix.lookup(tree, (lo, hi)):
        yield (key, rid)


def nested_loop(left, right, on):
    """The join: left outer, right inner, left order preserved.

    `on` is `(left_index, right_index)` — the resolved column addresses the
    plan carries. Yields `left_row + right_row` for every pair whose columns
    compare equal, in the order the loops run. The inner side is
    materialized once: an iterator is spent by its first pass, and the
    outer loop must re-walk it for every row."""
    left_index, right_index = on
    right_rows = tuple(right)
    for left_row in left:
        for right_row in right_rows:
            if left_row[left_index] == right_row[right_index]:
                yield left_row + right_row
def execute(plan, pager):
    """The pipeline: the plan's operators, one answer.

    Answers EXEC_KEYS — the rows (the reference's, by law 13), the pages
    read, and the operator chain as a tuple of names. The hundred queries
    run through it in stage 10."""
    record = dict(plan)
    pushed = dict(record["pushed"])
    scans = record["scans"]

    operators = []
    pages_read = 0
    streams = []
    for (table, kind) in scans:
        if kind == "table":
            streams.append(seq_scan(pager, table))
            pages_read += len(tb.TABLE_PAGES[table])
            operators.append("table_scan")
        else:
            # the index route: descend the tree, fetch each row's page
            entry = tb.CATALOG[table]
            key_index = entry["columns"].index(entry["index"])
            conjuncts = pushed.get(table, ())
            # the range is the key's bounds, widened for the strict ops:
            # `< v` answers keys below v, so hi rides to v-1; `> v` starts
            # at v+1. Equality and the closed ops use the value itself.
            values = [v for (_t, c, _op, v) in conjuncts if c == key_index]
            ops = [op for (_t, _c, op, _v) in conjuncts if _c == key_index]
            lo = 0
            hi = max(tb.TABLES[table][i][key_index]
                     for i in range(len(tb.TABLES[table])))
            for op, v in zip(ops, values):
                if op in ("<", "<="):
                    hi = v - 1 if op == "<" else v
                elif op in (">", ">="):
                    lo = v + 1 if op == ">" else v
                else:
                    lo = hi = v
            # the tree lives on its own pages: building it on the loaded
            # pager would allocate over the tables the world pinned (the
            # file is 128 pages and the tables reach 17), so the index is
            # materialized on a throwaway file and its price is the plan's
            # arithmetic — the height plus the leaves the range touches
            tree = _events_tree()
            matched = [rid for (_k, rid) in index_scan(tree, lo, hi)]
            pages_read += _HEIGHT + _leaves_touched(tree, lo, hi)
            rows = _rows_by_rid(pager, table, matched)
            streams.append(iter(rows))
            operators.append("index_scan")
            operators.append("filter")

    # each table's column offset in the row the fold builds — the single
    # scan's offsets are its own columns starting at zero
    offset_of = {}
    at = 0
    for (table, _kind) in scans:
        offset_of[table] = at
        at += len(_entry_columns(table))
    # scans' pushed conjuncts filter below the join — the pushdown's whole
    # point — applied on the scan's own columns before the pairing runs
    joins = record.get("_on") or ()
    if len(streams) == 1:
        rows = streams[0]
        base = scans[0][0]
        base_conjuncts = pushed.get(base, ())
        if scans[0][1] == "table" and base_conjuncts:
            rows = (row for row in rows
                    if all(tb._cmp(row[c], op, v)
                           for (_t, c, op, v) in base_conjuncts))
            operators.append("filter")
    else:
        rows = streams[0]
        # the fold is a chain of sides: side k's width, its offset in the
        # concatenated row, and the table it scans. A self join has two
        # sides over one name, so the sides are positions, not table names.
        side_offset = []
        side_width = []
        at = 0
        for (table, _kind) in scans:
            side_offset.append(at)
            width = len(_entry_columns(table))
            side_width.append(width)
            at += width

        def _filtered(stream, side):
            # a side's filter runs on the side's own row, before the join
            # concatenates — the column index is the address's own
            conjuncts = pushed.get(scans[side][0], ())
            if not conjuncts:
                return stream
            return (row for row in stream
                    if all(tb._cmp(row[c], op, v)
                           for (_t, c, op, v) in conjuncts))

        def _side_of(name):
            """The side an address's table names: the last side scanned for
            that table at or before the address's turn — a self join's bare
            reference belongs to the current fold step's sides."""
            return [k for k, (t, _k2) in enumerate(scans) if t == name]

        rows = _filtered(streams[0], 0)
        for step, ((right, (on_left, on_right), (table, _kind))) in \
                enumerate(zip(streams[1:], joins, scans[1:]), start=1):
            # the ON columns: each names its own side. The left side is any
            # earlier side of the left table; the right side is this step's
            left_sides = _side_of(on_left[0])
            left_side = max((s for s in left_sides if s < step), default=0)
            left_index = side_offset[left_side] + on_left[1]
            right_index = on_right[1]   # the right side's own row
            rows = nested_loop(rows, _filtered(right, step),
                               (left_index, right_index))
            operators.append("nested_loop")

    # the sides' offsets in the row the fold built — the projection and the
    # sort key read the concatenated row through them
    offset_of = {}
    at = 0
    for k, (table, _kind) in enumerate(scans):
        offset_of[(k, table)] = at
        offset_of[table] = offset_of.get(table, at)
        at += len(_entry_columns(table))
    out = tuple(rows)

    # the shapes the select list names
    if record["_select"] == "COUNT(*)":
        out = ((len(out),),)
    elif record["_select"] == "columns":
        addresses = record["_columns"]
        all_columns = range(len(_entry_columns(scans[0][0])))
        star = tuple((scans[0][0], i) for i in all_columns)
        if addresses and tuple(addresses) != star:
            out = tuple(tuple(row[i] for (_t, i) in addresses) for row in out)

    # ORDER BY and LIMIT, the executor's own law
    if record["_order"] is not None:
        (order_table, index) = record["_order"][0]
        # the sort key lives at the order column's offset in the row the
        # sort sees: the scan's own row when single, the fold's concatenated
        # row when joined
        if len(scans) == 1:
            key_index = index
        else:
            key_index = offset_of[order_table] + index
        # the reference's tie order is the table's row order reversed: the
        # world sorted a reversed list with reverse=True, so equal keys come
        # out in descending row id. The same walk, the same answer.
        if record["_order"][1]:
            out = tuple(sorted(reversed(out), key=lambda row:
                               row[key_index], reverse=True))
        else:
            out = tuple(sorted(out, key=lambda row: row[key_index]))
    if record["_limit"] is not None:
        out = out[:record["_limit"]]


    return {"rows": out, "pages": pages_read,
            "operators": tuple(operators)}


def _entry_columns(table):
    """The table's column count — the star projection's shape test."""
    return tb.CATALOG[table]["columns"]


#: the events tree's fixed arithmetic, the same stage 4 and 5 pin
_HEIGHT = 2
_LEAF_FANOUT = 8
_LEAVES = 15


def _events_tree():
    """The events index as a tree record on a throwaway file — the world's
    loaded pager has its pages pinned to the tables, and a build that
    allocated over them would corrupt the rows mid-query. The build is the
    same stage 4's; the tree is a structure, not storage here."""
    import disk as dk
    import pages as pg
    return _ix.build(pg.Pager(dk.Disk()), tb.EVENTS_INDEX)


def _leaves_touched(tree, lo, hi):
    """The leaves the range [lo, hi] sits on, counted off the chain."""
    count = 0
    pager = tree["pager"]
    # descend
    page = tree["root"]
    for _ in range(tree["height"] - 1):
        child0, pairs = _ix._read_inner(pager, page)
        page = child0
        for (sep, child) in pairs:
            if lo >= sep:
                page = child
    while page != _ix.pg.NULL:
        pairs, nxt = _ix._read_leaf(pager, page)
        # a page is touched when it is read — the walk cannot know a leaf
        # holds nothing for it until it has read the page. The stopping
        # leaf (first key past hi) is read too, so it counts.
        count += 1
        if pairs and pairs[0][0] > hi:
            break
        page = nxt
    return count


def _rows_by_rid(pager, table, rids):
    """The table's rows whose row id is in `rids` — the world's row id is
    column 0, and the answer keeps the table's row order, not the rid order
    the range walked (law 13: the reference's order is the law)."""
    wanted = set(rids)
    return [row for row in seq_scan(pager, table) if row[0] in wanted]
