"""Query Engine From Scratch — stage 10: The proof: a hundred queries, and
the audit.

Nine stages built the machinery; the proof is the course's answer to the
only question that matters: *does the whole stack return the world's rows,
every time, with the plans the costs chose, and a commit that survives the
power cut?* `run_all` runs the hundred through everything — parse, resolve,
plan, execute, buffer — and answers PROOF_KEYS: the rows per query, the
plans per query, the pages read, and the verdict. `prove` is stage 10's own
run: run_all plus the plan facts beside it (law 14: the index is earned,
and the proof says so) plus one crash fixture re-run for the durability
half — because rows and plans prove the engine, and the crash proves the
promise. `audit` re-reads the proof against the world: `wrong_rows` when any
query's rows differ from the reference's, `wrong_plan` when any plan
disagrees with its `uses_index`, `lost_commit` when a committed transaction
did not survive the crash, `pass` when all three hold — the reasons naming
the query ids that failed, because an audit that says *wrong* without
saying where is a puzzle, not a diagnosis.

DESIGN DECISION — Why does `run_all` answer the *verdict* rather than just
the records?
Because a stack that returns a hundred correct-looking records with one
wrong row is not a stack that works — and the consumer's question is the
verdict, not the dump. The records are the evidence; the verdict is the
answer. An audit that only ran on demand would let a wrong answer travel.

DESIGN DECISION — Why does `audit` take the *proof* rather than re-running
the stack itself?
Because the audit's job is to judge what ran, not to run it again: a proof
is a record of a run, and re-running it would make the audit the stack's
twin — able to agree with itself rather than with the reference. The audit
holds the proof against the world's own pins (rows, `uses_index`, the
fixture's committed split), which is the one direction of grading that
matters at the end of a course.

DESIGN DECISION — Why is `lost_commit` one of the closed four?
Because it is the one failure the other three cannot see: rows exact, plans
right, and the commit still lost — a durability bug in a stack that
*answers* correctly is the sneakiest wrong a database can be. The four
verdicts name every way a stack can be exactly wrong; a fifth would be a
prose category, and the audit does not grade prose.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

PROOF_KEYS = ("rows", "plans", "pages", "verdict")
AUDIT_KEYS = ("verdict", "reasons", "rows_agree", "plans_agree")
VERDICTS = ("pass", "wrong_rows", "wrong_plan", "lost_commit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def run_all(pager):
    """The hundred through the whole stack, one proof.

    Answers PROOF_KEYS — the rows per query, the plans per query, the pages
    read, and the verdict the stack's own answers earn."""

    raise NotImplementedError("stage 10: implement run_all()")


def prove(pager):
    """run_all plus the plan facts and one crash fixture re-run.

    Answers PROOF_KEYS with the crash half beside the engine half: the rows
    (law 13), the plans (law 14), the pages, and the verdict — where a
    committed transaction that did not survive the crash is `lost_commit`."""

    raise NotImplementedError("stage 10: implement prove()")


def audit(proof):
    """The proof re-read against the world: the verdict and its reasons.

    `wrong_rows` names the query ids whose rows differ from the
    reference's; `wrong_plan` names the ids whose plans disagree with their
    `uses_index`; `lost_commit` names the transactions that did not survive
    the crash; `pass` when all three hold."""

    raise NotImplementedError("stage 10: implement audit()")
