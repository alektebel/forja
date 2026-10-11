"""Where your learning record lives, and the bookkeeping that maintains it.

Two files under `codecraft/`:

  history.jsonl   append-only, one JSON object per checker run (raw evidence)
  profile.json    the derived model of you: per-stage state, per-concept
                  mastery, recurring mistake categories, and preferences

Nothing here is precious if deleted — history is the source of truth and the
profile can be rebuilt from it — but keeping both makes `codecraft status`
instant instead of a full replay.
"""

import json
import os
import time

from . import patterns

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "history.jsonl")
PROFILE = os.path.join(HERE, "profile.json")

DEFAULT_CONFIG = {
    "style": "balanced",            # balanced | deep | fast
    "mentor": "auto",               # auto (every failure) | stuck | manual | off
    "model": "deepseek-v4-flash",   # any NAN model id
    "endpoint": "https://api.nan.builders/v1",
    "publish": "http://127.0.0.1:8766",   # where `cz publish` POSTs run events
}

CONCEPT_BOXES = 3   # Leitner-ish: box 0 fails soon, box 3 is retired
BOX_LABELS = {0: "shaky", 1: "learning", 2: "getting there", 3: "solid"}


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def load_profile() -> dict:
    if not os.path.exists(PROFILE):
        return {"config": dict(DEFAULT_CONFIG), "patterns": {}, "courses": {}}
    try:
        with open(PROFILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {"config": dict(DEFAULT_CONFIG), "patterns": {}, "courses": {}}
    data.setdefault("config", {})
    for k, v in DEFAULT_CONFIG.items():
        data["config"].setdefault(k, v)
    data.setdefault("patterns", {})
    data.setdefault("courses", {})
    return data


def save_profile(profile: dict) -> None:
    tmp = PROFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, sort_keys=True)
    os.replace(tmp, PROFILE)


def append_history(record: dict) -> None:
    with open(HISTORY, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def iter_history(limit: int = 0):
    if not os.path.exists(HISTORY):
        return []
    with open(HISTORY, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return rows[-limit:] if limit else rows


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------

def _course(profile: dict, name: str, title: str = "") -> dict:
    course = profile["courses"].setdefault(name, {})
    if title:
        course["title"] = title
    course.setdefault("runs", 0)
    course.setdefault("stages", {})
    course.setdefault("concepts", {})
    return course


def record_attempt(profile: dict, attempt: dict, stage_meta: dict) -> dict:
    """Fold one checker run into the profile. Returns the updated course entry."""
    ts = attempt["ts"]
    course = _course(profile, attempt["course"], attempt.get("title", ""))
    course["runs"] += 1
    course["last_run"] = ts
    course["total"] = attempt["total"]
    course["last_passed"] = attempt["passed"]
    course["last_failed"] = attempt["failed"]
    course["last_todo"] = attempt["todo"]
    course["next_step"] = attempt.get("next_step")

    for st in attempt["stages"]:
        key = str(st["id"])
        row = course["stages"].setdefault(key, {
            "attempts": 0, "fails": 0, "todos": 0, "passes": 0,
            "fail_streak": 0, "signatures": {}, "hint_level": 0,
        })
        prev = row.get("status")
        row["attempts"] += 1
        row["file"] = st["file"]
        row["title"] = st["title"]
        row["last_status"] = st["status"]
        row["last_detail"] = st.get("detail", "")
        row["last_ts"] = ts

        if st["status"] == "PASS":
            row["passes"] += 1
            if prev != "PASS":
                row["attempts_to_pass"] = row["attempts"]
                row["first_pass"] = row.get("first_pass") or ts
            row["fail_streak"] = 0
        else:
            row["fail_streak"] = row.get("fail_streak", 0) + 1
            if st["status"] == "TODO":
                row["todos"] += 1
            else:
                row["fails"] += 1
                sig = patterns.signature(st.get("detail", ""))
                if sig:
                    row["signatures"][sig] = row["signatures"].get(sig, 0) + 1
                category = patterns.classify(st.get("detail", ""))
                row["last_category"] = category
                _bump_pattern(profile, category, attempt["course"], ts,
                              patterns.condense(st.get("detail", ""), 140))
            # a stage that regressed is worth noting
            if prev == "PASS":
                row["regressed"] = True
        # concept bookkeeping uses the authored/built-in tags for this stage
        meta = stage_meta.get(st["id"], {})
        for tag in meta.get("tags", []):
            concept = course["concepts"].setdefault(tag, {
                "exposures": 0, "fails": 0, "passes": 0, "box": 0, "last": 0,
            })
            concept["exposures"] += 1
            concept["last"] = ts
            if st["status"] == "PASS":
                concept["passes"] += 1
                if not concept.get("ever_failed"):
                    concept["box"] = min(CONCEPT_BOXES, concept.get("box", 0) + 1)
            elif st["status"] != "TODO":
                concept["fails"] += 1
                concept["ever_failed"] = True
                concept["box"] = 0
    profile["courses"][attempt["course"]] = course
    return course


def _bump_pattern(profile: dict, category: str, course: str, ts: float,
                  example: str) -> None:
    row = profile["patterns"].setdefault(category, {
        "count": 0, "courses": [], "examples": [], "last": 0,
    })
    row["count"] += 1
    if course not in row["courses"]:
        row["courses"].append(course)
    row["last"] = ts
    if example and example not in row["examples"]:
        row["examples"] = (row["examples"] + [example])[-3:]


def set_hint_level(profile: dict, course: str, stage: int, level: int) -> None:
    row = _course(profile, course)["stages"].setdefault(str(stage), {})
    row["hint_level"] = max(row.get("hint_level", 0), level)


def hint_level(profile: dict, course: str, stage: int) -> int:
    return _course(profile, course)["stages"].get(str(stage), {}).get("hint_level", 0)


def now() -> float:
    return time.time()
