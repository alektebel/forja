"""Query Engine From Scratch — stage 6: The executor: iterators over pages.

TODO: implement each function; the docstring is the contract.
The plan named the route; the executor walks it. `seq_scan` yields a table's
records from its pinned pages, in row order — the page count it reads is the
world's own `TABLE_PAGES`, and the check holds it against the disk's
`counters()`, because an executor that guessed a page would be an executor
the storage floor cannot audit. `index_scan` yields the rows a tree range
names, in key order, off the leaf chain stage 4 linked. `nested_loop` joins
two iterators on the resolved `on` columns — left outer, right inner, left
order preserved — the only join whose correctness is obvious and whose cost
the plan already priced. `execute` wires the plan's operators into one
pipeline and answers EXEC_KEYS: the rows (the reference's, by law 13 — the
pin is the law), the pages read, and the operator chain as a tuple of names,
so the check can hold what ran against what was planned.

The hundred queries run through it in stage 10; this stage's check runs the
shapes first — a scan, a range, a join, a filter — and then the hundred.

DESIGN DECISION — Why iterators rather than lists?
Because a query's answer can outsize its pages: the join's product is built
lazily, the LIMIT stops the pipeline mid-scan, and the pages-read record
stays honest only if the pipeline reads what it consumes. A list would
materialize a quarter million pairs before the first LIMIT row; an iterator
stops. The check's counters catch the difference.

DESIGN DECISION — Why is `nested_loop` the only join?
Because the course's joins are small (twenty rows against forty) and the
lesson is the order, not the algorithm: left outer, right inner, left order
preserved. A hash join would hide the order inside a bucket; a sort-merge
would sort what stage 3 already ordered. The nested loop's cost is the one
the plan priced (each side's pages times the other's rows), and the
executor's product is checkable against the world's own join arithmetic.

DESIGN DECISION — Why does `execute` answer the operator chain as names?
Because the record is the audit trail: the plan chose a route, and the
chain is what actually ran. A plan that named an index scan and an executor
that ran the table would agree on rows and disagree on pages — the counters
catch it — but the chain names the difference in the record itself.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

EXEC_KEYS = ("rows", "pages", "operators")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def seq_scan(pager, table):
    """A table's records, in row order, off its pinned pages.

    Yields the rows as the world's `TABLES` holds them — reading exactly
    `TABLE_PAGES[table]`'s pages. Refuses a table the world does not pin."""

    raise NotImplementedError("stage 6: implement seq_scan()")


def index_scan(tree, lo, hi):
    """The rows whose keys fall in [lo, hi], in key order.

    Yields the index's (key, rid) entries for the range, following the leaf
    chain stage 4 linked — then the caller fetches the rows themselves."""

    raise NotImplementedError("stage 6: implement index_scan()")


def nested_loop(left, right, on):
    """The join: left outer, right inner, left order preserved.

    `on` is `(left_index, right_index)` — the resolved column addresses the
    plan carries. Yields `left_row + right_row` for every pair whose columns
    compare equal, in the order the loops run."""

    raise NotImplementedError("stage 6: implement nested_loop()")


def execute(plan, pager):
    """The pipeline: the plan's operators, one answer.

    Answers EXEC_KEYS — the rows (the reference's, by law 13), the pages
    read, and the operator chain as a tuple of names. The hundred queries
    run through it in stage 10."""

    raise NotImplementedError("stage 6: implement execute()")
