"""The stage 10 solution: the whole stack, one proof, and the world's audit."""

import disk as dk
import pages as pg
import tables as tb
import ops

PROOF_KEYS = ("rows", "plans", "pages", "verdict")
AUDIT_KEYS = ("verdict", "reasons", "rows_agree", "plans_agree")
VERDICTS = ("pass", "wrong_rows", "wrong_plan", "lost_commit")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


def _crash_half():
    """One crash fixture re-run: the durability half of the proof.

    The fixture is `uncommitted-loss` — the one that exercises both
    directions of law 15: the committed row survives, the uncommitted one
    does not."""
    import stage_09
    fixture = None
    for entry in tb.CRASH_SCHEDULE:
        if entry["name"] == "uncommitted-loss":
            fixture = entry
            break
    run = stage_09.run_crash(fixture)
    return {"committed": run["committed"],
            "rolled_back": run["rolled_back"],
            "rows": run["rows"]}


def run_all(pager, crash=None):
    """The hundred through the whole stack, one proof."""
    import stage_01
    import stage_02
    import stage_05
    import stage_06
    rows = {}
    plans = {}
    pages_read = 0
    for q in tb.QUERIES:
        tree = stage_02.resolve(stage_01.parse(q["sql"]), tb.CATALOG)
        plan = stage_05.plan(tree, tb.PLAN_FACTS)
        answer = stage_06.execute(plan, pager)
        rows[q["id"]] = answer["rows"]
        plans[q["id"]] = plan
        pages_read += answer["pages"]
    proof = {"rows": rows, "plans": plans, "pages": pages_read,
             "verdict": None}
    if crash is not None:
        proof["crash"] = crash
    proof["verdict"] = audit(proof)["verdict"]
    return proof


def prove(pager):
    """run_all plus the plan facts and one crash fixture re-run."""
    crash = _crash_half()
    proof = run_all(pager, crash=crash)
    return proof


def audit(proof):
    """The proof re-read against the world."""
    rows_agree = True
    plans_agree = True
    wrong_rows = []
    wrong_plans = []
    for q in tb.QUERIES:
        if proof["rows"].get(q["id"]) != q["rows"]:
            wrong_rows.append(q["id"])
            rows_agree = False
        plan = proof["plans"].get(q["id"])
        if plan is not None and plan["uses_index"] != q["uses_index"]:
            wrong_plans.append(q["id"])
            plans_agree = False
    lost = []
    crash = proof.get("crash")
    if crash is not None:
        # law 15: the committed transactions survive, the rolled-back do not
        rolled = set(crash["rolled_back"])
        for xid, expect in _fixture_split():
            survived = _xid_rows_survive(crash["rows"], xid)
            if expect and not survived:
                lost.append(xid)
            if not expect and survived and xid in rolled:
                lost.append(xid)
    if wrong_rows:
        verdict = "wrong_rows"
    elif wrong_plans:
        verdict = "wrong_plan"
    elif lost:
        verdict = "lost_commit"
    else:
        verdict = "pass"
    reasons = []
    if wrong_rows:
        reasons.append("rows: %s" % (wrong_rows,))
    if wrong_plans:
        reasons.append("plans: %s" % (wrong_plans,))
    if lost:
        reasons.append("lost: %s" % (lost,))
    return {"verdict": verdict, "reasons": tuple(reasons),
            "rows_agree": rows_agree, "plans_agree": plans_agree}


def _xid_rows_survive(rows, xid):
    """Whether transaction xid's inserted row survived the recovery."""
    # the fixtures insert one row per transaction, its id = 40 + xid for
    # orders and 79 + xid for items — the arithmetic the workload pins
    for table_rows in rows.values():
        for row in table_rows:
            if row[0] in (41 + xid, 79 + xid):
                return True
    return False


def _fixture_split():
    """The uncommitted-loss fixture's committed/uncommitted split."""
    for entry in tb.CRASH_SCHEDULE:
        if entry["name"] == "uncommitted-loss":
            return tuple((int(tx["name"][1:]), tx["commits"])
                         for tx in entry["transactions"])
    return ()
