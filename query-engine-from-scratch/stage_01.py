"""Query Engine From Scratch — stage 1: The parse: words, trees, and the five
refusals.

A query is text before it is anything else, and the parse is the one stage
whose product every later stage consumes: `tokenize` splits the SQL into
words, ints, quoted strings and operators; `parse` turns the tokens into the
tree the resolver will walk — the select list, the table, the joins with their
ON columns, the WHERE's raw conjuncts, the ORDER BY with its direction, the
LIMIT. Nothing here looks at the catalog or the rows: a parse that knows what
a `users` is would be a resolver wearing a parser's coat.

The stage's discipline is the closed five. `PARSE_ERRORS` names every way a
query can be *shaped* wrong — `empty`, `no_from`, `bad_column`, `bad_op`,
`bad_value` — and every refusal carries the token that earned it. A column
the catalog never heard of parses fine (`bad_column` is about the select
list's shape, not the catalog's truth), and a WHERE against a nonexistent
table parses fine. The parse refuses only what the words themselves get
wrong.

DESIGN DECISION — Why does the tree answer *raw* conjuncts rather than parsed
column/op/value triples?
Because a conjunct's meaning — which table a bare column belongs to, whether
the value's type fits — is the resolver's question. The parse's WHERE is the
words in order; the resolve turns them into names.

DESIGN DECISION — Why is `COUNT(*)` a *select* shape and not a column?
Because the aggregate changes what the executor answers (one row, one count —
not the table's rows projected), and the select list is where that answer is
declared. A tree with `"COUNT(*)"` in `select` and an empty `columns` is the
shape the executor branches on.

DESIGN DECISION — Why do the refusals raise instead of answering an error
field?
Because a parse error is a caller's mistake by definition — the SQL was
shaped wrong before any engine ran — so `QueryError` with the reason word and
the token is the record. An error field would let a malformed tree travel
into the resolver, where its diagnosis would be a lie.
"""

import ops

TOKEN_KINDS = ("word", "int", "string", "op")
PARSE_KEYS = ("select", "columns", "table", "joins", "where", "order", "limit")
PARSE_ERRORS = ("empty", "no_from", "bad_column", "bad_op", "bad_value")

KEYWORDS = ("SELECT", "FROM", "JOIN", "ON", "WHERE", "AND", "ORDER", "BY",
            "DESC", "ASC", "LIMIT", "COUNT")

# Punctuation that rides as a word token: separators and the COUNT(*) shapes.
_WORD_PUNCT = {",", "*", "(", ")", "."}
_IDENT_EXTRA = set("0123456789_")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, token):
    raise QueryError("%s: %r" % (reason, token))


def tokenize(sql):
    """The words, the ints, the quoted strings, the operators.

    Answers a list of `(kind, value)` tokens, `kind` one of TOKEN_KINDS. A
    quoted string survives with its quotes stripped; an int is digits; a word
    is letters (uppercased when it is a keyword, left alone otherwise); an op
    is one of `ops.OPS` — anything else refuses as `bad_op`, naming it."""
    if not isinstance(sql, str):
        _refuse("bad_op", sql)
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        if c == "'":
            end = sql.find("'", i + 1)
            if end < 0:
                _refuse("bad_value", sql[i:])
            tokens.append(("string", sql[i + 1:end]))
            i = end + 1
            continue
        if c.isdigit():
            j = i
            while j < n and sql[j].isdigit():
                j += 1
            tokens.append(("int", int(sql[i:j])))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (sql[j].isalpha() or sql[j] in _IDENT_EXTRA):
                j += 1
            word = sql[i:j]
            if word.upper() in KEYWORDS:
                word = word.upper()
            tokens.append(("word", word))
            i = j
            continue
        if c in _WORD_PUNCT:
            tokens.append(("word", c))
            i += 1
            continue
        two = sql[i:i + 2]
        if two in ops.OPS:
            tokens.append(("op", two))
            i += 2
            continue
        if c in ops.OPS:
            tokens.append(("op", c))
            i += 1
            continue
        _refuse("bad_op", c)
    return tokens


def _take_word(tokens, i, reason):
    """One identifier token, or the refusal that names why not."""
    if i >= len(tokens):
        _refuse(reason, "end of query")
    kind, value = tokens[i]
    if kind != "word" or value in KEYWORDS or value in _WORD_PUNCT:
        _refuse(reason, value)
    return value, i + 1


def parse(sql):
    """The tree: select, columns, table, joins, where, order, limit.

    Answers PARSE_KEYS from the tokens `tokenize` made — `select` is the
    string "columns" or "COUNT(*)", `columns` the select list's words, `joins`
    a tuple of `(left, right, on_left, on_right)`, `where` the raw conjunct
    tokens in order, `order` a `(column, desc)` or None, `limit` an int or
    None. The five refusals are `PARSE_ERRORS`, each naming its token."""
    tokens = tokenize(sql)
    if not tokens:
        _refuse("empty", sql)

    # --- the select list, up to FROM -------------------------------------
    if tokens[0] != ("word", "SELECT"):
        _refuse("bad_op", tokens[0])
    i = 1
    select = "columns"
    columns = []
    if i < len(tokens) and tokens[i] == ("word", "*"):
        select = "*"
        i += 1
    elif (i + 3 < len(tokens) and tokens[i] == ("word", "COUNT")
          and tokens[i + 1] == ("word", "(") and tokens[i + 2] == ("word", "*")
          and tokens[i + 3] == ("word", ")")):
        select = "COUNT(*)"
        i += 4
    else:
        expect_word = True
        while i < len(tokens) and tokens[i] != ("word", "FROM"):
            kind, value = tokens[i]
            if expect_word:
                if kind == "int":
                    _refuse("bad_column", value)
                if kind != "word" or value in KEYWORDS or value in _WORD_PUNCT:
                    _refuse("bad_column", value)
                columns.append(value)
                if i + 1 < len(tokens) and tokens[i + 1] == ("word", "."):
                    if i + 2 >= len(tokens):
                        _refuse("bad_column", ".")
                    columns[-1] = value + "." + tokens[i + 2][1]
                    i += 2
                expect_word = False
            else:
                if (kind, value) != ("word", ","):
                    _refuse("no_from", value)
                expect_word = True
            i += 1
        if expect_word and columns:
            _refuse("no_from", "missing FROM after the select list")
    if i >= len(tokens) or tokens[i] != ("word", "FROM"):
        _refuse("no_from", tokens[i][1] if i < len(tokens) else "end of query")
    i += 1

    # --- the FROM table ----------------------------------------------------
    table, i = _take_word(tokens, i, "no_from")

    # --- the joins: LEFT JOIN RIGHT ON left.col = right.col ----------------
    joins = []
    while i < len(tokens) and tokens[i] == ("word", "JOIN"):
        right, i = _take_word(tokens, i + 1, "no_from")
        if i >= len(tokens) or tokens[i] != ("word", "ON"):
            _refuse("bad_op",
                    tokens[i][1] if i < len(tokens) else "JOIN without ON")
        i += 1
        left_col, i = _take_word(tokens, i, "bad_column")
        if i >= len(tokens) or tokens[i] != ("word", "."):
            _refuse("bad_op", tokens[i][1] if i < len(tokens) else left_col)
        left_field, i = _take_word(tokens, i + 1, "bad_column")
        if i >= len(tokens) or tokens[i] != ("op", "="):
            _refuse("bad_op",
                    tokens[i][1] if i < len(tokens) else left_field)
        i += 1
        right_col, i = _take_word(tokens, i, "bad_column")
        if i >= len(tokens) or tokens[i] != ("word", "."):
            _refuse("bad_op", tokens[i][1] if i < len(tokens) else right_col)
        right_field, i = _take_word(tokens, i + 1, "bad_column")
        joins.append((table, right, left_col + "." + left_field,
                      right_col + "." + right_field))
        table = right

    # --- the WHERE: raw conjuncts in order ---------------------------------
    where = []
    if i < len(tokens) and tokens[i] == ("word", "WHERE"):
        i += 1
        while True:
            col, i = _take_word(tokens, i, "bad_column")
            if i < len(tokens) and tokens[i] == ("word", "."):
                field, i = _take_word(tokens, i + 1, "bad_column")
                col = col + "." + field
            if i >= len(tokens) or tokens[i][0] != "op":
                _refuse("bad_op", tokens[i][1] if i < len(tokens) else col)
            op = tokens[i][1]
            i += 1
            if i >= len(tokens):
                _refuse("bad_value", "end of query")
            kind, value = tokens[i]
            if kind not in ("int", "string"):
                _refuse("bad_value", value)
            where.append((col, op, value))
            i += 1
            if i < len(tokens) and tokens[i] == ("word", "AND"):
                i += 1
                continue
            break

    # --- ORDER BY column [ASC|DESC] ----------------------------------------
    order = None
    if i < len(tokens) and tokens[i] == ("word", "ORDER"):
        if i + 1 >= len(tokens) or tokens[i + 1] != ("word", "BY"):
            _refuse("bad_op", "ORDER without BY")
        col, i = _take_word(tokens, i + 2, "bad_column")
        if i < len(tokens) and tokens[i] == ("word", "."):
            field, i = _take_word(tokens, i + 1, "bad_column")
            col = col + "." + field
        desc = False
        if i < len(tokens) and tokens[i][0] == "word" \
                and tokens[i][1] in ("ASC", "DESC"):
            desc = tokens[i][1] == "DESC"
            i += 1
        order = (col, desc)

    # --- LIMIT n -------------------------------------------------------------
    limit = None
    if i < len(tokens) and tokens[i] == ("word", "LIMIT"):
        if i + 1 >= len(tokens) or tokens[i + 1][0] != "int":
            _refuse("bad_value",
                    tokens[i + 1][1] if i + 1 < len(tokens) else "end of query")
        limit = tokens[i + 1][1]
        i += 2

    if i != len(tokens):
        _refuse("bad_value", tokens[i])

    return {"select": select, "columns": tuple(columns), "table": table,
            "joins": tuple(joins), "where": tuple(where), "order": order,
            "limit": limit}
