"""Query Engine From Scratch — stage 2: The resolve: names against a catalog
that may lie.

The parse answered shapes; the resolve answers *names*. Every column the tree
carries becomes `(table, index)` — the address the executor will index rows
with — and every table is checked to exist. The catalog is a parameter, not a
fact, and the world ships one that lies: `CATALOG_LIES` declares `email` on
`users` and a `phantom` table. The resolver trusts nothing — a name only the
lying catalog declares is caught, never carried into a resolved tree, because
a resolved tree is the executor's contract with the storage floor: an index
into a row that does not exist is not a slow query, it is a wrong one.

DESIGN DECISION — Why does the resolved tree keep the resolve's shape rather
than annotating the parse tree?
Because the executor reads a resolved form, and a resolved form that still
carries strings for columns would force the executor to resolve — the exact
smuggle stage 1 refused in the other direction. The resolve answers its own
RESOLVE_KEYS tree: same keys, every column replaced by `(table, index)`.

DESIGN DECISION — Why is `columns_of` a separate way in rather than a
dictionary access the stages could each inline?
Because the columns of a table are the catalog's promise, and the promise has
one door: every stage that needs a table's shape asks `columns_of`, so when
the catalog lies the fix lands in one place.

DESIGN DECISION — Why does `check_value` judge the name against the truth and
answer the value unchanged?
Because the value's *type* checking is the storage floor's law; what the
resolve owns is the *name*. `check_value` is the door a conjunct walks
through to learn the column it compares against exists — and `email`, which
only the lying catalog declares, is exactly the kind of name that must be
refused, naming the lie. The truth is the judge, never the catalog under test.
"""

import tables as tb

RESOLVE_KEYS = ("select", "columns", "table", "joins", "where", "order",
                "limit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def columns_of(table, catalog):
    """The table's columns, in order, from the catalog it is looked up in.

    Refuses a table the catalog does not declare, naming both the table and
    the catalog it was looked up in."""
    entry = catalog.get(table)
    if entry is None:
        _refuse("no_table", table, catalog)
    return entry["columns"]


def check_value(column, value):
    """The value a literal resolves to under the column's declared type.

    Refuses a column the truth does not declare — `CATALOG_LIES` declares
    `email` on `users`, and the check catches the lie, not passes it through.
    Otherwise answers the value unchanged."""
    if "." in column:
        owner, name = column.split(".", 1)
    else:
        owner, name = None, column
    entry = tb.CATALOG.get(owner)
    if entry is None or name not in entry["columns"]:
        _refuse("no_column", column, owner)
    return value


def _address(name, base, catalog):
    """One column name as `(owner, index)`, the truth judging the name.

    A bare name owns the base table — the tree's final table, so a bare name
    in a joined query binds to the join's right side. A qualified name owns
    the table it names."""
    if "." in name:
        owner, col = name.split(".", 1)
    else:
        owner, col = base, name
    if owner not in tb.CATALOG:
        _refuse("no_table", owner, tb.CATALOG)
    truth = tb.CATALOG[owner]["columns"]
    if col not in truth:
        _refuse("no_column", col, owner)
    # the catalog under test must also carry the table: a shape it does not
    # declare is a table it does not have
    columns_of(owner, catalog)
    return (owner, truth.index(col))


def resolve(tree, catalog):
    """The resolved tree: every column a (table, index), every name checked.

    Walks the parse tree and answers RESOLVE_KEYS with every column replaced
    by `(table, index)` — the address the executor indexes rows with. Refuses
    naming the offending name and the table it was looked up in."""
    base = tree["table"]
    if base not in tb.CATALOG:
        _refuse("no_table", base, tb.CATALOG)

    columns = tuple(_address(name, base, catalog) for name in tree["columns"])

    joins = []
    for (left, right, on_left, on_right) in tree["joins"]:
        joins.append((left, right,
                      _address(on_left, base, catalog),
                      _address(on_right, base, catalog)))

    where = tuple((_address(col, base, catalog), op, value)
                  for (col, op, value) in tree["where"])

    order = None
    if tree["order"] is not None:
        order = (_address(tree["order"][0], base, catalog), tree["order"][1])

    return {"select": tree["select"], "columns": columns, "table": base,
            "joins": tuple(joins), "where": where, "order": order,
            "limit": tree["limit"]}
