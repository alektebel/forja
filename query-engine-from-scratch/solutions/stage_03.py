"""The stage 3 solution: every conjunct a table, every conjunct a home."""

import disk as dk
import pages as pg
import tables as tb
import ops

PRED_KEYS = ("conjuncts", "pushed", "both")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the conjunct that earned it."""
    raise QueryError("%s: %r" % (reason, what))


def conjuncts_of(where):
    """The resolved WHERE as (table, column, op, value), in order."""
    out = []
    for conjunct in where:
        if not (isinstance(conjunct, tuple) and len(conjunct) == 3
                and isinstance(conjunct[0], tuple)
                and len(conjunct[0]) == 2):
            _refuse("unresolved", conjunct)
        (table, index), op, value = conjunct
        out.append((table, index, op, value))
    return tuple(out)


def referenced(conjunct, side, tree):
    """Whether one conjunct names one side of the tree's join."""
    if not tree["joins"]:
        return False
    join = tree["joins"][0]
    left, right = join[0], join[1]
    table = conjunct[0]
    if side == "left":
        return table == left
    if side == "right":
        return table == right
    _refuse("no_side", side)


def pushdown(tree):
    """Conjuncts with their tables; per scan what was pushed; what stayed.

    A conjunct naming exactly one of the query's scans is pushed to that
    scan; a conjunct naming two scans (or one appearing twice in a self
    join) names both sides and stays above the join."""
    conjuncts = conjuncts_of(tree["where"])
    joins = tree["joins"]
    if joins:
        scans = [joins[0][0]] + [join[1] for join in joins]
    else:
        scans = [tree["table"]]
    pushed = {scan: () for scan in scans}
    both = ()
    for conjunct in conjuncts:
        homes = tuple(scan for scan in scans if scan == conjunct[0])
        if len(homes) == 1:
            pushed[homes[0]] = pushed[homes[0]] + (conjunct,)
        else:
            both = both + (conjunct,)
    return {"conjuncts": conjuncts,
            "pushed": tuple((scan, pushed[scan]) for scan in scans),
            "both": both}
