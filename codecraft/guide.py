"""CodeCrafters-shaped stage guides for Forja courses.

Renders (and optionally writes) one markdown page per stage in the form:

  mechanism excerpt → what to implement → how the tester runs → notes/predict

Sources of truth stay in course.py, curriculum.py, check.py, or lessons.json;
generated pages are a product surface, not a second syllabus.
"""

from __future__ import annotations

import os
import re

from . import showcase

STAGES_DIR = "stages"


def _slugify(title: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return text[:48] or "stage"


def render_stage(course: dict, stage_id: int) -> str:
    """One CC-style stage page as markdown."""
    meta = course["stages"][stage_id]
    if meta.get("task"):
        return _render_micro_stage(course, stage_id, meta)
    file = meta.get("file") or f"stage_{stage_id:02d}.py"
    title = meta.get("title") or file
    action = meta.get("action") or ""
    why = meta.get("why") or ""
    predict = meta.get("predict") or ""
    tags = meta.get("tags") or []
    hints = meta.get("hints") or []

    tag_line = ", ".join(tags) if tags else "—"
    lines = [
        f"# Stage {stage_id}: {title}",
        "",
        f"**Course:** {course['title']} (`{course['name']}`)",
        f"**File:** `{file}`",
        f"**Tags:** {tag_line}",
        "",
        "## The mechanism",
        "",
    ]
    if action:
        lines.append(action)
    else:
        lines.append(
            f"Implement what `{file}` asks for. The checker names the failure "
            "mode when you get it wrong.")
    if why:
        lines.extend(["", "## Why the requirement is what it is", "", why, ""])
    lines.extend(["", "## Tests", "",
                  "The tester runs your code like this:", "",
                  "```bash",
                  f"forja test {course['name']} --stage {stage_id}",
                  "# same as:",
                  f"python3 codecraft/cli.py run {course['name']} --stage {stage_id}",
                  "```", "",
                  "It imports **your** module (never `solutions/`) and asserts "
                  "the behaviour this stage defines. A red failure names the "
                  "likely cause — read that before rewriting.", ""])
    if predict:
        lines.extend(["## Predict before you look", "",
                      f"> {predict}", "",
                      "Commit to a number (or outcome) *before* the check "
                      "prints. That is where the learning consolidates.", ""])
    if hints:
        lines.extend(["## Notes", ""])
        for hint in hints:
            lines.append(f"- {hint}")
        lines.append("")
    lines.extend([
        "## Next",
        "",
        "When this stage is green:",
        "",
        "```bash",
        f"forja stage {course['name']} {stage_id + 1}",
        "```",
        "",
    ])
    return "\n".join(lines)


def _render_micro_stage(course: dict, stage_id: int, meta: dict) -> str:
    """Compact guide with one context, task, prediction, and check."""
    optional = " · optional" if meta.get("optional") else ""
    lines = [
        f"# Stage {stage_id}: {meta['title']}",
        "",
        f"**Edit:** `{meta['file']}` → `{meta.get('target', '')}`{optional}",
        "",
        "## Context",
        "",
        meta["context"],
        "",
        "## Your task",
        "",
        meta["task"],
        "",
    ]
    requirements = meta.get("requirements") or []
    if requirements:
        lines.extend(["## Requirements", ""])
        lines.extend(f"- {item}" for item in requirements)
        lines.append("")
    out_of_scope = meta.get("out_of_scope") or []
    if out_of_scope:
        lines.extend(["## Not in this stage", ""])
        lines.extend(f"- {item}" for item in out_of_scope)
        lines.append("")
    if meta.get("example"):
        lines.extend(["## Example edit", "", "```python", meta["example"], "```", ""])
    lines.extend([
        "## Predict",
        "",
        f"> {meta['predict']}",
        "",
        "## Check",
        "",
        "```bash",
        f"forja test {course['name']} --stage {stage_id}",
        "```",
        "",
    ])
    if stage_id < len(course["stages"]):
        lines.extend([f"Next: `forja stage {course['name']} {stage_id + 1}`", ""])
    else:
        lines.extend(["You finished the course.", ""])
    return "\n".join(lines)


def render_start(course: dict) -> str:
    """Stage-0 / onboarding page — the CodeCrafters 'first green' surface."""
    n = len(course["stages"])
    first = course["stages"][min(course["stages"])]
    if first.get("task"):
        lines = [
            f"# {course['title']}", "", course.get("description") or "", "",
            f"**{n} short stages.** Build one behavior at a time in your editor.", "",
            "## Check the setup", "", "```bash",
            f"forja smoke {course['name']}", "```", "",
            "## Your first stage", "", first["context"], "", first["task"], "",
        ]
        if first.get("example"):
            lines.extend(["```python", first["example"], "```", ""])
        lines.extend([
            "Predict: " + first["predict"], "", "```bash",
            f"forja guide {course['name']} 1",
            f"forja test {course['name']} --stage 1", "```", "",
        ])
        return "\n".join(lines)
    return "\n".join([
        f"# {course['title']}",
        "",
        course.get("description") or "",
        "",
        f"**{n} stages.** Code in your editor. Run tests locally. No toy IDE.",
        "",
        "## Stage 0 — smoke (under 30 seconds)",
        "",
        "Confirm the course is runnable before you write anything:",
        "",
        "```bash",
        f"forja smoke {course['name']}",
        "```",
        "",
        "You should see `smoke OK`. That is your first green — the same "
        "dopamine CodeCrafters buys with 'uncomment and push', without "
        "pretending uncommenting taught you IAM.",
        "",
        "## Stage 1 — first real work",
        "",
        f"**File:** `{first.get('file', '')}` — {first.get('title', '')}",
        "",
        first.get("action") or "Open the file and implement the first TODO.",
        "",
        "```bash",
        f"forja guide {course['name']} 1     # the full stage page",
        f"forja test {course['name']} --stage 1",
        "```",
        "",
        "## The loop",
        "",
        "1. Read the stage guide",
        "2. Edit the file in your IDE",
        "3. `forja test` (alias of `cz run`)",
        "4. Read the cause / mentor nudge",
        "5. Predict, then re-run",
        "",
        f"Stuck: `forja hint {course['name']}` · "
        f"`forja explain {course['name']}`",
        "",
    ])


def write_course_guides(course: dict, force: bool = False) -> list:
    """Write START.md + stages/NN-*.md under the course directory."""
    root = course["dir"]
    stages_dir = os.path.join(root, STAGES_DIR)
    os.makedirs(stages_dir, exist_ok=True)
    written = []

    start_path = os.path.join(root, "START.md")
    if force or not os.path.exists(start_path):
        with open(start_path, "w", encoding="utf-8") as fh:
            fh.write(render_start(course))
        written.append(start_path)

    for sid in sorted(course["stages"]):
        meta = course["stages"][sid]
        name = f"{sid:02d}-{_slugify(meta.get('title') or meta.get('file') or 'stage')}.md"
        path = os.path.join(stages_dir, name)
        if force or not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(render_stage(course, sid))
            written.append(path)
    return written


def write_showcase_guides(force: bool = False) -> dict:
    """Generate guides for every priority-track course."""
    report = {}
    for row in showcase.entries():
        if not row["ready"]:
            report[row["slug"]] = []
            continue
        report[row["slug"]] = write_course_guides(row["course"], force=force)
    return report


def guide_path(course: dict, stage_id: int) -> str:
    """Path of the on-disk guide if it exists, else ''."""
    stages_dir = os.path.join(course["dir"], STAGES_DIR)
    if not os.path.isdir(stages_dir):
        return ""
    prefix = f"{stage_id:02d}-"
    for name in sorted(os.listdir(stages_dir)):
        if name.startswith(prefix) and name.endswith(".md"):
            return os.path.join(stages_dir, name)
    return ""
