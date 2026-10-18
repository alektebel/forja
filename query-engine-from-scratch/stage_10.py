"""Query Engine From Scratch — stage 10: The proof: a hundred queries, and the
audit.

The nine stages built the engine; this one proves it. `run_all` walks the
world's hundred queries through the whole stack — parse, resolve, plan,
execute — on a fresh world per query, so each query's page count is its own
receipt. `prove` adds the two halves a run cannot see: the plan facts held
as a set, and one crash fixture re-run so a commit the crash lost is
`lost_commit` in the proof's own vocabulary. `audit` re-reads the proof
against the world — not against the proof — and names the ids that failed.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — Why does `run_all` build a fresh world per query?
Because the pages receipt is per query: a buffer shared across queries
accumulates everyone's reads, and a count that names page 4 twice because
two queries read it is not either query's receipt. A fresh pager and disk
per query makes `pages` the receipt the contract names, and the cost —
loading the world a hundred times — is the honesty price.

DESIGN DECISION — Why is the stack's answer the evidence and the reference
the judge?
Because a proof that compares the reference with itself proves nothing: the
rows the executor computed are the only thing under test. `run_all` answers
the stack's rows even when the reference lies — the check plants a lying
reference and holds the answer against the executor's own arithmetic — and
the verdict classifies, it never overrides.

DESIGN DECISION — Why does the audit re-compare rather than trust the
proof's verdict?
Because a proof that says pass while its own rows disagree is the failure
mode the audit exists for. `rows_agree` and `plans_agree` are the audit's
own comparison against QUERIES; `reasons` names the failing ids in query
order; and the verdict is the strictest class the evidence supports —
`lost_commit` over `wrong_rows` over `wrong_plan` over `pass`.

DESIGN DECISION — Why is one crash fixture inside the proof?
Because a hundred rows prove the reads and none of the promises: the commit
stage's rule is about durability, and a proof that never crashes the disk
proves the arithmetic and not the engine. The clean fixture re-run through
stage 9's own door — with every committed transaction required in the
recovery's committed list — is the smallest run that makes `lost_commit` a
verdict the proof can answer rather than a word.
"""

import disk as dk
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
