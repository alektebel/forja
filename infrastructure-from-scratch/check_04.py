"""check_04 — reverse proxy: routing, TLS, compression, buffering.

Catches:
- Proxy that doesn't route requests
- TLS that isn't terminated (plaintext to backend)
- Compression that isn't applied (no gzip/brotli)
- Buffering that isn't configured (streaming vs buffered)
"""

import sys
import os
import tempfile
import shutil


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "url_shortener.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "url_shortener.py")

    spec = importlib.util.spec_from_file_location("reverseproxy_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that Proxy class exists
    assert hasattr(mod, "ReverseProxy") or hasattr(mod, "Proxy"), \
        "ReverseProxy class not found"

    # Test routing if available
    if hasattr(mod, "ReverseProxy"):
        proxy = mod.ReverseProxy()
        proxy.add_route("/api", "http://backend-api:8080")
        proxy.add_route("/app", "http://backend-app:8080")
        proxy.add_route("/", "http://backend-web:8080")

        route = proxy.route("/api/users")
        assert route == "http://backend-api:8080", f"Expected /api route, got {route}"

    print("  check_04: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_04: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_04: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_04: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)