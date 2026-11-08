"""Run one small AWS From Scratch stage at a time.

    python3 check.py            # stop at the first incomplete stage
    python3 check.py 1          # run stage 1 only
    python3 check.py 4 6        # run stages 4 through 6
    python3 check.py --all      # see every stage
"""

import json
import pathlib
import sys
import traceback
from typing import Callable, List, Tuple

sys.dont_write_bytecode = True
from stage_checks import CHECKS as STAGE_CHECKS

ROOT = pathlib.Path(__file__).parent
LESSONS = json.loads((ROOT / "lessons.json").read_text(encoding="utf-8"))
assert [lesson["id"] for lesson in LESSONS] == list(range(1, len(STAGE_CHECKS) + 1))
CHECKS: List[Tuple[str, str, Callable[[], None]]] = [
    (lesson["file"], lesson["title"], check)
    for lesson, check in zip(LESSONS, STAGE_CHECKS)
]

PASS, FAIL, TODO, ERROR = "PASS", "FAIL", "TODO", "ERROR"
GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m")


def run_one(check: Callable[[], None]) -> Tuple[str, str]:
    try:
        check()
        return PASS, ""
    except NotImplementedError as exc:
        return TODO, str(exc)
    except AssertionError as exc:
        return FAIL, str(exc) or "assertion failed"
    except Exception as exc:  # noqa: BLE001
        where = ""
        for frame in reversed(traceback.extract_tb(sys.exc_info()[2])):
            if frame.filename.endswith(".py") and frame.filename != __file__:
                where = f" at {pathlib.Path(frame.filename).name}:{frame.lineno}"
                break
        return ERROR, f"{type(exc).__name__}: {exc}{where}"


def main(argv: List[str]) -> int:
    keep_going = "--all" in argv
    wanted = [int(arg) for arg in argv if arg.isdigit()]
    if len(wanted) > 1:
        wanted = list(range(min(wanted), max(wanted) + 1))
    if wanted and (min(wanted) < 1 or max(wanted) > len(CHECKS)):
        print(f"Stage must be between 1 and {len(CHECKS)}.")
        return 2

    print(f"\n{BOLD}AWS From Scratch — progress check{RESET}\n")
    passed = failed = todo = 0
    first_gap = None
    for index, (filename, title, check) in enumerate(CHECKS, start=1):
        if wanted and index not in wanted:
            continue
        status, detail = run_one(check)
        optional = " (optional)" if LESSONS[index - 1]["optional"] else ""
        if status == PASS:
            passed += 1
            print(f"  {GREEN}✓{RESET} {index:>2}. {filename:<16} {title}{optional}")
        elif status == TODO:
            todo += 1
            first_gap = first_gap or index
            print(f"  {GREY}·{RESET} {index:>2}. {filename:<16} {title}{optional}")
            print(f"      {GREY}not implemented yet{(' — ' + detail) if detail else ''}{RESET}")
            if not keep_going and not wanted:
                break
        else:
            failed += 1
            first_gap = first_gap or index
            color = RED if status == FAIL else YELLOW
            print(f"  {color}✗{RESET} {index:>2}. {filename:<16} {title}{optional}")
            print(f"      {color}{detail}{RESET}")
            if not keep_going and not wanted:
                break

    total = len(wanted) if wanted else len(CHECKS)
    print(f"\n  {passed}/{total} passing", end="")
    if failed:
        print(f", {failed} failing", end="")
    if todo:
        print(f", {todo} to write", end="")
    print()
    if first_gap:
        filename, title, _ = CHECKS[first_gap - 1]
        print(f"\n  Next: stage {first_gap} — {title} ({filename})")
        print(f"  Read: forja guide aws-from-scratch {first_gap}\n")
    elif passed == len(CHECKS):
        print("\n  All AWS From Scratch stages pass.\n")
    return 1 if failed or (wanted and todo) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
