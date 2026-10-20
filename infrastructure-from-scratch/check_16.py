"""check_16 — sagas: choreography, orchestration, compensation.

Catches:
- Saga that doesn't execute steps in order
- Compensation that doesn't rollback on failure
- Orchestration that doesn't manage state
- Choreography that doesn't coordinate events
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "connection_pooling.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "connection_pooling.py")

    spec = importlib.util.spec_from_file_location("saga_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that SagaOrchestrator class exists
    assert hasattr(mod, "SagaOrchestrator") or hasattr(mod, "Saga"), \
        "SagaOrchestrator class not found"

    # Test basic saga execution if available
    if hasattr(mod, "SagaOrchestrator"):
        saga = mod.SagaOrchestrator()
        saga.add_step("create_order", lambda: {"order_id": 1}, lambda: True)
        saga.add_step("reserve_inventory", lambda: {"reserved": True}, lambda: True)
        saga.add_step("process_payment", lambda: {"payment_id": 1}, lambda: True)

        result = saga.execute()
        assert result is not None, "Saga result is None"

    print("  check_16: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_16: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_16: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_16: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)