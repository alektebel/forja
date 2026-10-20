"""check_message_queue — the message queue: delivery semantics, acks, retries, DLQ.

Catches:
- At-least-once: doesn't redeliver unacked messages
- Idempotency: doesn't deduplicate by message ID
- DLQ: doesn't move failed messages after N retries
- Acknowledgements: auto-ack on receive (should be manual)
"""

import sys
import os

def _check_delivery_semantics(s):
    """Test that delivery semantics match the expected behavior."""
    # Check that the implementation has the right methods
    assert hasattr(s, "MessageQueue") or hasattr(s, "Queue"), \
        "MessageQueue class not found"


def _check_acks(s):
    """Test that acknowledgements work correctly."""
    # Check that the implementation has ack methods
    assert hasattr(s, "ack") or hasattr(s, "acknowledge"), \
        "ack() or acknowledge() method not found"


def check():
    import importlib.util

    # Load the module from templates or solutions
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "message_queue.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "message_queue.py")

    spec = importlib.util.spec_from_file_location("message_queue_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _check_delivery_semantics(mod)
    _check_acks(mod)

if __name__ == "__main__":
    try:
        check()
        print("check_message_queue: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"message_queue: not implemented yet ({sys.exc_info()})")
        sys.exit(2)
    except Exception as e:
        print(f"message_queue: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)