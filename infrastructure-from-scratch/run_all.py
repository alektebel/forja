#!/usr/bin/env python3
"""run_all.py — run all checks for the infrastructure course.

Usage: python3 run_all.py [N]...  # run checks for specific stages, or all
"""

import os
import sys
import subprocess
import importlib.util

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import stages from course.py (course.py imports codecraft.api)
sys.path.insert(0, COURSE_DIR)
sys.path.insert(0, os.path.dirname(COURSE_DIR))
import course

STAGES = course.STAGES


def check_stage(stage_num, filename):
    """Run check_NN.py for a stage."""
    check_file = os.path.join(COURSE_DIR, f"check_{stage_num:02d}.py")
    if not os.path.exists(check_file):
        print(f"  {stage_num}: SKIP — check_{stage_num:02d}.py not found")
        return True

    result = subprocess.run(
        [sys.executable, check_file],
        cwd=COURSE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode == 0:
        print(f"  {stage_num}: PASS")
        return True
    elif result.returncode == 2:
        print(f"  {stage_num}: TEMPLATE FAIL (stub not implemented) — {filename}")
        return False
    else:
        print(f"  {stage_num}: FAIL — {result.stdout.strip()}")
        return False


def main(argv):
    stages_to_check = [int(a) for a in argv] if argv else None
    results = []

    for st in course.STAGES:
        if stages_to_check is None or st.id in stages_to_check:
            ok = check_stage(st.id, st.file)
            results.append((st.id, ok))

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} stages passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))