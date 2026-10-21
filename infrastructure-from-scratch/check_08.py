"""check_08 — connection_pooling: graded against templates/connection_pooling.py.

Delegates to `course.py`'s `check_8` so `python3 check_08.py`,
`run_all.py` and `codecraft run infrastructure-from-scratch` grade the
identical assertions: the module's surface, its probe, and its own `_test()`.

Exit codes: 0 pass, 2 stub (NotImplementedError), 1 failure.
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # repo root, for codecraft.api

_spec = importlib.util.spec_from_file_location(
    "infra_course", os.path.join(HERE, "course.py"))
course = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(course)


def check():
    course.check_8()


if __name__ == "__main__":
    try:
        check()
        print("check_connection_pooling: PASS")
        sys.exit(0)
    except NotImplementedError:
        print("connection_pooling: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"connection_pooling: FAIL — {e}")
        sys.exit(1)
