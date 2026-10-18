"""The stage 1 solution: the tokenizer, the tree, and the five refusals."""

import disk as dk
import pages as pg
import tables as tb
import ops

TOKEN_KINDS = ("word", "int", "string", "op")
PARSE_KEYS = ("select", "columns", "table", "joins", "where", "order", "limit")
PARSE_ERRORS = ("empty", "no_from", "bad_column", "bad_op", "bad_value")

KEYWORDS = ("SELECT", "FROM", "JOIN", "ON", "WHERE", "AND", "ORDER", "BY",
            "DESC", "ASC", "LIMIT", "COUNT")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, token):
    """The one refusal: a PARSE_ERRORS word and the token that earned it."""
    raise QueryError("%s: %r" % (reason, token))


def tokenize(sql):
    """Words, ints, quoted strings, operators — and a refusal for the rest."""
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch in " \t":
            i += 1
            continue
        if ch == "'":
            end = sql.find("'", i + 1)
            if end < 0:
                _refuse("bad_value", sql[i:])
            tokens.append(("string", sql[i + 1:end]))
            i = end + 1
            continue
        if ch.isdigit():
            j = i
            while j < n and sql[j].isdigit():
                j += 1
            tokens.append(("int", int(sql[i:j])))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j]
            if word.upper() in KEYWORDS:
                tokens.append(("word", word.upper()))
            else:
                tokens.append(("word", word))
            i = j
            continue
        two = sql[i:i + 2]
        if two in ("<=", ">=", "!="):
            tokens.append(("op", two))
            i += 2
            continue
        if ch in ("<", ">", "="):
            tokens.append(("op", ch))
            i += 1
            continue
        if ch in "()*,.":       # the dot rides between a table and a column
            tokens.append(("word", ch))
            i += 1
            continue
        _refuse("bad_op", ch)
    return tokens


def parse(sql):
    """The tree the resolver walks, and the five refusals."""
    tokens = tokenize(sql)
    if not tokens:
        _refuse("empty", sql)
    at = 0

    def peek():
        return tokens[at] if at < len(tokens) else (None, None)

    def take():
        nonlocal at
        token = tokens[at]
        at += 1
        return token

    def need(word):
        kind, value = peek()
        if kind != "word" or value != word:
            if word == "FROM":
                _refuse("no_from", value if kind else "end")
            _refuse("bad_value", value if kind else "end")
        return take()

    # --- the select list -----------------------------------------------------
    if peek() != ("word", "SELECT"):
        _refuse("bad_column", peek()[1])
    take()
    if peek() == ("word", "COUNT"):
        take()
        if take()[1] != "(" or take()[1] != "*":
            _refuse("bad_column", "*")
        if take()[1] != ")":
            _refuse("bad_column", ")")
        select, columns = "COUNT(*)", ()
    elif peek() == ("word", "*"):
        take()
        select, columns = "*", ()
    else:
        names = []
        while True:
            kind, value = peek()
            if kind != "word" or value in KEYWORDS or value in "(*,":
                _refuse("bad_column", value)
            names.append(value)
            take()
            if peek() == ("word", ","):
                take()
                continue
            break
        select, columns = "columns", tuple(names)

    # --- FROM, and the table --------------------------------------------------
    need("FROM")
    kind, table = peek()
    if kind != "word" or table in KEYWORDS or table in "(*,":
        _refuse("no_from", table)
    take()

    # --- the joins ------------------------------------------------------------
    joins = []
    while peek() == ("word", "JOIN"):
        take()
        kind, right = peek()
        if kind != "word" or right in KEYWORDS:
            _refuse("no_from", right)
        take()
        need("ON")
        on_left = _column_ref(take, peek)
        if take()[1] != "=":
            _refuse("bad_op", "=")
        on_right = _column_ref(take, peek)
        joins.append((table, right, on_left, on_right))
        table = right

    # --- WHERE: the raw conjuncts, in order -----------------------------------
    where = []
    if peek() == ("word", "WHERE"):
        take()
        while True:
            left = _column_ref(take, peek)
            kind, op = peek()
            if kind != "op":
                _refuse("bad_op", op)
            take()
            kind, value = peek()
            if kind == "int":
                take()
            elif kind == "string":
                take()
            elif kind == "word" and value not in KEYWORDS:
                _refuse("bad_value", value)
            elif kind == "word":
                _refuse("bad_value", value)
            else:
                _refuse("bad_value", value)
            where.append((left, op, value))
            if peek() == ("word", "AND"):
                take()
                continue
            break

    # --- ORDER BY, LIMIT --------------------------------------------------------
    order = None
    if peek() == ("word", "ORDER"):
        take()
        if take()[1] != "BY":
            _refuse("bad_column", "BY")
        order = (_column_ref(take, peek), False)
        if peek() == ("word", "DESC"):
            take()
            order = (order[0], True)
        elif peek() == ("word", "ASC"):
            take()
    limit = None
    if peek() == ("word", "LIMIT"):
        take()
        kind, value = peek()
        if kind != "int":
            _refuse("bad_value", value)
        take()
        limit = value

    if at != len(tokens):
        _refuse("bad_value", tokens[at][1])
    return {"select": select, "columns": columns, "table": table,
            "joins": tuple(joins), "where": tuple(where),
            "order": order, "limit": limit}


def _column_ref(take, peek):
    """One column reference: a word, or table.column — the qualified form
    answers as the dotted string the resolver will split."""
    kind, value = peek()
    if kind != "word" or value in KEYWORDS or value in "(*,":
        _refuse("bad_column", value)
    take()
    if peek() == ("word", "."):
        take()
        kind, column = peek()
        if kind != "word" or column in KEYWORDS or column in "(*,.":
            _refuse("bad_column", column)
        take()
        return "%s.%s" % (value, column)
    return value
