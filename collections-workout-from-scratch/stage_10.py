"""Collections Workout From Scratch — stage 10: The per-loan story (capstone).

Every loan in the book is a story: the borrower's payments, the bank's actions
through the pyramid, the forbearance grants, the waterfall splits, the workout
sale, and the final recovery. This stage tells that story from the raw facts
alone, and audits every piece against the world's own records.

The story is one dated line per event: a payment, a pyramid step, a forbearance
grant, a cure, a default signal, a write-off, or a recovery. Each line names
the rule that produced it.

The audit cross-checks every piece: the pyramid the loan was on, the forbearance
the bank allowed against the rules, the waterfall's totals, the workout's
footing, and the write-off's ledger effect.

    CapstoneError          the refusal this stage raises
    STORY_KEYS             the five fields of one story line, in order
    story(book, loan)      -> ONE loan's story from first action to last
    audit(book, loan)      -> cross-check: pyramid, forbearance, waterfall, workout

DESIGN DECISION — why does the story read the world's own records?
Because the capstone is about telling the complete story, and the world's
records are the truth. The audit, however, recomputes from the raw facts
and checks agreement.

DESIGN DECISION — why is the audit a separate function from the story?
Because the story is the narrative and the audit is the verification. A
learner reads the story to understand the loan's life, and the audit to
understand whether the world's records are consistent.

TODO: implement `CapstoneError`, `story` and `audit` in this file:
the per-loan narrative and the cross-check audit.

    A loan the book does not hold is refused by name.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules
import stage_01 as s1
import stage_02 as s2
import stage_04 as s4
import stage_06 as s6
import stage_07 as s7


def _import_s6_ledger():
    """Import the ledger function from the solution, not the template."""
    import importlib
    import sys
    sol = __import__("solutions.stage_06", fromlist=["ledger"])
    return sol.ledger


def _import_s2_due_actions():
    """Import the due_actions function from the solution."""
    import solutions.stage_02 as sol_s2
    return sol_s2.due_actions

STORY_KEYS = ("date", "event", "detail", "source", "amount_cents")


class CapstoneError(ValueError):
    """The refusal this stage raises: something the capstone cannot tell.

    It names the offender — the loan the book does not hold — because a story
    the capstone cannot assemble must say what it was asked for rather than
    answer a narrative nobody can defend.
    """


def story(book, loan):
    raise NotImplementedError("stage 77: implement story()")


















































































def audit(book, loan):
    raise NotImplementedError("stage 161: implement audit()")





















































































def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if record.get("loan") == name:
            return record
    raise CapstoneError("the book holds no loan %r" % (name,))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 10 — the per-loan story")
    for loan_name in ("L-01", "L-07", "L-10"):
        lines = story(book, loan_name)
        print("  %-5s -> %d line(s)" % (loan_name, len(lines)))
        for line in lines:
            print("        %-12s %-25s %s %s"
                  % (line["date"], line["event"], line["detail"], line["amount_cents"]))
    print()
    print("  audit:")
    for loan_name in ("L-07", "L-10"):
        audit_result = audit(book, loan_name)
        print("    %-5s pyramid=%s waterfall_balance=%s workout_identity=%s"
              % (loan_name,
                 audit_result["pyramid"]["agrees"],
                 audit_result["waterfall"]["balance_holds"],
                 audit_result["workout"]["identity_holds"] if "workout" in audit_result else "N/A"))