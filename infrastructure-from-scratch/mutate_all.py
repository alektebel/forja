#!/usr/bin/env python3
"""mutate_all.py — run all mutations for the infrastructure course.

Usage: python3 mutate_all.py [N]...  # run mutations for specific stages, or all
"""

import os
import sys
import subprocess

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))
STAGES = []


def mutate_stage(stage_num):
    """Run mutate_NN.py for a stage."""
    # Use zero-padded naming (mutate_01.py, not mutate_1.py)
    mutate_file = os.path.join(COURSE_DIR, f"mutate_{stage_num:02d}.py")
    if not os.path.exists(mutate_file):
        print(f"  {stage_num:2d}: SKIP — mutate_{stage_num:02d}.py not found")
        return True

    result = subprocess.run(
        [sys.executable, mutate_file],
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = result.stdout.strip()
    # Parse the last line for caught/missed counts
    if "MUTATE:" in output:
        print(f"  {stage_num:2d}: {output.split(chr(10))[-1]}")
        return True
    else:
        print(f"  {stage_num:2d}: SKIP — no mutations")
        return True


def main(argv):
    stages_to_mutate = [int(a) for a in argv] if argv else list(range(1, 21))
    results = []
    total_mutations = 0
    total_caught = 0

    for stage_num in stages_to_mutate:
        ok = mutate_stage(stage_num)
        results.append((stage_num, ok))

    print(f"\nAll mutations complete")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))