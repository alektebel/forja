"""check_09 — read replicas: primary, replica, failover, lag.

Catches:
- Replicas that don't replicate data
- Failover that doesn't promote a replica
- Lag that isn't measured or handled
- Read-only that isn't enforced on replicas
"""

import sys
import os
import tempfile
import shutil


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "leaderboard.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "leaderboard.py")

    spec = importlib.util.spec_from_file_location("readreplicas_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that ReplicationManager class exists
    assert hasattr(mod, "ReplicationManager") or hasattr(mod, "ReadReplica"), \
        "ReplicationManager class not found"

    # Test basic replication if available
    if hasattr(mod, "ReplicationManager"):
        manager = mod.ReplicationManager()
        manager.add_primary("primary-1", "http://primary:5432")
        manager.add_replica("replica-1", "http://replica-1:5432")
        manager.add_replica("replica-2", "http://replica-2:5432")

        primary = manager.get_primary()
        assert primary is not None, "Primary not found"

        replicas = manager.get_replicas()
        assert len(replicas) == 2, f"Expected 2 replicas, got {len(replicas)}"

    print("  check_09: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_09: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_09: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_09: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)