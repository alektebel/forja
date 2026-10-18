"""The tables: the catalog, the rows, and the 100 queries.

Three closed vocabularies, all data, all read-only:

  * `CATALOG` — the schema: four tables, each with its column names, its
    integer key column, and the index the storage layer maintains (`None`
    where there is none). The catalog is the truth a query engine resolves
    names against — and it can *lie*: `CATALOG_LIES` is the fixture where a
    column is named that no table has and a type is declared that no row
    honours, because resolving against a catalog you did not verify is the
    resolve stage's whole point.
  * `TABLES` — the rows themselves, as tuples of tuples. They are what the
    storage layer is expected to be able to reproduce from pages alone: a
    stage that loads a table into memory and forgets the pages has not run on
    this world. `TABLE_PAGES` pins which pages hold which table's rows when
    the world loads them through the provided pager — the layout a recovery
    is graded against.
  * `QUERIES` — one hundred of them, each a dict with the SQL text, the id,
    and the rows the reference answers (`"rows"`), plus for the indexed ones
    the plan facts a stage's EXPLAIN has to agree with (`"uses_index"`). The
    judge in stage 10 is this list: the same rows, the same order, no
    argument.

The SQL subset these queries speak is the course's whole grammar:

    SELECT <cols | COUNT(*)> FROM <table>
        [JOIN <table> ON <col> = <col>]
        [WHERE <col> <op> <value> [AND <col> <op> <value>]...]
        [ORDER BY <col> [ASC | DESC]] [LIMIT n]

The four tables are small on purpose — `users`, `orders`, `items`,
`events` — but shaped to force every plan decision: `orders.user_id` joins
`users.id`; `events.ts` is the indexed column whose index only pays when the
predicate is selective; every table's rows are unique enough that an
`ORDER BY` has exactly one right answer.
"""

# --- the catalog --------------------------------------------------------------

CATALOG = {
    "users": {"columns": ("id", "name_id", "plan"),
              "key": "id",
              "index": None},
    "orders": {"columns": ("id", "user_id", "total", "status"),
               "key": "id",
               "index": None},
    "items": {"columns": ("id", "order_id", "price"),
              "key": "id",
              "index": None},
    "events": {"columns": ("id", "ts", "kind"),
               "key": "id",
               "index": "ts"},       # the one B+tree: events by ts
}

#: the fixture where the catalog lies: a column no table has, a type no row
#: honours, and a table that is not there. Resolving against it must refuse,
#: naming the offender — not trust it.
CATALOG_LIES = {
    "users": {"columns": ("id", "name_id", "plan", "email"),   # no such column
              "key": "email",                                   # not a column
              "index": None},
    "phantom": {"columns": ("id",), "key": "id", "index": None},  # no table
}

#: the ops a WHERE clause may speak, closed
OPS = ("=", "!=", "<", "<=", ">", ">=")

# --- the rows -----------------------------------------------------------------

_USERS = tuple((i, 100 + i * 7 % 90, ("free", "pro", "team")[i % 3])
               for i in range(1, 21))
_ORDERS = tuple((i, (i * 7) % 20 + 1, i * 13 % 250 + 5,
                 ("open", "paid", "shipped")[i % 3])
                for i in range(1, 41))
_ITEMS = tuple((i, (i * 3) % 40 + 1, i * 11 % 90 + 1)
               for i in range(1, 80))
_EVENTS = tuple((i, (i * 17) % 500 + 1, ("login", "click", "buy")[i % 3])
                for i in range(1, 121))

TABLES = {"users": _USERS, "orders": _ORDERS, "items": _ITEMS,
          "events": _EVENTS}

#: which pages hold which table when the world loads it: table t's rows live
#: on pages whose numbers the stage-4 loader recorded. The world pins the
#: layout so recovery has something fixed to be graded against.
TABLE_PAGES = {"users": (1, 2), "orders": (3, 4, 5, 6), "items": (7, 8, 9, 10),
               "events": (11, 12, 13, 14, 15, 16, 17)}

#: the events index: an ordered index over (ts, id), materialized as rows of
#: (ts, id) pairs — the leaf entries a B+tree over `events.ts` must contain,
#: in ts order, ids ascending within a tie
EVENTS_INDEX = tuple(sorted(((ts, i) for (i, ts, _kind) in _EVENTS)))

# --- the queries ---------------------------------------------------------------


def _q(qid, sql, rows, uses_index=None):
    q = {"id": qid, "sql": sql, "rows": tuple(rows)}
    if uses_index is not None:
        q["uses_index"] = uses_index
    return q


def _build_queries():
    """The hundred: generated from the tables so the expected rows are the
    reference's own arithmetic, never a stage's claim."""
    queries = []

    users, orders, items, events = TABLES["users"], TABLES["orders"], \
        TABLES["items"], TABLES["events"]
    u_by_id = {r[0]: r for r in users}
    o_by_id = {r[0]: r for r in orders}
    i_by_id = {r[0]: r for r in items}
    e_by_id = {r[0]: r for r in events}

    # 1–10: whole tables, one per shape, in key order
    for t, rows in TABLES.items():
        queries.append(_q(len(queries) + 1,
                          "SELECT * FROM %s" % (t,), rows))
    # 6–10: single columns
    for t, cols in (("users", ("id",)), ("orders", ("id", "user_id")),
                    ("items", ("price",)), ("events", ("ts", "kind")),
                    ("orders", ("status",)), ("users", ("plan", "name_id"))):
        idx = [CATALOG[t]["columns"].index(c) for c in cols]
        queries.append(_q(len(queries) + 1,
                          "SELECT %s FROM %s"
                          % (", ".join(cols), t),
                          tuple(tuple(r[j] for j in idx)
                                for r in TABLES[t])))

    # 11–30: WHERE, one predicate, every op
    for n, (t, col, op, val) in enumerate([
            ("orders", "total", ">", 100), ("orders", "total", "<=", 50),
            ("orders", "status", "=", "paid"), ("orders", "status", "!=", "open"),
            ("orders", "user_id", "=", 8), ("orders", "user_id", ">", 15),
            ("items", "price", ">=", 40), ("items", "price", "<", 20),
            ("items", "order_id", "=", 10), ("events", "ts", ">", 250),
            ("events", "ts", "<", 100), ("events", "kind", "=", "buy"),
            ("events", "kind", "!=", "login"), ("events", "ts", "<=", 60),
            ("users", "plan", "=", "pro"), ("users", "plan", "!=", "team"),
            ("users", "name_id", ">", 150), ("users", "name_id", "<=", 130),
            ("orders", "id", ">=", 30), ("items", "id", "=", 55)]):
        table = TABLES[t]
        idx = CATALOG[t]["columns"].index(col)
        rows = tuple(r for r in table
                     if _cmp(r[idx], op, val))
        queries.append(_q(len(queries) + 1,
                          "SELECT * FROM %s WHERE %s %s %r"
                          % (t, col, op, val), rows))

    # 31–45: WHERE, two conjuncts (AND)
    two = [
        ("orders", ("total", ">", 100), ("status", "=", "paid")),
        ("orders", ("total", "<", 100), ("status", "!=", "shipped")),
        ("orders", ("user_id", "=", 8), ("total", ">", 50)),
        ("orders", ("user_id", "<", 10), ("total", ">=", 100)),
        ("items", ("price", ">", 30), ("price", "<", 60)),
        ("items", ("order_id", "=", 5), ("price", "<=", 45)),
        ("events", ("ts", ">", 200), ("ts", "<", 300)),
        ("events", ("ts", ">=", 100), ("kind", "=", "click")),
        ("events", ("kind", "=", "buy"), ("id", "<", 50)),
        ("users", ("plan", "=", "free"), ("name_id", ">", 140)),
        ("users", ("plan", "!=", "free"), ("name_id", "<", 160)),
        ("orders", ("total", ">=", 50), ("total", "<=", 150)),
        ("events", ("ts", "<", 50), ("kind", "=", "login")),
        ("items", ("price", "=", 45), ("order_id", ">", 10)),
        ("orders", ("status", "=", "open"), ("id", "<", 10)),
    ]
    for (t, (c1, op1, v1), (c2, op2, v2)) in two:
        cols = CATALOG[t]["columns"]
        i1, i2 = cols.index(c1), cols.index(c2)
        rows = tuple(r for r in TABLES[t]
                     if _cmp(r[i1], op1, v1) and _cmp(r[i2], op2, v2))
        queries.append(_q(len(queries) + 1,
                          "SELECT * FROM %s WHERE %s %s %r AND %s %s %r"
                          % (t, c1, op1, v1, c2, op2, v2), rows))

    # 46–60: ORDER BY (asc and desc), some with LIMIT
    orders_by = [
        ("users", "id", False), ("users", "name_id", True),
        ("orders", "total", True), ("orders", "total", False),
        ("orders", "user_id", False), ("orders", "id", True),
        ("items", "price", False), ("items", "price", True),
        ("events", "ts", False), ("events", "ts", True),
        ("events", "id", False), ("orders", "status", False),
        ("items", "order_id", True), ("users", "plan", True),
        ("events", "kind", False),
    ]
    for n, (t, col, desc) in enumerate(orders_by):
        cols = CATALOG[t]["columns"]
        icol = cols.index(col)
        rows = tuple(sorted(TABLES[t],
                            key=lambda r: (r[icol], r[0]),
                            reverse=desc))
        limit = [None, None, 5, None, 3, None, None, 10, None, 7,
                 None, None, 4, None, None][n]
        if limit is not None:
            rows = rows[:limit]
        sql = "SELECT * FROM %s ORDER BY %s%s" % (
            t, col, " DESC" if desc else "")
        if limit is not None:
            sql += " LIMIT %d" % (limit,)
        queries.append(_q(len(queries) + 1, sql, rows))

    # 61–75: WHERE + ORDER BY (+ LIMIT)
    where_order = [
        ("orders", ("status", "=", "paid"), "total", True, None),
        ("orders", ("total", ">", 50), "user_id", False, 6),
        ("items", ("price", "<", 50), "price", True, None),
        ("items", ("price", ">=", 40), "order_id", False, None),
        ("events", ("ts", "<=", 80), "ts", False, 8),
        ("events", ("kind", "=", "buy"), "id", False, None),
        ("users", ("plan", "=", "team"), "name_id", True, 3),
        ("orders", ("user_id", "=", 8), "id", False, None),
        ("events", ("ts", "<", 400), "kind", False, None),
        ("items", ("order_id", "<", 20), "price", True, None),
        ("orders", ("total", "<=", 120), "total", True, None),
        ("users", ("name_id", ">", 120), "id", False, 5),
        ("events", ("id", ">", 80), "ts", True, None),
        ("orders", ("id", "<", 25), "total", False, None),
        ("items", ("price", ">", 10), "id", True, 9),
    ]
    for (t, (c1, op1, v1), col, desc, limit) in where_order:
        cols = CATALOG[t]["columns"]
        i1 = cols.index(c1)
        icol = cols.index(col)
        rows = [r for r in TABLES[t] if _cmp(r[i1], op1, v1)]
        rows = tuple(sorted(rows, key=lambda r: (r[icol], r[0]),
                            reverse=desc))
        if limit is not None:
            rows = rows[:limit]
        sql = "SELECT * FROM %s WHERE %s %s %r ORDER BY %s%s" % (
            t, c1, op1, v1, col, " DESC" if desc else "")
        if limit is not None:
            sql += " LIMIT %d" % (limit,)
        queries.append(_q(len(queries) + 1, sql, rows))

    # 76–90: JOIN orders↔users, items↔orders, with predicates and orders
    joins = [
        ("orders", "users", "user_id", "id", None, None),
        ("items", "orders", "order_id", "id", None, None),
        ("orders", "users", "user_id", "id", ("orders", "total", ">", 100), None),
        ("orders", "users", "user_id", "id", ("users", "plan", "=", "pro"), None),
        ("items", "orders", "order_id", "id", ("orders", "status", "=", "paid"), None),
        ("items", "orders", "order_id", "id", ("items", "price", "<", 30), None),
        ("orders", "users", "user_id", "id", ("orders", "total", ">", 150), "orders.total"),
        ("items", "orders", "order_id", "id", ("orders", "total", ">=", 200), "orders.id"),
        ("orders", "users", "user_id", "id", ("users", "name_id", "<", 150), "users.id"),
        ("items", "orders", "order_id", "id", ("items", "price", ">", 60), "items.price"),
        ("events", "events", "id", "id", None, None),          # self join
        ("orders", "users", "user_id", "id", ("orders", "status", "!=", "open"), "orders.total"),
        ("items", "orders", "order_id", "id", ("orders", "user_id", "=", 8), None),
        ("orders", "users", "user_id", "id", ("orders", "user_id", ">", 10), None),
        ("items", "orders", "order_id", "id", ("orders", "total", "<", 60), "items.order_id"),
    ]
    for n, (tl, tr, cl, cr, pred, order) in enumerate(joins):
        left, right = TABLES[tl], TABLES[tr]
        lcols, rcols = CATALOG[tl]["columns"], CATALOG[tr]["columns"]
        il, ir = lcols.index(cl), rcols.index(cr)
        joined = []
        for l in left:
            for r in right:
                if l[il] == r[ir]:
                    joined.append(l + r)
        if pred is not None:
            pt, pc, pop, pv = pred
            if pt == tl:
                j = lcols.index(pc)
            else:
                j = len(lcols) + rcols.index(pc)
            joined = [row for row in joined if _cmp(row[j], pop, pv)]
        if order is not None:
            pt, pc = order.split(".")
            j = (lcols if pt == tl else rcols).index(pc)
            j = j if pt == tl else len(lcols) + j
            joined = sorted(joined, key=lambda row: (row[j], row[0]))
        out = tuple(joined)
        sql = "SELECT * FROM %s JOIN %s ON %s.%s = %s.%s" % (
            tl, tr, tl, cl, tr, cr)
        if pred is not None:
            sql += " WHERE %s.%s %s %r" % (pred[0], pred[1], pred[2], pred[3])
        if order is not None:
            sql += " ORDER BY %s" % (order,)
        queries.append(_q(len(queries) + 1, sql, out))

    # 91–100: COUNT(*) — the aggregate that needs no group
    counts = [
        ("users", None, None), ("orders", None, None),
        ("items", None, None), ("events", None, None),
        ("orders", ("status", "=", "paid"), None),
        ("orders", ("total", ">", 100), None),
        ("items", ("price", "<", 30), None),
        ("events", ("ts", ">", 250), None),
        ("events", ("kind", "=", "login"), None),
        ("orders", ("user_id", "=", 8), None),
    ]
    for (t, pred, _x) in counts:
        cols = CATALOG[t]["columns"]
        rows = TABLES[t]
        if pred is not None:
            i1 = cols.index(pred[0])
            rows = tuple(r for r in rows if _cmp(r[i1], pred[1], pred[2]))
        sql = "SELECT COUNT(*) FROM %s" % (t,)
        if pred is not None:
            sql += " WHERE %s %s %r" % (pred[0], pred[1], pred[2])
        queries.append(_q(len(queries) + 1, sql, ((len(rows),),)))

    return tuple(queries)


def _cmp(a, op, b):
    """One predicate, as `ops.compare` spells it — the world uses the same
    comparison law it hands the stages."""
    import ops
    return ops.compare(a, op, b)


QUERIES = _build_queries()

#: the plan facts, pinned per query. The events index is a B+tree over
#: (ts, id). A query whose WHERE names only `events.ts` is measured on the
#: rows themselves: if its conjuncts match at most a quarter of the table,
#: the index earns its keep and `uses_index` is pinned True; otherwise the
#: scan is cheaper and it is pinned False. Every other query is pinned False
#: outright — planning an index scan over `items` would be a mistake the
#: plan stage exists to catch, and the EXPLAIN has to say so.


def _ts_conjuncts(sql):
    """The `ts <op> <value>` conjuncts of an events WHERE, or None when the
    WHERE names anything else (a column the index cannot serve)."""
    if " FROM events " not in sql or " WHERE " not in sql:
        return None
    where = sql.split(" WHERE ", 1)[1]
    where = where.split(" ORDER BY ")[0]
    conjuncts = []
    for chunk in where.split(" AND "):
        parts = chunk.strip().rsplit(" ", 2)
        if len(parts) != 3 or parts[0] != "ts":
            return None
        value = eval(parts[2]) if parts[2].isdigit() else None  # noqa: S307
        if value is None:
            return None
        conjuncts.append((parts[1], value))
    return conjuncts


def _pin_plan_facts():
    """Pin `uses_index` on every query, from the rows' own arithmetic."""
    total = len(TABLES["events"])
    pinned = []
    for query in QUERIES:
        conjuncts = _ts_conjuncts(query["sql"])
        if conjuncts is None:
            query["uses_index"] = False
            continue
        matched = [r for r in TABLES["events"]
                   if all(_cmp(r[1], op, v) for (op, v) in conjuncts)]
        query["uses_index"] = len(matched) <= total // 4
        pinned.append((query["id"], query["uses_index"]))
    return pinned


PLAN_FACTS = tuple(_pin_plan_facts())
_INDEXED_IDS = tuple(qid for (qid, uses) in PLAN_FACTS if uses)

# --- loading the world onto pages ---------------------------------------------


def load_world(pager):
    """The tables, encoded onto the pages `TABLE_PAGES` pins: table t's rows
    in row order, each page holding as many whole records as fit (a record is
    length-prefixed; the count rides the page's first byte, then the records
    back to back). The layout recovery is graded against. Syncs once at the
    end — the world's own first barrier, before any stage runs."""
    import pages as pg
    for table, page_nums in TABLE_PAGES.items():
        records = [pg.Pager.encode(row) for row in TABLES[table]]
        for page_num in page_nums:
            body = bytearray(pg.PAGE_SIZE)
            room = pg.PAGE_SIZE - 2
            count = 0
            at = 1
            while records and len(records[0]) + 1 <= room:
                rec = records.pop(0)
                body[at] = len(rec)
                body[at + 1:at + 1 + len(rec)] = rec
                at += 1 + len(rec)
                room -= 1 + len(rec)
                count += 1
            body[0] = count
            pager.write(page_num, bytes(body))
        if records:
            raise ValueError("table %s does not fit its pinned pages" % (table,))
    pager.sync()
    return TABLE_PAGES


def page_rows(pager, page):
    """The records one table page holds: the count byte, then per record one
    length byte and the record's own bytes."""
    import pages as pg
    raw = pager.read(page)
    count = raw[0]
    rows = []
    at = 1
    for _ in range(count):
        rec_len = raw[at]
        rows.append(pg.Pager.decode(raw[at + 1:at + 1 + rec_len]))
        at += 1 + rec_len
    return tuple(rows)


# --- the crash schedule ---------------------------------------------------------

#: the crash schedule: every fixture recovery is graded on. Each entry is a
#: phase the world runs a transaction workload through, then a `power_fail`
#: with or without a tear, then the recovered state's facts. `committed` is
#: what a correct recovery must leave (the transactions whose commit the log
#: made durable before the crash); `uncommitted` is what it must roll back.
CRASH_SCHEDULE = (
    {"name": "clean",
     "transactions": (
         {"name": "t1", "ops": (("insert", "orders", (41, 8, 100, "open")),
                                ("update", "orders", 1, 2, "total")),
          "commits": True},),
     "tear": False},
    {"name": "uncommitted-loss",
     "transactions": (
         {"name": "t1", "ops": (("insert", "orders", (42, 3, 55, "paid")),),
          "commits": True},
         {"name": "t2", "ops": (("insert", "orders", (43, 5, 60, "open")),),
          "commits": False},),
     "tear": False},
    {"name": "torn-log",
     "transactions": (
         {"name": "t1", "ops": (("insert", "orders", (44, 1, 10, "open")),),
          "commits": True},),
     "tear": True},
    {"name": "many-uncommitted",
     "transactions": (
         {"name": "t1", "ops": (("insert", "items", (80, 1, 5)),),
          "commits": True},
         {"name": "t2", "ops": (("insert", "items", (81, 2, 6)),),
          "commits": False},
         {"name": "t3", "ops": (("insert", "items", (82, 3, 7)),),
          "commits": False},
         {"name": "t4", "ops": (("insert", "items", (83, 4, 8)),),
          "commits": True},),
     "tear": False},
)
