"""Public starter files for the browser's course workspaces.

Each course is bundled on demand: its top-level templates (`.py`, or `.sas` for
the SAS course), the checker and the local support modules they import.
Reference solutions, local profiles and repository metadata never enter a
bundle.
"""

from pathlib import Path
import json
import re

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "aws-from-scratch"
TEXT_SUFFIXES = {".py", ".sas", ".json", ".txt", ".csv", ".toml", ".yaml", ".yml", ".cfg", ".ini"}
CHECKER_FILES = {"check.py", "course.py", "stage_checks.py", "validate_course.py", "conftest.py"}
SKIP_DIRS = {"solutions", "_build", "__pycache__", ".git", ".pytest_cache", ".mypy_cache"}
COURSE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def course_names() -> list[str]:
    names = []
    for path in REPO.iterdir():
        if not path.is_dir() or not COURSE_RE.match(path.name):
            continue
        if (path / "course.py").exists() or (path / "check.py").exists():
            names.append(path.name)
    return sorted(names)


def _text_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 500_000:
                continue
            files[rel.as_posix()] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return files


def bundle(course: str) -> dict:
    if not COURSE_RE.match(course or ""):
        raise ValueError(f"invalid course: {course!r}")
    root = REPO / course
    if not root.is_dir():
        raise FileNotFoundError(course)
    if (root / "course.py").exists():
        entry, mode = "course.py", "course"
    elif (root / "check.py").exists():
        entry, mode = "check.py", "check"
    else:
        raise FileNotFoundError(f"{course} has no course.py or check.py")

    files = _text_files(root)
    if mode == "course":
        package = Path(__file__).resolve().parent
        files["codecraft/__init__.py"] = ""
        files["codecraft/api.py"] = (package / "api.py").read_text(encoding="utf-8")

    editable = [
        name for name in files
        if "/" not in name and name.endswith(".sas")
    ]
    if not editable:
        editable = [
            name for name in files
            if "/" not in name and name.endswith(".py") and name not in CHECKER_FILES
            and not re.match(r"^(check|mutate)_\d+\.py$|^(check|mutate|run)_all\.py$", name)
        ]
    stage_files = {}
    if not editable:
        for name in files:
            parts = name.split("/")
            if len(parts) == 2 and parts[0] == "templates" and name.endswith(".py"):
                editable.append(name)
                stage_files[parts[1]] = name
    learning = {}
    lessons = root / "lessons.json"
    if lessons.exists():
        rows = json.loads(lessons.read_text(encoding="utf-8"))
        learning = {str(row["id"]): row["learning"] for row in rows if row.get("learning")}
    return {
        "course": course,
        "mode": mode,
        "entry": entry,
        "editable": editable,
        "stageFiles": stage_files,
        "files": files,
        "learning": learning,
    }


def aws_bundle() -> dict:
    return bundle("aws-from-scratch")
