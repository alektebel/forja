"""The operators, as data: the closed vocabulary and the comparison law.

A query engine's grammar is only as closed as its operator set, and the only
honest way to keep it closed is to make the operators *data* a stage imports:
`OPS` is the whole vocabulary, `compare` is the one comparison the world runs,
and a predicate outside `OPS` is a parse error (`bad_op`), not a KeyError at
execution time.

`compare` is also the law for the world's own arithmetic — `tables.py` built
the hundred queries' expected rows with exactly this function, so a stage that
compares some other way is wrong by the reference's definition, not by taste.
The values it compares are the grammar's: ints and short strings, with the
type check done once, here — comparing an int to a string raises, naming both,
because a WHERE that mixes types is a caller's mistake (law 12) and not a
runtime outcome.
"""

OPS = ("=", "!=", "<", "<=", ">", ">=")


class OpError(ValueError):
    """Raised for anything the *caller* of this module got wrong."""


def compare(a, op, b):
    """One comparison, as the closed vocabulary spells it.

    The law: `=` and `!=` compare by value with the types' own equality;
    the four ordered ops refuse a mixed int/string pair — an ordering across
    types is not defined, and pretending it is would make `ORDER BY` a lie.
    """
    if op not in OPS:
        raise OpError("unknown op %r (the vocabulary is %s)" % (op, ", ".join(OPS)))
    mixed = (isinstance(a, str) != isinstance(b, str))
    if op not in ("=", "!=") and mixed:
        raise OpError("an ordered comparison of %r and %r mixes types"
                      % (a, b))
    if op == "=":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    return a >= b
