#!/usr/bin/env python3
"""run_all.py — run all checks for the infrastructure course.

Usage: python3 run_all.py [N]...  # run checks for specific stages, or all
"""

import os
import sys
import subprocess
import importlib.util

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import stages from course.py
sys.path.insert(0, COURSE_DIR)
import course

STAGES = course.STAGES


def check_stage(stage_num, filename):
    """Run check_NN.py for a stage."""
    check_file = os.path.join(COURSE_DIR, f"check_{stage_num}.py")
    if not os.path.exists(check_file):
        print(f"  {stage_num:2d}: SKIP — check_{stage_num}.py not found")
        return True

    env = os.environ.copy()
    env["INFRA_COURSE_DIR"] = COURSE_DIR
    env["INFRA_TEMPLATE_DIR"] = os.path.join(COURSE_DIR, "templates")

    result = subprocess.run(
        [sys.executable, check_file],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode == 0:
        print(f"  {stage_num:2d}: PASS")
        return True
    elif result.returncode == 2:
        print(f"  {stage_num:2d}: TEMPLATE FAIL (stub not implemented)")
        return False
    else:
        print(f"  {stage_num:2d}: FAIL — {result.stdout.strip()}")
        return False


def main(argv):
    stages_to_check = [int(a) for a in argv] if argv else range(1, 21)
    results = []

    for stage_num, filename in STAGES:
        if stage_num in stages_to_check or not argv:
            ok = check_stage(stage_num, filename)
            results.append((stage_num, ok))

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} stages passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))