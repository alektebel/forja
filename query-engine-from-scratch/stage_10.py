"""stage_10.py — the proof: a hundred queries, and the audit.

The course's last stage composes everything and holds the answer against
the reference: parse, resolve, plan, execute, buffer — the hundred queries
run through the whole stack, each query's rows compared with the rows the
world pinned, each plan compared with the index the world pinned, and one
crash fixture re-run so the durability half (law 15) is inside the proof
too. The audit re-reads the proof against the world and classifies what
failed: the rows, the plans, or a commit the crash lost.

Import the world and every stage; answer only what the surface names.

Constants:

PROOF_KEYS  the record a run answers: ("rows", "plans", "pages", "verdict")
AUDIT_KEYS  the record the audit answers:
            ("verdict", "reasons", "rows_agree", "plans_agree")
VERDICTS    ("pass", "wrong_rows", "wrong_plan", "lost_commit") — the audit's
            whole vocabulary, in strictness order

Design decisions (each is a law the checks hold):

1. One pipeline, run a hundred times. `run_all` walks QUERIES in order:
   parse the sql, push the predicates, plan against the pushdown, execute
   through the buffer. Every query goes through the same door; no query is
   special-cased, and none is skipped.

2. The verdict is the proof's own word, strictest first. A query's rows
   that differ from the reference's is wrong_rows; a plan whose
   uses_index disagrees with the reference's is wrong_plan; a committed
   transaction the crash lost is lost_commit. The first failure in
   strictness order is the verdict — `pass` only when nothing failed.

3. `prove` is run_all plus the two halves run_all cannot see. The plan
   facts (§4.5) are checked as a set — every query the world pins as
   indexed is indexed in the plan, and no other. One crash fixture (the
   clean one) is re-run through stage 9's run_crash: every transaction
   that committed must be in the recovery's committed list, and the
   recovered rows must carry the committed work.

4. `audit` re-reads the proof against the world, not against the proof.
   rows_agree and plans_agree are the audit's own comparison of the
   proof's rows and plans with QUERIES' — a proof that says pass while
   the rows disagree is caught here. reasons names the query ids that
   failed, in query order; the verdict is the strictest class the
   evidence supports.

5. The audit is graded against the reference, not against anyone's prose.
   Its verdicts are exactly VERDICTS; anything else is refused.
"""

import disk as dk
import ops
import pages as pg
import tables as tb

PROOF_KEYS = None
AUDIT_KEYS = None
VERDICTS = None


def run_all(pager=None):
    """The hundred queries through the whole stack, and the verdict."""
    raise NotImplementedError("stage 10: implement run_all()")


def prove(pager=None):
    """run_all, plus the plan facts, plus one crash re-run."""
    raise NotImplementedError("stage 10: implement prove()")


def audit(proof):
    """The proof re-read against the world, classified."""
    raise NotImplementedError("stage 10: implement audit()")
