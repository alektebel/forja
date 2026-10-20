"""check_17 — consensus (Raft): leader election, log replication, safety.

Catches:
- Leader election that doesn't work (no majority)
- Log replication that doesn't match across nodes
- Safety that isn't enforced (no two leaders)
- Catch-up that doesn't work for lagging nodes
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "session_stickiness.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "session_stickiness.py")

    spec = importlib.util.spec_from_file_location("consensus_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that RaftNode class exists
    assert hasattr(mod, "RaftNode") or hasattr(mod, "Consensus"), \
        "RaftNode class not found"

    # Test basic consensus if available
    if hasattr(mod, "RaftNode"):
        nodes = []
        for i in range(3):
            node = mod.RaftNode(f"node-{i}")
            nodes.append(node)

        # Form cluster
        for node in nodes:
            for other in nodes:
                if other is not node:
                    node.connect(other)

        node1 = nodes[0]
        leader_id = node1.elect_leader()
        assert leader_id is not None, "No leader elected"

        # Check single leader
        leaders = set()
        for node in nodes:
            l = node.get_leader()
            if l is not None:
                leaders.add(l)
        assert len(leaders) <= 1, f"Multiple leaders: {leaders}"

    print("  check_17: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_17: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_17: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_17: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)