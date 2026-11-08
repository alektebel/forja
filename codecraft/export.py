"""Export a course as a standalone starter folder (CodeCrafters-shaped).

Copies templates + checker + START.md / stages guides into a destination
directory. Solutions stay out — the learner's repo should not ship answers.
"""

from __future__ import annotations

import os
import shutil

from . import guide, manifests

# Never copy these into an exported starter.
_SKIP_NAMES = {
    "solutions", "__pycache__", ".git", "_build", ".pytest_cache",
    ".mypy_cache", "mutate_01.py", "validate_course.py",  # authoring tools stay in-repo
}
_SKIP_PREFIXES = ("mutate_", ".")
_SKIP_SUFFIXES = (".pyc",)


def _should_skip(name: str) -> bool:
    if name in _SKIP_NAMES:
        return True
    if any(name.startswith(p) for p in _SKIP_PREFIXES):
        return True
    if any(name.endswith(s) for s in _SKIP_SUFFIXES):
        return True
    return False


def smoke(course: dict) -> tuple[bool, list[str]]:
    """Stage-0 checks: course loads, templates exist, checker is invokable."""
    notes = []
    root = course["dir"]
    if not os.path.isdir(root):
        return False, [f"missing directory {root}"]

    has_check = os.path.exists(os.path.join(root, "check.py"))
    has_course = os.path.exists(os.path.join(root, "course.py"))
    if not (has_check or has_course):
        return False, ["no check.py or course.py"]
    notes.append("grader present (" + ("course.py" if has_course else "check.py") + ")")

    stages = course.get("stages") or {}
    if not stages:
        return False, ["course has zero stages"]
    notes.append(f"{len(stages)} stages registered")

    missing = []
    for sid, meta in stages.items():
        file = meta.get("file")
        if not file:
            continue
        # Prefer course root; fall back to templates/<file> (infra layout).
        path = os.path.join(root, file)
        alt = os.path.join(root, "templates", file)
        if not os.path.exists(path) and not os.path.exists(alt):
            missing.append(file)
    if missing:
        return False, [f"missing template(s): {', '.join(missing[:5])}"]
    notes.append("all stage files on disk")

    start = os.path.join(root, "START.md")
    if os.path.exists(start):
        notes.append("START.md ready")
    else:
        notes.append("START.md missing — run: forja guides --write")

    return True, notes


def export_course(slug: str, dest: str, force: bool = False) -> str:
    """Copy a runnable starter to dest. Returns the absolute path written."""
    course = manifests.load(slug)
    if course is None:
        raise ValueError(f"no course named {slug!r}")

    dest = os.path.abspath(dest)
    if os.path.exists(dest):
        if not force:
            raise FileExistsError(
                f"{dest} already exists (pass --force to replace)")
        shutil.rmtree(dest)
    os.makedirs(dest)

    # Ensure guides exist before copy.
    guide.write_course_guides(course, force=False)

    src = course["dir"]
    for name in sorted(os.listdir(src)):
        if _should_skip(name):
            continue
        # Skip per-stage mutate_NN.py in infrastructure-from-scratch.
        if name.startswith("mutate_") and name.endswith(".py"):
            continue
        if name.startswith("check_") and name.endswith(".py") and name != "check.py":
            # infrastructure check_NN.py helpers are part of the grader — keep.
            pass
        from_path = os.path.join(src, name)
        to_path = os.path.join(dest, name)
        if os.path.isdir(from_path):
            shutil.copytree(from_path, to_path, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "solutions"))
        else:
            shutil.copy2(from_path, to_path)

    readme = os.path.join(dest, "README.forja.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(
            f"# {course['title']} — Forja starter\n\n"
            f"Exported from `{slug}`.\n\n"
            "## Loop\n\n"
            "```bash\n"
            f"forja smoke {slug}          # stage 0\n"
            f"forja guide {slug} 1        # stage page\n"
            f"forja test {slug} --stage 1 # run the tester\n"
            "```\n\n"
            "Or from this directory:\n\n"
            "```bash\n"
            "python3 check.py 1           # if this course uses check.py\n"
            "python3 course.py            # if this course uses course.py\n"
            "```\n\n"
            "Solutions are intentionally not included.\n"
        )
    return dest
