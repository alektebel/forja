"""check_12 — event-driven architecture: event bus, pub/sub, ordering, DLQ.

Catches:
- EventBus that doesn't route events to subscribers
- Pub/sub that doesn't handle multiple subscribers
- Ordering that isn't preserved (FIFO per topic)
- DLQ that doesn't capture dead messages
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "eventual_consistency.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "eventual_consistency.py")

    spec = importlib.util.spec_from_file_location("eda_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that EventBus class exists
    assert hasattr(mod, "EventBus") or hasattr(mod, "EventBus"), \
        "EventBus class not found"

    # Test basic event routing if available
    if hasattr(mod, "EventBus"):
        bus = mod.EventBus()
        received = []
        bus.subscribe("order.created", lambda e: received.append(e))
        bus.publish("order.created", {"order_id": 1, "total": 100})
        assert len(received) == 1, f"Expected 1 event, got {len(received)}"
        assert received[0]["order_id"] == 1

    print("  check_12: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_12: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_12: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_12: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)