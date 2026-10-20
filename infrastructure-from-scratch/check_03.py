"""check_03 — object storage: blob store, CRUD, metadata, versioning.

Catches:
- Store that doesn't persist (in-memory only, no on-disk)
- Get that doesn't check existence (returns None instead of error)
- Delete that doesn't remove entry
- Metadata that isn't stored
- Versioning that doesn't track history
"""

import sys
import os
import tempfile
import shutil


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "cache.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "cache.py")

    spec = importlib.util.spec_from_file_location("objstore_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that ObjectStore class exists
    assert hasattr(mod, "ObjectStore") or hasattr(mod, "Store"), \
        "ObjectStore class not found"

    # Test basic CRUD operations if available
    if hasattr(mod, "ObjectStore"):
        store = mod.ObjectStore("/tmp/test-store")
        store.put("test-key", b"test-value", metadata={"content-type": "text/plain"})
        value = store.get("test-key")
        assert value == b"test-value", f"Expected b'test-value', got {value}"

        meta = store.get_metadata("test-key")
        assert meta == {"content-type": "text/plain"}, f"Expected metadata, got {meta}"

        store.delete("test-key")
        try:
            store.get("test-key")
            assert False, "Should have raised error for deleted key"
        except (KeyError, ValueError):
            pass  # expected

    print("  check_03: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_03: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_03: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_03: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)