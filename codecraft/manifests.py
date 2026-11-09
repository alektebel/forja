"""Find courses and load their metadata into one shape.

A *course* is any directory under the repo root that carries either:

  * `course.py`   — an authored course (see codecraft/api.py), or
  * `check.py`    — one of the existing projects (built-in curriculum).

For `check.py` courses we read `lessons.json` when present, otherwise the
ordered `CHECKS` list from source and learning metadata from `curriculum.py`.
"""

import json
import os
import re

from . import contract, curriculum

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SKIP = {".git", "codecraft", "solutions", "__pycache__"}
_CHECKS_ENTRY = re.compile(r"\(\s*\"([^\"]+\.py)\"\s*,\s*\"([^\"]+)\"")


def _parse_check_stages(path: str):
    """Recover [(file, title), ...] from a check.py's static CHECKS list."""
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:
        return []
    block = source.split("CHECKS", 1)
    if len(block) < 2:
        return []
    return [(m.group(1), m.group(2)) for m in _CHECKS_ENTRY.finditer(block[1])]


def load(name: str):
    """Load a course by directory name or path. Returns dict or None."""
    candidate = os.path.join(REPO_ROOT, name)
    if not os.path.isdir(candidate):
        candidate = os.path.abspath(name)
    if not os.path.isdir(candidate):
        return None
    base = os.path.basename(candidate.rstrip("/"))

    if os.path.exists(os.path.join(candidate, "course.py")):
        module = contract.load_course_module(candidate)
        stages = {}
        for st in getattr(module, "STAGES", []):
            stages[st.id] = st.meta()
        return {
            "name": base, "dir": candidate, "mode": contract.MODE_COURSE,
            "title": getattr(module, "TITLE", base.replace("-", " ").title()),
            "description": getattr(module, "DESCRIPTION", ""),
            "level": getattr(module, "LEVEL", "custom"),
            "order": getattr(module, "ORDER", 99),
            "stages": stages,
        }

    if os.path.exists(os.path.join(candidate, "check.py")):
        info = curriculum.COURSE_INFO.get(base, {})
        metas = curriculum.CURRICULUM.get(base, {})
        stages = {}
        lessons_path = os.path.join(candidate, "lessons.json")
        lessons = None
        if os.path.exists(lessons_path):
            with open(lessons_path, encoding="utf-8") as fh:
                lessons = json.load(fh)
            if [row["id"] for row in lessons] != list(range(1, len(lessons) + 1)):
                raise ValueError(f"nonsequential lesson IDs in {lessons_path}")
        rows = ([(row["file"], row["title"]) for row in lessons]
                if lessons is not None else _parse_check_stages(
                    os.path.join(candidate, "check.py")))
        for i, (file, title) in enumerate(rows, start=1):
            meta = dict(metas.get(i, {}))
            if lessons is not None:
                meta = dict(lessons[i - 1])
            stages[i] = {
                "file": file, "title": title,
                "tags": list(meta.get("tags", [])),
                "action": meta.get("action") or meta.get("task", ""),
                "why": meta.get("why") or meta.get("context", ""),
                "predict": meta.get("predict", ""),
                "context": meta.get("context", ""),
                "task": meta.get("task", ""),
                "example": meta.get("example", ""),
                "target": meta.get("target", ""),
                "optional": meta.get("optional", False),
                "hints": list(meta.get("hints", [])),
                "requirements": list(meta.get("requirements", [])),
                "out_of_scope": list(meta.get("out_of_scope", [])),
                "learning": meta.get("learning"), "solution": "",
            }
        return {
            "name": base, "dir": candidate, "mode": contract.MODE_CHECK,
            "title": info.get("title", base.replace("-", " ").title()),
            "description": info.get("blurb", ""),
            "level": info.get("level", "custom"),
            "order": info.get("order", 99),
            "stages": stages,
        }
    return None


def discover():
    """All courses under the repo root, in recommended order."""
    found = []
    for entry in sorted(os.listdir(REPO_ROOT)):
        if entry.startswith(".") or entry in _SKIP:
            continue
        if not os.path.isdir(os.path.join(REPO_ROOT, entry)):
            continue
        try:
            course = load(entry)
        except Exception as exc:                              # noqa: BLE001
            print(f"  (skipping {entry}: {type(exc).__name__}: {exc})")
            course = None
        if course:
            found.append(course)
    found.sort(key=lambda c: (c["order"], c["name"]))
    return found


def stage_meta(course: dict) -> dict:
    """{id: meta} suitable for store.record_attempt."""
    return course["stages"]
