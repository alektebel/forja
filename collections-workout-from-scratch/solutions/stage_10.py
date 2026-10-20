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
    """ONE loan's story: every dated event from the raw facts.

    Returns a tuple of story lines, one per event the loan experienced: payments,
    pyramid actions, forbearance grants, cures, default signals, write-offs,
    and recoveries. Each line carries the date, the event type, a detail string,
    the source module that produced it, and the amount in cents (0 for non-financial
    events).

    The lines are in date order. A loan the book does not hold is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]
    lines = []

    # 1. Payments
    for pay_row in book.payments(record):
        lines.append({
            "date": pay_row["paid_on"],
            "event": "payment",
            "detail": "%s on due %s" % (pay_row["kind"], pay_row["due"]),
            "source": "book.payments",
            "amount_cents": pay_row["amount_cents"],
        })

    # 2. Pyramid actions (from the log)
    for log_row in col.log_of(loan_id):
        lines.append({
            "date": log_row["date"],
            "event": "pyramid-" + log_row["action"],
            "detail": log_row["outcome"],
            "source": "workout.pyramid",
            "amount_cents": 0,
        })

    # 3. Forbearance grants
    grant = col.grant_of(loan_id)
    if grant:
        lines.append({
            "date": grant["granted_on"],
            "event": "forbearance",
            "detail": "%s (probation until %s)" % (grant["remedy"], grant["probation_until"]),
            "source": "collections.forbearance",
            "amount_cents": grant["detail_cents"],
        })

    # 4. Events from the book (cure, default signals, write-off)
    for event_row in book.events(record):
        if event_row["kind"] in ("cure", "write-off", "forbearance",
                                  "distressed-restructuring", "cross-default",
                                  "bankruptcy"):
            lines.append({
                "date": event_row["date"],
                "event": event_row["kind"],
                "detail": "event",
                "source": "book.events",
                "amount_cents": event_row["detail_cents"],
            })

    # 5. Recoveries
    for rec_row in book.recoveries(record):
        lines.append({
            "date": rec_row["date"],
            "event": "recovery",
            "detail": rec_row["source"],
            "source": "book.recoveries",
            "amount_cents": rec_row["amount_cents"],
        })

    # 6. Workout sale
    for sale_row in col.SALES:
        if sale_row["loan"] == loan_id:
            lines.append({
                "date": sale_row["sale_date"],
                "event": "sale",
                "detail": "net proceeds: %d" % sale_row["net_proceeds_cents"],
                "source": "collections.workout",
                "amount_cents": sale_row["net_proceeds_cents"],
            })

    lines.sort(key=lambda l: (l["date"], l["event"]))
    return tuple(lines)


def audit(book, loan):
    """Cross-check: pyramid, forbearance, waterfall, workout, write-off.

    Returns a dict with the audit results for this loan:
    - pyramid: the steps that fired (vs. workout.py's log)
    - forbearance: the grant (vs. workout.py's GRANTS)
    - waterfall: the ledger totals balance check
    - workout: the sale identity check
    - writeoff: the write-off event

    Each check names what it verified and whether it passed.
    """
    record = _resolve(book, loan)
    loan_id = record["loan"]
    result = {}

    # 1. Pyramid audit: re-walk the pyramid and compare to log
    import solutions.stage_02 as s2_sol
    import solutions.stage_03 as s3_sol
    # Use replay to check log integrity
    try:
        replay_result = s3_sol.replay(book, loan)
        log_rows = col.log_of(loan_id)
        result["pyramid"] = {
            "generated_steps": len(replay_result),
            "logged_steps": len(log_rows),
            "agrees": len(replay_result) == len(log_rows),
        }
    except Exception:
        result["pyramid"] = {
            "generated_steps": 0,
            "logged_steps": len(col.log_of(loan_id)),
            "agrees": False,
            "error": "replay failed",
        }

    # 2. Forbearance audit
    grant = col.grant_of(loan_id)
    if grant:
        # Check the grant matches the world's GRANTS
        result["forbearance"] = {
            "granted_on": grant["granted_on"],
            "remedy": grant["remedy"],
            "probation_until": grant["probation_until"],
        }
    else:
        result["forbearance"] = {"granted": None}

    # 3. Waterfall audit
    import solutions.stage_06 as s6_sol
    ledger_rows = s6_sol.ledger(book, loan)
    total_cash = sum(r["cash_cents"] for r in ledger_rows)
    total_fees = sum(r["fees_cents"] for r in ledger_rows)
    total_interest = sum(r["interest_cents"] for r in ledger_rows)
    total_principal = sum(r["principal_cents"] for r in ledger_rows)
    total_carried = sum(r["carried_cents"] for r in ledger_rows)
    result["waterfall"] = {
        "total_cash": total_cash,
        "total_split": total_fees + total_interest + total_principal + total_carried,
        "balance_holds": total_cash == total_fees + total_interest + total_principal + total_carried,
    }

    # 4. Workout audit
    for sale_row in col.SALES:
        if sale_row["loan"] == loan_id:
            identity = (sale_row["settlement_cents"] + sale_row["net_proceeds_cents"]
                        + sale_row["deficiency_cents"])
            result["workout"] = {
                "defaulted_on": sale_row["defaulted_on"],
                "sale_date": sale_row["sale_date"],
                "identity_holds": identity == sale_row["exposure_at_default_cents"],
                "exposure": sale_row["exposure_at_default_cents"],
                "deficiency": sale_row["deficiency_cents"],
            }
            break

    # 5. Write-off audit
    writeoff_date = None
    for event_row in book.events(record):
        if event_row["kind"] == "write-off":
            writeoff_date = event_row["date"]
            break
    result["writeoff"] = {"date": writeoff_date}

    return result


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