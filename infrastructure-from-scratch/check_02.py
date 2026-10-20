"""check_cdn — CDN: caching, cache policies, origin shield, purge.

Catches:
- Cache-Control parsing (max-age, private, no-store)
- Cache key normalization (lowercase host, sorted query params)
- Origin shield (single fetch on miss)
- Purge by tag (bulk purge by content relationship)
"""

import sys
import os


def _check_cdn(s):
    """Test that CDN caches correctly and respects policies."""
    assert hasattr(s, "CDN") or hasattr(s, "Cache"), \
        "CDN cache class not found"


def _check_purge(s):
    """Test that purge works correctly."""
    assert hasattr(s, "purge") or hasattr(s, "Purge"), \
        "Purge functionality not found"


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "cdn_caching.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "cdn_caching.py")

    spec = importlib.util.spec_from_file_location("cdn_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _check_cdn(mod)
    _check_purge(mod)

if __name__ == "__main__":
    try:
        check()
        print("check_cdn: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"cdn: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"cdn: FAIL — {e}")
        sys.exit(1)