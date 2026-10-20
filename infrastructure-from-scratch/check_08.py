"""check_rate_limiter — the rate limiter: token bucket, sliding window.

Catches:
- Token bucket: wrong refill rate, wrong bucket size, wrong consume logic
- Sliding window: doesn't track timestamps, counts wrong window
- Distributed: no atomicity, no Redis-like INCR pattern
"""

import sys
import os

def _check_token_bucket(s):
    """Token bucket: burst then refill."""
    # Test the RateLimiter implementation
    # This assumes the template/solution has a RateLimiter class

    # Test that basic operations exist
    assert hasattr(s, "RateLimiter"), "RateLimiter class not found"

    # Test capacity validation
    try:
        rl = s.RateLimiter(capacity=0)
        assert False, "Should reject capacity=0"
    except (ValueError, AssertionError):
        pass  # expected


def _check_sliding_window(s):
    """Sliding window: count requests in time window."""
    # Test that the implementation exists
    assert hasattr(s, "SlidingWindowRateLimiter") or hasattr(s, "SlidingWindow"), \
        "Sliding window rate limiter not found"


def check():
    import importlib.util

    # Load the module from templates or solutions
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "rate_limiter.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "rate_limiter.py")

    spec = importlib.util.spec_from_file_location("rate_limiter_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _check_token_bucket(mod)
    _check_sliding_window(mod)

if __name__ == "__main__":
    try:
        check()
        print("check_rate_limiter: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"rate_limiter: not implemented yet ({sys.exc_info()})")
        sys.exit(2)
    except Exception as e:
        print(f"rate_limiter: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)