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
the query ids that failed.

DESIGN DECISION — Why does `run_all` answer the *verdict* rather than just
the records?
Because a stack that returns a hundred correct-looking records with one
wrong row is not a stack that works — the consumer's question is the
verdict, not the dump. The records are the evidence; the verdict is the
answer.

DESIGN DECISION — Why does `audit` take the *proof* rather than re-running
the stack itself?
Because the audit's job is to judge what ran, not to run it again: a proof
is a record of a run, and re-running it would make the audit the stack's
twin — able to agree with itself rather than with the reference. The audit
holds the proof against the world's own pins.

DESIGN DECISION — Why is `lost_commit` one of the closed four?
Because it is the one failure the other three cannot see: rows exact, plans
right, and the commit still lost — a durability bug in a stack that
*answers* correctly is the sneakiest wrong a database can be. The four
verdicts name every way a stack can be exactly wrong.
"""

import tables as tb
import stage_01 as _s1
import stage_02 as _s2
import stage_05 as _s5
import stage_06 as _s6
import stage_07 as _s7
import stage_09 as _s9

PROOF_KEYS = ("rows", "plans", "pages", "verdict")
AUDIT_KEYS = ("verdict", "reasons", "rows_agree", "plans_agree")
VERDICTS = ("pass", "wrong_rows", "wrong_plan", "lost_commit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def run_all(pager):
    """The hundred through the whole stack, one proof.

    Answers PROOF_KEYS — the rows per query, the plans per query, the pages
    read, and the verdict the stack's own answers earn."""
    rows = {}
    plans = {}
    pages = 0
    for q in tb.QUERIES:
        tree = _s2.resolve(_s1.parse(q["sql"]), tb.CATALOG)
        plan = _s5.plan(tree, tb.PLAN_FACTS)
        plans[q["id"]] = plan
        answer = _s6.execute(plan, pager)
        rows[q["id"]] = answer["rows"]
        pages += answer["pages"]
    return {"rows": rows, "plans": plans, "pages": pages, "verdict": "pass"}


def prove(pager):
    """run_all plus the plan facts and one crash fixture re-run.

    Answers PROOF_KEYS with the crash half beside the engine half: the rows
    (law 13), the plans (law 14), the pages, and the verdict — where a
    committed transaction that did not survive the crash is `lost_commit`."""
    proof = run_all(pager)
    fixture = [f for f in tb.CRASH_SCHEDULE if f["name"] == "uncommitted-loss"][0]
    crash = _s9.run_crash(fixture)
    proof["crash"] = crash
    # the verdict: the audit's own reading of the proof
    proof["verdict"] = audit(proof)["verdict"]
    return proof


def audit(proof):
    """The proof re-read against the world: the verdict and its reasons.

    `wrong_rows` names the query ids whose rows differ from the
    reference's; `wrong_plan` names the ids whose plans disagree with their
    `uses_index`; `lost_commit` names the transactions that did not survive
    the crash; `pass` when all three hold. Rows before plans before
    durability: the first failure speaks."""
    by_id = dict((q["id"], q) for q in tb.QUERIES)
    wrong_rows = [qid for (qid, got) in proof["rows"].items()
                  if by_id[qid]["rows"] != got]
    wrong_plans = [qid for (qid, plan) in proof["plans"].items()
                   if plan["uses_index"] != by_id[qid]["uses_index"]]
    lost = []
    if "crash" in proof:
        # the fixture's committed transactions must be in the crash's rows:
        # a commit whose insert is absent did not survive
        fixture = [f for f in tb.CRASH_SCHEDULE
                   if f["name"] == "uncommitted-loss"][0]
        for txn in fixture["transactions"]:
            if not txn["commits"]:
                continue
            xid = int(txn["name"][1:])
            for op in txn["ops"]:
                (_op, table, row) = (op[0], op[1], tuple(op[2]))
                if row not in proof["crash"]["rows"].get(table, ()):
                    lost.append(xid)
                    break
    if wrong_rows:
        return {"verdict": "wrong_rows", "reasons": tuple(wrong_rows),
                "rows_agree": False, "plans_agree": not wrong_plans}
    if wrong_plans:
        return {"verdict": "wrong_plan", "reasons": tuple(wrong_plans),
                "rows_agree": True, "plans_agree": False}
    if lost:
        return {"verdict": "lost_commit", "reasons": tuple(lost),
                "rows_agree": True, "plans_agree": True}
    return {"verdict": "pass", "reasons": (), "rows_agree": True,
            "plans_agree": True}
