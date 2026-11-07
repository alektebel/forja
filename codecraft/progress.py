"""Real progress for every course: what is written, and what passes.

Two signals, both read live from the working tree, so neither is a number you
can fake:

  repo    the stub markers still standing in the course templates. A function
          is written when its ``raise NotImplementedError`` is gone. The
          baseline is the marker count of the *pristine* templates, kept below
          rather than recomputed, so a half-finished course cannot suddenly
          report itself 100% done.
  checks  the course's own ``check.py --all``, parsed to N/M passing. This is
          the number that cannot be gamed, and the one the tree's bar shows.

The two disagree exactly when you have written code that is still wrong — the
state worth seeing. ``repo`` answers "how much have I written"; ``checks``
answers "how much works".

    python3 codecraft/cli.py progress      # the table, in the terminal
"""

import pathlib
import re
import sys

from . import contract

# Markers measured on the pristine templates. Regenerate with the CLI when you
# author a new course that ships stubs; a course with no entry falls back to its
# current marker count, which reads as 0% written rather than inventing progress.
BASELINE = {
    "llm-from-scratch": 26,
    "context-caching": 94,
    "contextcite": 42,
    "dynamo-paper": 70,
    "aws-from-scratch": 95,
    "deploy-and-debug": 34,
    "compiler-and-vgpu": 53,
}

# Suffix -> (primary marker that cannot lie, fallback comment marker). The
# Python count is honest: the marker disappears when the function is written.
# The C/CUDA/Haskell counts are honest only if you delete the TODO comment.
_MARKERS = {
    ".py": (r"raise NotImplementedError", r"#\s*TODO"),
    ".lean": (r"\bsorry\b", r"--\s*TODO"),
    ".hs": (r"=\s*undefined", r"--\s*TODO"),
    ".c": (r"\bTODO\b", r"\bFIXME\b"),
    ".h": (r"\bTODO\b", r"\bFIXME\b"),
    ".cu": (r"\bTODO\b", r"\bFIXME\b"),
}

_SKIP_NAMES = {"check.py", "progress.py", "serve.py", "course.py"}


def scan_markers(directory) -> int:
    """Markers still standing in a course's templates. Solutions never count."""
    directory = pathlib.Path(directory)
    primary = fallback = 0
    for path in directory.rglob("*"):
        if (not path.is_file() or "solutions" in path.parts
                or "__pycache__" in path.parts or path.name in _SKIP_NAMES):
            continue
        patterns = _MARKERS.get(path.suffix)
        if not patterns:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        primary += len(re.findall(patterns[0], text))
        fallback += len(re.findall(patterns[1], text))
    # A file with real NotImplementedError stubs is measured by those; the TODO
    # comments beside them are guidance, not work items, and counting both would
    # make an implemented file look half done forever.
    return primary if primary else fallback


def repo_signal(course: dict) -> dict:
    """How much of a course is written, from the templates on disk."""
    baseline = BASELINE.get(course["name"]) or scan_markers(course["dir"]) or 0
    remaining = scan_markers(course["dir"])
    written = max(0, baseline - remaining)
    fraction = (written / baseline) if baseline else 0.0
    return {"baseline": baseline, "remaining": remaining, "written": written,
            "fraction": round(fraction, 4)}


def checks_signal(course: dict):
    """Run the course's own checker; N/M passing, or None if it has no checker."""
    if course.get("mode") != contract.MODE_CHECK:
        return None
    try:
        outcome = contract.run_checker(course["dir"], ["--all"])
    except Exception as exc:                                   # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "total": 0, "passed": 0,
                "next_step": None, "stages": {}}
    res = outcome["result"]
    return {
        "total": res["total"], "passed": res["passed"], "failed": res["failed"],
        "todo": res["todo"], "next_step": res["next_step"],
        "stages": {str(s["id"]): {"status": s["status"], "file": s["file"],
                                  "title": s["title"]} for s in res["stages"]},
    }


def build(courses) -> list:
    """One row per course: title, repo signal, checks signal, current stage."""
    rows = []
    for course in courses:
        repo = repo_signal(course)
        checks = checks_signal(course)
        current = None
        if checks and checks["next_step"]:
            current = checks["next_step"]
        elif checks and checks["total"] and checks["passed"] == checks["total"]:
            current = None
        rows.append({"name": course["name"], "title": course["title"],
                     "dir": course["dir"], "mode": course["mode"],
                     "order": course.get("order", 99),
                     "repo": repo, "checks": checks, "next_step": current})
    rows.sort(key=lambda r: (r["order"], r["name"]))
    return rows


# ---------------------------------------------------------------------------
# Terminal rendering (the web reads build(); this is the same data in text)
# ---------------------------------------------------------------------------

def render(courses, ink) -> str:
    rows = build(courses)
    if not rows:
        return "  no courses found.\n"
    width = max(len(r["name"]) for r in rows)
    lines = ["", ink("  codecraft · progress", "\033[1m"),
             ink("  repo = template markers written   checks = checker cannot be gamed",
                 "\033[90m"), ""]
    tot_p = tot_c = tot_rem = tot_base = 0
    for r in rows:
        repo, checks = r["repo"], r["checks"]
        tot_rem += repo["remaining"]
        tot_base += repo["baseline"]
        if checks:
            tot_p += checks["passed"]
            tot_c += checks["total"]
        bar = _bar(repo["fraction"])
        cbar = _bar((checks["passed"] / checks["total"]) if checks and checks["total"] else 0.0)
        ctext = (f"{checks['passed']:>2}/{checks['total']:<2}" if checks else " -- ")
        nxt = f"  next {checks['next_step']}" if checks and checks["next_step"] else ""
        lines.append(f"  {r['name']:<{width}}  repo {bar} {repo['fraction']*100:>5.1f}%"
                     f"   checks {cbar} {ctext}{nxt}")
    lines.append("")
    frac = (tot_base - tot_rem) / tot_base if tot_base else 0.0
    lines.append(ink(f"  {tot_p}/{tot_c} checks passing · {tot_rem} stub markers left "
                     f"({frac*100:.1f}% written) · {len(rows)} courses",
                     "\033[90m"))
    lines.append("")
    return "\n".join(lines)


def _bar(fraction: float, width: int = 12) -> str:
    filled = int(round(max(0.0, min(1.0, fraction)) * width))
    colour = "\033[32m" if filled >= width else "\033[33m"
    if filled <= 0:
        return f"\033[90m{'.' * width}\033[0m"
    return f"{colour}{'#' * filled}\033[90m{'.' * (width - filled)}\033[0m"
