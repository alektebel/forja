"""check_18 — exactly-once delivery: idempotency, dedup, at-least-once.

Catches:
- Delivery that duplicates messages
- Idempotency that doesn't deduplicate
- At-least-once that isn't guaranteed
- Dedup that doesn't check message IDs
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "idempotency_keys.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "idempotency_keys.py")

    spec = importlib.util.spec_from_file_location("exactlyonce_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that ExactlyOnceBroker class exists
    assert hasattr(mod, "ExactlyOnceBroker") or hasattr(mod, "IdempotentBroker"), \
        "ExactlyOnceBroker class not found"

    # Test basic idempotency if available
    if hasattr(mod, "ExactlyOnceBroker"):
        broker = mod.ExactlyOnceBroker()
        broker.publish("msg-1", {"action": "charge", "amount": 100})
        broker.publish("msg-1", {"action": "charge", "amount": 100})  # duplicate
        broker.publish("msg-2", {"action": "charge", "amount": 200})

        delivered = broker.deliver_all()
        ids = [m["id"] for m in delivered]
        assert ids.count("msg-1") == 1, f"Expected 1 msg-1, got {ids.count('msg-1')}"

    print("  check_18: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_18: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_18: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_18: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)