"""The priority Forja track — CodeCrafters-shaped entry path.

These five courses are the first product surface: same loop as CodeCrafters
(pick a challenge → read one stage → run one test → green → next), without
diluting the house philosophy (mutations, design decisions, local ownership).

Order is the Anyformat interview prep set (LLMOps / agent orchestration):

  1. aws-from-scratch            — cloud mechanisms (A1)
  2. infrastructure-from-scratch — queues, cache, rate limits, capacity (A5)
  3. llm-from-scratch            — tokenizer, attention, sampling, KV cache (A2)
  4. evals-from-scratch          — metrics, judges, significance, the gate (C1)
  5. agents-from-scratch         — tool loop, retries, sandbox, budgets (C2)

`deploy-and-debug` (A7) stays in the full path for ops depth; it is not on this
track so the five slots stay interview-shaped. `system-design/` (legacy prose)
is superseded by infrastructure-from-scratch.
"""

from . import manifests
from . import path as pathmod

# (slug, path id, short label, catalog title, learn-about blurb, logo key)
TRACK = (
    (
        "aws-from-scratch", "A1", "AWS From Scratch",
        "Build your own AWS",
        "Learn about IAM, S3, leased queues, DynamoDB and more",
        "aws",
    ),
    (
        "infrastructure-from-scratch", "A5", "Infrastructure",
        "Build your own Infrastructure",
        "Learn about caching, rate limits, queues, capacity and more",
        "infra",
    ),
    (
        "llm-from-scratch", "A2", "LLM From Scratch",
        "Build your own LLM",
        "Learn about tokenization, attention, sampling, KV cache and more",
        "llm",
    ),
    (
        "evals-from-scratch", "C1", "Evals From Scratch",
        "Build your own Evals",
        "Learn about metrics, judges, significance, the gate and more",
        "evals",
    ),
    (
        "agent-verification-from-scratch", "C3", "Agent Verification",
        "Verify agents with formal logic",
        "Learn about LTL, monitors, enforcement gates, spec mining and more",
        "verify",
    ),
    (
        "agents-from-scratch", "C2", "Agents From Scratch",
        "Build your own Agents",
        "Learn about tool loops, retries, sandboxes, budgets and more",
        "agents",
    ),
)

SLUGS = tuple(row[0] for row in TRACK)
BY_SLUG = {slug: (rid, label) for slug, rid, label, *_ in TRACK}


def entries():
    """Resolved track rows: registry entry + loaded course (or None)."""
    out = []
    for slug, rid, label, headline, blurb, logo in TRACK:
        _letter, _phase, entry = pathmod.find(rid)
        course = manifests.load(slug)
        out.append({
            "slug": slug,
            "id": rid,
            "label": label,
            "headline": headline,
            "blurb": blurb,
            "logo": logo,
            "entry": entry,
            "course": course,
            "why": (entry or {}).get("why", ""),
            "description": (course or {}).get("description") or blurb,
            "stages": len(course["stages"]) if course else 0,
            "ready": course is not None,
        })
    return out


def is_showcase(slug: str) -> bool:
    return slug in BY_SLUG


def next_on_track(profile) -> dict:
    """First showcase course that is not fully passed, with its next stage id."""
    for row in entries():
        if not row["ready"]:
            continue
        course = row["course"]
        cstate = profile.get("courses", {}).get(row["slug"], {})
        stages = cstate.get("stages", {})
        ids = sorted(course["stages"])
        for sid in ids:
            status = stages.get(str(sid), {}).get("last_status", "TODO")
            if status != "PASS":
                meta = course["stages"][sid]
                return {
                    "slug": row["slug"],
                    "id": row["id"],
                    "label": row["label"],
                    "headline": row["headline"],
                    "title": row["headline"],
                    "course": row["slug"],
                    "logo": row["logo"],
                    "showcase": True,
                    "stage": sid,
                    "file": meta.get("file", ""),
                    "stage_title": meta.get("title", ""),
                    "action": meta.get("action", ""),
                    "why": meta.get("why", ""),
                    "predict": meta.get("predict", ""),
                    "command": f"forja test {row['slug']} --stage {sid}",
                }
    return None
