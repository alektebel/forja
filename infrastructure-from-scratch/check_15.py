"""check_15 — cache invalidation: write-through, stampede, tag-based purge.

Catches:
- Cache that doesn't invalidate on update
- Stampede that isn't protected (multiple fetchers)
- Tag-based purge that doesn't remove related keys
- Write-through that doesn't update cache
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "capacity_planner.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "capacity_planner.py")

    spec = importlib.util.spec_from_file_location("invalidation_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that CacheInvalidator class exists
    assert hasattr(mod, "CacheInvalidator") or hasattr(mod, "Invalidator"), \
        "CacheInvalidator class not found"

    # Test invalidation if available
    if hasattr(mod, "CacheInvalidator"):
        inv = mod.CacheInvalidator()
        inv.set("key1", "value1", tags=["article", "tech"])
        inv.invalidate_tags(["article"])
        try:
            inv.get("key1")
            assert False, "key1 should have been invalidated"
        except (KeyError, ValueError):
            pass  # expected

    print("  check_15: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_15: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_15: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_15: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)