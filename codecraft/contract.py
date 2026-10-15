"""Two ways to produce a graded attempt, one result shape.

Existing projects ship a `check.py` that already prints the standard block; we
run it as a subprocess and parse the output. Authored courses ship a `course.py`
that defines `STAGES`; we import it and run the stage checks in-process. Both
paths return the same dict, so the rest of codecraft never cares which mode a
course uses.
"""

import importlib.util
import os
import re
import subprocess
import sys
import traceback
from typing import Dict, List, Optional

from . import patterns

ANSI = re.compile(r"\x1b\[[0-9;]*m")
STATUS_RE = re.compile(r"^\s*([\u2713\u00b7\u2717])\s+(\d+)\.\s+(\S+)\s+(.*?)\s*$")
SUMMARY_RE = re.compile(r"(\d+)/(\d+)\s+passing")
NEXT_RE = re.compile(r"Next:\s*step\s+(\d+)\s+[—-]\s+(.*?)\s*\((.*?)\)")

_STATUS = {"\u2713": "PASS", "\u00b7": "TODO", "\u2717": "FAIL"}

MODE_CHECK = "check"
MODE_COURSE = "course"


# ---------------------------------------------------------------------------
# Parsing an existing check.py's stdout
# ---------------------------------------------------------------------------

def parse_check_output(text: str) -> Dict[str, object]:
    lines = ANSI.sub("", text).splitlines()
    stages: List[dict] = []
    current: Optional[dict] = None
    passed = failed = todo = 0
    next_step = None

    for line in lines:
        m = STATUS_RE.match(line)
        if m:
            current = {
                "id": int(m.group(2)),
                "file": m.group(3),
                "title": m.group(4).strip(),
                "status": _STATUS.get(m.group(1), "FAIL"),
                "detail": "",
            }
            stages.append(current)
            continue
        if current is not None:
            indent = len(line) - len(line.lstrip())
            if line.strip() and indent >= 6:
                current["detail"] += ("" if not current["detail"] else "\n") + line.strip()
                continue
            current = None
        mm = NEXT_RE.search(line)
        if mm:
            next_step = int(mm.group(1))

    for st in stages:
        detail = st["detail"]
        if st["status"] == "TODO" and not detail.lower().startswith("not implemented"):
            st["detail"] = "not implemented yet"
        if st["status"] != "PASS" and patterns.is_exception(detail):
            st["status"] = "ERROR"
        if st["status"] == "PASS":
            passed += 1
        elif st["status"] == "TODO":
            todo += 1
        else:
            failed += 1

    total = len(stages)
    if total and next_step is None:
        for st in stages:
            if st["status"] != "PASS":
                next_step = st["id"]
                break
    return {
        "total": total, "passed": passed, "failed": failed, "todo": todo,
        "next_step": next_step, "stages": stages,
    }


def run_checker(project_dir: str, args: Optional[List[str]] = None) -> dict:
    """Run `<project>/check.py` and parse it. Defaults to --all for full state."""
    argv = [sys.executable, "check.py", *(args if args is not None else ["--all"])]
    proc = subprocess.run(argv, cwd=project_dir, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    return {"returncode": proc.returncode, "stdout": proc.stdout,
            "result": parse_check_output(proc.stdout)}


# ---------------------------------------------------------------------------
# Running an authored course.py in-process
# ---------------------------------------------------------------------------

def load_course_module(course_dir: str):
    path = os.path.join(course_dir, "course.py")
    spec = importlib.util.spec_from_file_location("codecraft_authored_course", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # stage implementations import from their own directory, and course.py
    # imports codecraft.api from the repo root. Every course names its stage
    # modules `stage_NN.py`, so the course being loaded has to WIN that name
    # over any course discovered earlier in this process: they are all on
    # sys.path, and the first match is the one imported.
    root = os.path.dirname(os.path.dirname(os.path.abspath(course_dir)))
    for p in (root, os.path.abspath(course_dir)):
        while p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    spec.loader.exec_module(module)
    return module


def _where(exc: BaseException) -> str:
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        name = os.path.basename(frame.filename)
        if name not in ("contract.py", "course.py"):
            return f"{name}:{frame.lineno} in {frame.name}()"
    return ""


def run_course_module(course_dir: str, stage: Optional[int] = None) -> dict:
    # A previous authored course in this process may have left `stage_01` and
    # friends in sys.modules; drop them so this course's files are imported.
    for key in [k for k in sys.modules if re.match(r"^stage_?\d+$", k)]:
        del sys.modules[key]
    module = load_course_module(course_dir)
    stages_meta = getattr(module, "STAGES", [])
    stages: List[dict] = []
    for st in stages_meta:
        if stage is not None and st.id != stage:
            continue
        try:
            st.check()
            status, detail = "PASS", ""
        except NotImplementedError as exc:
            status, detail = "TODO", f"not implemented yet — {_where(exc) or exc}"
        except AssertionError as exc:
            status, detail = "FAIL", str(exc) or "assertion failed"
        except Exception as exc:                              # noqa: BLE001
            status, detail = "ERROR", f"{type(exc).__name__}: {exc} {_where(exc)}".strip()
        stages.append({"id": st.id, "file": st.file, "title": st.title,
                       "status": status, "detail": detail})
    passed = sum(1 for s in stages if s["status"] == "PASS")
    failed = sum(1 for s in stages if s["status"] in ("FAIL", "ERROR"))
    todo = sum(1 for s in stages if s["status"] == "TODO")
    next_step = next((s["id"] for s in stages if s["status"] != "PASS"), None)
    return {
        "total": len(stages), "passed": passed, "failed": failed, "todo": todo,
        "next_step": next_step, "stages": stages,
    }


# ---------------------------------------------------------------------------
# The stage selector
# ---------------------------------------------------------------------------

def stage_request(course: dict, stage=None, args=None) -> Optional[int]:
    """The one stage an attempt is narrowed to — `cz run <course> --stage N`.

    Returns None when the whole course was asked for. A bare number among the
    checker args is the same request, in both modes: an authored course has no
    argv of its own, and a `check.py` takes the number in its argv anyway
    (`run_attempt` does not add it twice).

    A number the course does not have raises ValueError, naming the stages it
    does have — the caller prints that and runs nothing.
    """
    requested = stage
    if requested is None:
        numbers = [int(a) for a in (args or ()) if str(a).isdigit()]
        requested = numbers[0] if numbers else None
    if requested is None:
        return None
    if requested not in course["stages"]:
        ids = sorted(course["stages"])
        have = f"{ids[0]}..{ids[-1]}" if ids else "none"
        raise ValueError(f"{course['name']} has stages {have} — no stage {requested}")
    return requested



# ---------------------------------------------------------------------------
# Uniform entry point
# ---------------------------------------------------------------------------

def run_attempt(course: dict, args: Optional[List[str]] = None,
                echo: bool = True, stage: Optional[int] = None) -> dict:
    """Run one attempt for a loaded course dict (see manifests.load).

    `stage` narrows the attempt to one stage (`cz run <course> --stage N`),
    refused here — before anything runs — when the course has no such stage.
    An authored course filters its own `STAGES`; a `check.py` course is handed
    the number as the argument it already honours, and `--all` stays the
    default when nothing is asked for.
    """
    stage = stage_request(course, stage=stage, args=args)
    if course["mode"] == MODE_COURSE:
        result = run_course_module(course["dir"], stage=stage)
        stdout = _render_module_stdout(course, result, stage)
    else:
        argv = list(args or ())
        if stage is not None and str(stage) not in argv:
            argv = [str(stage)] + argv
        out = run_checker(course["dir"], argv or None)
        stdout = out["stdout"]
        result = out["result"]
    if echo:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    return result


def _render_module_stdout(course: dict, result: dict,
                          stage: Optional[int] = None) -> str:
    """Print authored-course results in the same visual language as check.py."""
    green, red, grey, bold, reset = (
        "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m")
    head = (f"{course['title']} \u2014 stage {stage} check" if stage is not None
            else f"{course['title']} \u2014 progress check")
    out = [f"\n{bold}{head}{reset}",
           f"{grey}run codecraft after each stage; read the nudge below{reset}\n"]
    for st in result["stages"]:
        if st["status"] == "PASS":
            out.append(f"  {green}\u2713{reset} {st['id']:>2}. {st['file']:<18} {st['title']}")
        elif st["status"] == "TODO":
            out.append(f"  {grey}\u00b7{reset} {st['id']:>2}. {st['file']:<18} {st['title']}")
            out.append(f"      {grey}{st['detail']}{reset}")
        else:
            out.append(f"  {red}\u2717{reset} {st['id']:>2}. {st['file']:<18} {st['title']}")
            for line in st["detail"].splitlines():
                out.append(f"      {red}{line}{reset}")
    scope = f"stage {stage}: " if stage is not None else ""
    out.append(f"\n  {scope}{result['passed']}/{result['total']} passing")
    return "\n".join(out) + "\n"
