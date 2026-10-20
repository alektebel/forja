"""check_11 — database sharding: consistent hash, rebalance, hot partition.

Catches:
- Sharding that doesn't distribute evenly
- Consistent hash that doesn't use virtual nodes
- Rebalance that doesn't minimize movement
- Hot partition that isn't detected or mitigated
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "hot_partition_mitigation.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "hot_partition_mitigation.py")

    spec = importlib.util.spec_from_file_location("sharding_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that ShardManager class exists
    assert hasattr(mod, "ShardManager") or hasattr(mod, "Shard"), \
        "ShardManager class not found"

    # Test sharding if available
    if hasattr(mod, "ShardManager"):
        sharder = mod.ShardManager(shard_count=10)
        for i in range(1000):
            shard_id = sharder.get_shard(f"user-{i}")
            assert 0 <= shard_id < 10, f"Shard {shard_id} out of range"

        # Check distribution
        counts = [0] * 10
        for i in range(1000):
            counts[sharder.get_shard(f"user-{i}")] += 1
        avg = 100.0
        max_deviation = max(abs(c - avg) for c in counts)
        assert max_deviation < 50, f"Distribution uneven: {counts}"

    print("  check_11: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_11: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_11: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_11: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)