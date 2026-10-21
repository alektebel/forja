#!/usr/bin/env python3
"""mutate_all.py — run all mutations for the infrastructure course.

Usage: python3 mutate_all.py [N]...  # run mutations for specific stages, or all
"""

import os
import re
import sys
import subprocess

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))


def mutate_stage(stage_num):
    """Run mutate_NN.py for a stage. Returns (ok, caught, total)."""
    mutate_file = os.path.join(COURSE_DIR, f"mutate_{stage_num:02d}.py")
    if not os.path.exists(mutate_file):
        print(f"  {stage_num:2d}: SKIP — mutate_{stage_num:02d}.py not found")
        return True, 0, 0

    result = subprocess.run(
        [sys.executable, mutate_file],
        cwd=COURSE_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )

    output = result.stdout.strip()
    line = output.splitlines()[-1] if output else ""
    m = re.search(r"CAUGHT (\d+) / (\d+)", line)
    if m and result.returncode == 0:
        print(f"  {stage_num:2d}: {line}")
        return True, int(m.group(1)), int(m.group(2))
    elif m:
        print(f"  {stage_num:2d}: {line}")
        return False, int(m.group(1)), int(m.group(2))
    else:
        print(f"  {stage_num:2d}: ERROR — {line or output[:120]!r} "
              f"(rc {result.returncode})")
        return False, 0, 0


def main(argv):
    import importlib.util
    sys.path.insert(0, os.path.dirname(COURSE_DIR))  # repo root, codecraft.api
    spec = importlib.util.spec_from_file_location(
        "infra_course_mutate_all", os.path.join(COURSE_DIR, "course.py"))
    course = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(course)

    wanted = [int(a) for a in argv] if argv else course.ALL
    total_caught = 0
    total_mutants = 0
    failures = []

    for stage_num in wanted:
        ok, caught, t = mutate_stage(stage_num)
        total_caught += caught
        total_mutants += t
        if not ok:
            failures.append(stage_num)

    print(f"\n{total_caught}/{total_mutants} mutants caught")
    if failures:
        print(f"stages with misses: {failures}")
        return 1
    print("All mutation batteries green")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
