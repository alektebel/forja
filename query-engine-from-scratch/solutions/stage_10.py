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

import stage_01
import stage_02
import stage_05
import stage_06
import stage_09

PROOF_KEYS = ("rows", "plans", "pages", "verdict")
AUDIT_KEYS = ("verdict", "reasons", "rows_agree", "plans_agree")
VERDICTS = ("pass", "wrong_rows", "wrong_plan", "lost_commit")


def _one(query):
    """One query through the whole stack, on a fresh world.

    Each query gets its own pager and its own disk: the pages read are
    that query's receipt, not an accumulation of everyone's."""
    pager = pg.Pager(dk.Disk())
    tb.load_world(pager)
    tree = stage_02.resolve(stage_01.parse(query["sql"]), tb.CATALOG)
    plan = stage_05.plan(tree, tb.PLAN_FACTS)
    out = stage_06.execute(pager, tree, plan)
    return out["rows"], plan, out["pages"]


def _rows_agree(proof):
    """Every query's rows against the reference's, failing ids in order."""
    return [q["id"] for q in tb.QUERIES
            if q["id"] in proof["rows"] and proof["rows"][q["id"]]
            != q["rows"]]


def _plans_agree(proof):
    """Every query's plan against the reference's uses_index."""
    pinned = dict(tb.PLAN_FACTS)
    return [q["id"] for q in tb.QUERIES
            if q["id"] in proof["plans"]
            and bool(proof["plans"][q["id"]]["uses_index"])
            != bool(pinned.get(q["id"], False))]


def run_all(pager=None):
    """The hundred queries through the whole stack, and the verdict.

    `pager` is accepted and unused: the stack builds a fresh world per
    query, so each query's pages are its own receipt."""
    rows, plans, pages_read = {}, {}, {}
    for query in tb.QUERIES:
        out_rows, plan, out_pages = _one(query)
        rows[query["id"]] = out_rows
        plans[query["id"]] = plan
        pages_read[query["id"]] = out_pages
    if _rows_agree({"rows": rows}):
        verdict = "wrong_rows"
    elif _plans_agree({"plans": plans}):
        verdict = "wrong_plan"
    else:
        verdict = "pass"
    return {"rows": rows, "plans": plans, "pages": pages_read,
            "verdict": verdict}


def prove(pager=None):
    """run_all, plus the plan facts, plus one crash re-run."""
    proof = run_all(pager)
    if proof["verdict"] == "pass":
        # the plan facts as a set: the world's indexed ids are exactly
        # the plans' indexed ids
        pinned = {qid for (qid, uses) in tb.PLAN_FACTS if uses}
        planned = {qid for qid, plan in proof["plans"].items()
                   if plan["uses_index"]}
        if pinned != planned:
            proof["verdict"] = "wrong_plan"
    if proof["verdict"] == "pass":
        # one crash fixture re-run: the durability half (law 15)
        fixture = [f for f in tb.CRASH_SCHEDULE if not f["tear"]
                   and any(t["commits"] for t in f["transactions"])][0]
        out = stage_09.run_crash(fixture)
        committed = set(out["committed"])
        for tx in fixture["transactions"]:
            if tx["commits"] and tx["name"] not in committed:
                proof["verdict"] = "lost_commit"
                break
    return proof


def audit(proof):
    """The proof re-read against the world, classified."""
    rows_bad = _rows_agree(proof)
    plans_bad = _plans_agree(proof)
    reasons = tuple(rows_bad + plans_bad)
    rows_agree = not rows_bad
    plans_agree = not plans_bad
    if proof.get("verdict") == "lost_commit":
        verdict = "lost_commit"
    elif rows_bad:
        verdict = "wrong_rows"
    elif plans_bad:
        verdict = "wrong_plan"
    else:
        verdict = "pass"
    assert verdict in VERDICTS
    return {"verdict": verdict, "reasons": reasons,
            "rows_agree": rows_agree, "plans_agree": plans_agree}
