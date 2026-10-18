"""Query Engine From Scratch — stage 6: The executor: iterators over pages.


TODO: implement each function; the docstring is the contract.
The plan named the scans; the executor runs them and answers the rows — the
world's rows, exactly, by law 13: the pin is law, and an executor that
answered a row the reference does not hold is wrong whatever else it got
right. `seq_scan` yields a table's records from its pages in row order — the
same pages `load_world` filled, read back through the pager. `index_scan`
yields the entries a tree range names, following the leaf chain, and fetches
the rows whose keys fall in the range, in key order — the order the index
imposes, not the order the rows were stored. `nested_loop` joins two
iterators on the resolved ON columns, left outer, right inner, left order
preserved — the join's cost is quadratic and stage 3's pushdown is why some
rows never reach it. `execute` wires the plan's operators into one pipeline
and answers the rows, the pages read, and the chain as a tuple of names —
the record the proof (stage 10) holds against the world's hundred.

DESIGN DECISION — Why iterators rather than lists?
Because a pipeline that materializes every intermediate answer pays for rows
it never yields — LIMIT 8 on a hundred-row scan reads eight rows' worth, not
the table. The iterators here are simple generators, and the record's page
count is the receipt: the check holds `execute`'s reads against the plan's
cost, and a materializing executor's receipt would not fit.

DESIGN DECISION — Why does `execute` answer the operator chain as names?
Because the proof's verdicts distinguish `wrong_rows` from a pipeline that
ran the wrong operators: the same rows from a `table` scan the plan chose
`index` for is law 14's violation, not law 13's. The chain is the plan made
observable; the rows are the world made observable; the record carries both.

DESIGN DECISION — Why does the index scan fetch rows rather than yield
entries?
Because the query's answer is rows, and an executor that yields (ts, id)
pairs hands the caller its own plumbing. The fetch is the index's promise —
each entry names a row by its id — and the check holds the fetched rows
against the table's own, in key order.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

EXEC_KEYS = ("rows", "pages", "chain")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def seq_scan(pager, table):
    """A table's records from its pages, in row order — an iterator.

    Reads exactly `TABLE_PAGES[table]`'s pages, in order; each page's
    records yield as `page_rows` spells them."""

    raise NotImplementedError("stage 6: implement seq_scan()")


def index_scan(pager, lo, hi):
    """The rows whose ts falls in [lo, hi], in key order — an iterator.

    Walks the tree's leaf chain (stage 4's range answer), fetches each
    entry's row from events by its id."""

    raise NotImplementedError("stage 6: implement index_scan()")


def nested_loop(left, right, left_on, right_on):
    """The join: left outer, right inner, left order preserved.

    Yields left-row + right-row tuples where the ON columns compare equal
    under the world's own comparison law."""

    raise NotImplementedError("stage 6: implement nested_loop()")


def execute(pager, tree, plan_record):
    """The pipeline: the rows, the pages read, the chain as names.

    Runs the plan's scans (seq or index, as the plan chose), the join when
    the tree has one, the WHERE conjuncts, the projection or COUNT, the
    ORDER BY, the LIMIT. Answers EXEC_KEYS: the rows (the reference's, by
    law 13), the pages read, and the operator chain as a tuple of names."""

    raise NotImplementedError("stage 6: implement execute()")
