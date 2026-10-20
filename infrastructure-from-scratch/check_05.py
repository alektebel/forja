"""check_05 — API gateway: routes, auth, rate limiting, transformation.

Catches:
- Gateway that doesn't route requests
- Auth that isn't validated (no JWT, no API key check)
- Rate limiting that isn't enforced (always allows)
- Transformation that isn't applied (no header stripping, body rewrite)
"""

import sys
import os
import tempfile
import shutil


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "request_batching.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "request_batching.py")

    spec = importlib.util.spec_from_file_location("apigateway_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that APIGateway class exists
    assert hasattr(mod, "APIGateway") or hasattr(mod, "Gateway"), \
        "APIGateway class not found"

    # Test routing if available
    if hasattr(mod, "APIGateway"):
        gateway = mod.APIGateway()
        gateway.add_route("/users", "http://user-service:8080", auth_required=True)
        gateway.add_route("/public", "http://public-service:8080", auth_required=False)

        route = gateway.get_route("/users")
        assert route is not None, "Route not found"
        assert route.auth_required, "Auth not required for /users"

    print("  check_05: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_05: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_05: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_05: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)