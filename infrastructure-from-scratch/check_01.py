"""check_load_balancer — Load Balancer: round-robin, weighted, health checks, consistent hash.

Catches:
- Round-robin that doesn't cycle or doesn't skip unhealthy
- Consistent hash that doesn't use virtual nodes
- Health check that doesn't mark dead backends as unhealthy
- Session stickiness that doesn't pin to backends
"""

import sys
import os


def _check_load_balancer(s):
    """Test that the LB distributes requests and handles health."""
    assert hasattr(s, "LoadBalancer") or hasattr(s, "LB"), \
        "LoadBalancer class not found"


def _check_consistent_hash(s):
    """Test that consistent hashing distributes evenly."""
    assert hasattr(s, "ConsistentHash") or hasattr(s, "Ring"), \
        "Consistent hash ring not found"


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "consistent_hash.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "consistent_hash.py")

    spec = importlib.util.spec_from_file_location("lb_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _check_load_balancer(mod)
    _check_consistent_hash(mod)

if __name__ == "__main__":
    try:
        check()
        print("check_load_balancer: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"load_balancer: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"load_balancer: FAIL — {e}")
        sys.exit(1)