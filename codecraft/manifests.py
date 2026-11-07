"""Find courses and load their metadata into one shape.

A *course* is any directory under the repo root that carries either:

  * `course.py`   — an authored course (see codecraft/api.py), or
  * `check.py`    — one of the existing projects (built-in curriculum).

For `check.py` courses we read the ordered `CHECKS` list out of the source so
`codecraft next` works without running anything, and fill learning metadata
from `curriculum.py`.
"""

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
        for i, (file, title) in enumerate(_parse_check_stages(
                os.path.join(candidate, "check.py")), start=1):
            meta = dict(metas.get(i, {}))
            stages[i] = {
                "file": file, "title": title,
                "tags": list(meta.get("tags", [])),
                "action": meta.get("action", ""),
                "why": meta.get("why", ""),
                "predict": meta.get("predict", ""),
                "hints": [], "solution": "",
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
