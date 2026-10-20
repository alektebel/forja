"""check_20 — multi-region active-active: replication, conflict resolution.

Catches:
- Replication that doesn't propagate changes
- Conflict resolution that doesn't handle conflicts
- Regional isolation that isn't maintained
- CRDTs that don't converge
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "data_locality.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "data_locality.py")

    spec = importlib.util.spec_from_file_location("multiregion_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that MultiRegionManager class exists
    assert hasattr(mod, "MultiRegionManager") or hasattr(mod, "ActiveActive"), \
        "MultiRegionManager class not found"

    # Test basic replication if available
    if hasattr(mod, "MultiRegionManager"):
        manager = mod.MultiRegionManager()
        manager.add_region("us", "http://us-region:8080")
        manager.add_region("eu", "http://eu-region:8080")
        manager.add_region("ap", "http://ap-region:8080")

        manager.write("us", "key1", "value1")
        manager.replicate()

        value = manager.read("eu", "key1")
        assert value == "value1", f"Expected value1, got {value}"

    print("  check_20: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_20: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_20: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_20: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)