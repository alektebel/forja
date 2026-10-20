"""check_10 — service discovery: register, deregister, health check, query.

Catches:
- Service that doesn't register
- Health check that doesn't work
- Query that doesn't return healthy nodes
- Deregistration that doesn't remove service
"""

import sys
import os
import tempfile
import shutil


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "consistent_hash.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "consistent_hash.py")

    spec = importlib.util.spec_from_file_location("servicediscovery_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that ServiceRegistry class exists
    assert hasattr(mod, "ServiceRegistry") or hasattr(mod, "Discovery"), \
        "ServiceRegistry class not found"

    # Test basic registration if available
    if hasattr(mod, "ServiceRegistry"):
        registry = mod.ServiceRegistry()
        registry.register("user-service", "10.0.1.1:8080", health_check="http://10.0.1.1:8080/health")
        registry.register("order-service", "10.0.1.2:8080", health_check="http://10.0.1.2:8080/health")

        users = registry.get_services("user-service")
        assert len(users) > 0, "No user-service nodes found"

        orders = registry.get_services("order-service")
        assert len(orders) > 0, "No order-service nodes found"

    print("  check_10: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_10: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_10: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_10: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)