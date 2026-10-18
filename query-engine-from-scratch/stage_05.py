"""Query Engine From Scratch — stage 5: The plan: pushdown, selectivity, and
the earned index.

The predicates stage said where each conjunct goes; the plan says what each
scan costs and which scan to run. `cost_of` prices a scan in pages — a table
scan costs the table's page count, an index scan costs the tree's height plus
the leaves the conjuncts match — and `plan` answers the choice that
comparison made: per scan, `table` or `index`; the conjuncts pushed to it;
the total. The pin (`uses_index`) is not consulted — the pin is the world's
answer the plan must *agree with*, and the check proves the agreement on all
hundred queries. A planner that read the pin would pass every test it was
written against and fail the first query the world had not measured; the
arithmetic — matches ≤ a quarter of the table — is the same arithmetic that
pinned the facts, and it runs here, on the plan's own account.

`explain` renders the record one line wide — `events: index[ts] (ts<=60) |
users: table` — because a plan the user cannot read is a plan the user cannot
argue with, and the check holds the line against the plan's own record, not
against a string the stage was handed.

DESIGN DECISION — Why does `cost_of` take the matched count rather than the
conjuncts?
Because the world pinned its facts on the rows themselves — matched ≤ a
quarter of the table — and the planner must run the *same* arithmetic, not a
recapitulation of it. Deriving matches from the conjuncts here would make the
planner trust its own guess about selectivity; taking the matched count the
world computes (stage 4's `lookup` over the tree, or the count over rows)
keeps one law: the rows are the answer.

DESIGN DECISION — Why does the plan carry the pin it did not use?
Because the record is also the audit's: stage 10's `audit` answers
`wrong_plan` by holding the plan's choice against the world's pinned fact. A
plan that agreed by accident and a plan that agreed by arithmetic look the
same in the record; the check's job is to tell them apart *here*, on all
hundred, by proving the choice changes when the costs change — the mutation
battery plants a planner that reads the pin and the check must catch it.

DESIGN DECISION — Why is `explain` a public way in rather than a repr?
Because the line is a contract: the checks hold it, the tail course greps it,
and a repr is whatever the class felt like. One renderer, one shape, the same
line whether the plan came from a cost comparison or a crash recovery.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

PLAN_KEYS = ("scans", "pushed", "uses_index", "cost")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def cost_of(scan, table, matched, pager=None):
    """A scan's price in pages: the table's pages, or height plus leaves.

    `scan` is `"table"` or `"index"`; `matched` is the rows the conjuncts
    match, the world's own arithmetic. An index scan prices the tree's
    height plus the leaves the matches spread over."""

    raise NotImplementedError("stage 5: implement cost_of()")


def plan(tree, facts):
    """The scans chosen, the conjuncts pushed, the pin, the total cost.

    `tree` is the resolved tree (stage 2's record with stage 3's pushdown
    available); `facts` is the world's `PLAN_FACTS`-shaped pin the plan must
    agree with. The choice is `cost_of`'s comparison, never a lookup of the
    pin."""

    raise NotImplementedError("stage 5: implement plan()")


def explain(plan_record):
    """The plan, one line: `events: index[ts] (ts<=60) | users: table`."""

    raise NotImplementedError("stage 5: implement explain()")
