"""Query Engine From Scratch — stage 1: The parse: words, trees, and the five
refusals.


TODO: implement each function; the docstring is the contract.
A query is text before it is anything else, and the parse is the one stage
whose product every later stage consumes: `tokenize` splits the SQL into
words, ints, quoted strings and operators; `parse` turns the tokens into the
tree the resolver will walk — the select list, the table, the joins with their
ON columns, the WHERE's raw conjuncts, the ORDER BY with its direction, the
LIMIT. Nothing here looks at the catalog or the rows: a parse that knows what
a `users` is would be a resolver wearing a parser's coat.

The stage's discipline is the closed five. `PARSE_ERRORS` names every way a
query can be *shaped* wrong — `empty`, `no_from`, `bad_column`, `bad_op`,
`bad_value` — and every refusal carries the token that earned it, because a
parse error that does not say where is a puzzle, not a diagnosis. What is
*not* here matters as much: a column the catalog never heard of parses fine
(`bad_column` is about the select list's shape, not the catalog's truth — that
is stage 2's job), and a WHERE against a nonexistent table parses fine. The
parse refuses only what the words themselves get wrong.

DESIGN DECISION — Why does the tree answer *raw* conjuncts rather than parsed
column/op/value triples?
Because a conjunct's meaning — which table a bare column belongs to, whether
the value's type fits — is the resolver's question, and answering it here
would mean the parser resolves. The parse's WHERE is the words in order; the
resolve turns them into names. Every later stage reads the resolved form, and
the check holds the raw form against the SQL it came from.

DESIGN DECISION — Why is `COUNT(*)` a *select* shape and not a column?
Because the aggregate changes what the executor answers (one row, one count —
not the table's rows projected), and the select list is where that answer is
declared. A tree with `"COUNT(*)"` in `select` and an empty `columns` is the
shape the executor branches on; hiding the aggregate inside a fake column
would make the executor parse.

DESIGN DECISION — Why do the refusals raise instead of answering an error
field?
Because law 12's line is the world's: a caller's mistake raises, naming the
offender. A parse error is a caller's mistake by definition — the SQL was
shaped wrong before any engine ran — so `QueryError` with the reason word and
the token is the record. An error field would let a malformed tree travel
into the resolver, where its diagnosis would be a lie.
"""

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


def tokenize(sql):
    """The words, the ints, the quoted strings, the operators.

    Answers a list of `(kind, value)` tokens, `kind` one of TOKEN_KINDS. A
    quoted string survives with its quotes stripped; an int is digits; a word
    is letters (uppercased when it is a keyword, left alone otherwise); an op
    is one of `ops.OPS` — anything else refuses as `bad_op`, naming it."""

    raise NotImplementedError("stage 1: implement tokenize()")


def parse(sql):
    """The tree: select, columns, table, joins, where, order, limit.

    Answers PARSE_KEYS from the tokens `tokenize` made — `select` is the
    string "columns" or "COUNT(*)", `columns` the select list's words, `joins`
    a tuple of `(left, right, on_left, on_right)`, `where` the raw conjunct
    tokens in order, `order` a `(column, desc)` or None, `limit` an int or
    None. The five refusals are `PARSE_ERRORS`, each naming its token."""

    raise NotImplementedError("stage 1: implement parse()")
