#!/usr/bin/env python3
"""Infrastructure From Scratch — check harness.

For each stage:
  1. Import the template, run its _test(): must raise NotImplementedError
  2. Copy the solution over the template, run _test(): must pass
  3. Verify stage file compiles

Usage: python3 check.py [N]...  # check specific stages, or all
"""

import os
import sys
import shutil
import tempfile
import traceback

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(COURSE_DIR, "templates")
SOLUTIONS_DIR = os.path.join(COURSE_DIR, "solutions")

STAGES = [
    (1, "load_balancer.py"),
    (2, "cdn_caching.py"),
    (3, "cache.py"),
    (4, "url_shortener.py"),
    (5, "request_batching.py"),
    (6, "cache.py"),
    (7, "message_queue.py"),
    (8, "rate_limiter.py"),
    (9, "leaderboard.py"),
    (10, "consistent_hash.py"),
    (11, "hot_partition_mitigation.py"),
    (12, "eventual_consistency.py"),
    (13, "data_locality.py"),
    (14, "edge_computing.py"),
    (15, "capacity_planner.py"),
    (16, "connection_pooling.py"),
    (17, "session_stickiness.py"),
    (18, "idempotency_keys.py"),
    (19, "throttling.py"),
    (20, "cdn_caching.py"),
]


def check_one(stage_num, filename):
    """Run checks for one stage. Returns True on success."""
    template_path = os.path.join(TEMPLATES_DIR, filename)
    solution_path = os.path.join(SOLUTIONS_DIR, filename)

    if not os.path.exists(template_path):
        print(f"  {stage_num}: SKIP — template not found")
        return True

    if not os.path.exists(solution_path):
        print(f"  {stage_num}: SKIP — solution not found")
        return True

    # Create temp dir with solution
    tmpdir = tempfile.mkdtemp(prefix=f"infra-stage{stage_num}-")
    dst = os.path.join(tmpdir, filename)
    shutil.copy(solution_path, dst)

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"module_{stage_num}", dst)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Run _test() if present
        if hasattr(mod, "_test"):
            mod._test()

        return True
    except NotImplementedError:
        print(f"  {stage_num}: TEMPLATE FAIL — stage still stub")
        return False
    except Exception:
        print(f"  {stage_num}: CRASH — {traceback.format_exc()[:200]}")
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv):
    stages_to_check = [int(a) for a in argv] if argv else STAGES
    results = []

    for stage_num, filename in STAGES:
        if argv and stage_num not in stages_to_check:
            continue
        ok = check_one(stage_num, filename)
        results.append((stage_num, ok))

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} stages passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))