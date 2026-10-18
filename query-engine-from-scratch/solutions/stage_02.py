"""The stage 2 solution: names become addresses, against a catalog that lies."""

import disk as dk
import pages as pg
import tables as tb
import ops

RESOLVE_KEYS = ("select", "columns", "table", "joins", "where", "order",
                "limit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, name, table):
    """The one refusal: a reason word, the name, the table it was asked in."""
    raise QueryError("%s: %r in %r" % (reason, name, table))


def columns_of(table, catalog):
    """The table's columns, in order — the catalog's promise, one door."""
    if table not in catalog:
        _refuse("no_table", table, "catalog")
    return tuple(catalog[table]["columns"])


def check_value(column, value):
    """The literal's column holds against the catalog — the real one.

    `column` is the qualified form the resolve vets: `users.email` is checked
    against `tables.CATALOG`, where `users` has no `email` — so a catalog that
    declares the lie is caught here, never trusted. The value answers
    unchanged; the type law lives in the record format, not here."""
    table, name = column.split(".", 1)
    if table not in tb.CATALOG or name not in tb.CATALOG[table]["columns"]:
        _refuse("no_column", name, table)
    return value


def resolve(tree, catalog):
    """Every column becomes (table, index); every name is checked twice —
    once in the catalog the resolve was handed, once against the truth."""

    def owner_of(ref):
        """The dotted ref's owner, or the resolve's base table for a bare one."""
        if "." in ref:
            return ref.split(".", 1)
        return tree["table"], ref

    def place(ref):
        """One column ref to its (table, index) address, vetted against truth."""
        owner, name = owner_of(ref)
        columns = columns_of(owner, catalog)
        if name not in columns:
            _refuse("no_column", name, owner)
        check_value("%s.%s" % (owner, name), None)
        return (owner, columns.index(name))

    def vet_table(name):
        """A table exists in the catalog handed in — and on the real floor."""
        columns_of(name, catalog)
        if name not in tb.CATALOG:
            _refuse("no_table", name, "catalog")

    vet_table(tree["table"])
    for _left, right, on_left, on_right in tree["joins"]:
        vet_table(right)
        place(on_left)
        place(on_right)
    if tree["order"]:
        place(tree["order"][0])
    return {
        "select": tree["select"],
        "columns": tuple(place(ref) for ref in tree["columns"]),
        "table": tree["table"],
        "joins": tuple((left, right, place(on_left), place(on_right))
                       for (left, right, on_left, on_right) in tree["joins"]),
        "where": tuple((place(ref), op, value)
                       for (ref, op, value) in tree["where"]),
        "order": (place(tree["order"][0]), tree["order"][1])
        if tree["order"] else None,
        "limit": tree["limit"],
    }
