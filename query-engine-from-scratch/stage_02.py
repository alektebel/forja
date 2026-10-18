"""Query Engine From Scratch — stage 2: The resolve: names against a catalog
that may lie.

The parse answered shapes; the resolve answers *names*. Every column the tree
carries becomes `(table, index)` — the address the executor will index rows
with — and every table is checked to exist in the catalog it is resolved
against. The catalog is a parameter, not a fact: `resolve(tree, CATALOG)` is
the honest query, and `resolve(tree, CATALOG_LIES)` is the same tree walked
against a catalog that declares `email` on `users` and a `phantom` table. The
resolver trusts nothing; a name the lying catalog offers must be caught, never
carried into a resolved tree, because a resolved tree is the executor's
contract with the storage floor — an index into a row that does not exist is
not a slow query, it is a wrong one.

DESIGN DECISION — Why does the resolved tree keep the resolve's shape rather
than annotating the parse tree?
Because the executor reads a resolved form, and a resolved form that still
carries strings for columns would force the executor to resolve — the exact
smuggle stage 1 refused in the other direction. The resolve answers its own
RESOLVE_KEYS tree: same keys, every column replaced by `(table, index)`, so
later stages never touch a bare name again.

DESIGN DECISION — Why is `columns_of` a separate way in rather than a
dictionary access the stages could each inline?
Because the columns of a table are the catalog's promise, and the promise has
one door: every stage that needs a table's shape asks `columns_of`, so when
the catalog lies the fix lands in one place. A stage reaching past it would
read the lie directly.

DESIGN DECISION — Why does `check_value` check the column's existence and
answer the value unchanged otherwise?
Because the value's *type* checking is the storage floor's law (the record
format already refuses what does not encode); what the resolve owns is the
*name*: `check_value` is the door a conjunct walks through to learn that the
column it compares against exists — and against `CATALOG_LIES`, that `email`
is exactly the kind of name that must be refused, naming the lie.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

RESOLVE_KEYS = ("select", "columns", "table", "joins", "where", "order",
                "limit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def columns_of(table, catalog):
    """The table's columns, in order, from the catalog it is looked up in.

    Refuses a table the catalog does not declare, naming both the table and
    the catalog it was looked up in."""

    raise NotImplementedError("stage 2: implement columns_of()")


def check_value(column, value):
    """The value a literal resolves to under the column's declared type.

    Refuses a column the catalog does not declare — `CATALOG_LIES` declares
    `email` on `users`, and the check must catch the lie, not pass it through.
    Otherwise answers the value."""

    raise NotImplementedError("stage 2: implement check_value()")


def resolve(tree, catalog):
    """The resolved tree: every column a (table, index), every name checked.

    Walks the parse tree and answers RESOLVE_KEYS with every column replaced
    by `(table, index)` — the address the executor indexes rows with. Refuses
    naming the offending name and the table it was looked up in."""

    raise NotImplementedError("stage 2: implement resolve()")
