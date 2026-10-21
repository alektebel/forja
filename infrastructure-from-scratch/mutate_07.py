"""mutate_07 — request_batching: 14 anchored mutations, each caught by check_07.

Every mutation replaces one exact, once-occurring line of
`solutions/request_batching.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_7()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/request_batching.py`. If a line ever loses its uniqueness or its
behaviour stops mattering, the file reports SKIP/MISSED — never a silent 100%%.
"""

import contextlib
import importlib.util
import io
import os
import shutil
import signal
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # repo root, for codecraft.api

MODULE = "request_batching.py"
STAGE = 7
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self._stop_event = threading.Event()', '        pass  # mutated', 'L46: statement removed'),
    _m('        self._thread = threading.Thread(target=self._flush_loop, daemon=True)', '        pass  # mutated', 'L51: statement removed'),
    _m('        self._thread.start()', '        pass  # mutated', 'L52: statement removed'),
    _m('        event = threading.Event()', '        pass  # mutated', 'L89: statement removed'),
    _m('        event.wait()', '        pass  # mutated', 'L98: statement removed'),
    _m('        return self._results.get(key)', '        return None', 'L99: return -> None'),
    _m('        flush_now = False', '        pass  # mutated', 'L126: statement removed'),
    _m('            self._results[key] = results.get(key)', '            pass  # mutated', 'L109: statement removed'),
    _m('            self._timer = threading.Timer(self.window_ms / 1000.0, self.flush)', '            pass  # mutated', 'L149: statement removed'),
    _m('                return self._flush_locked()', '                return None', 'L21: return -> None'),
    _m('                self._pending[key] = []', '                pass  # mutated', 'L92: statement removed'),
    _m('                flush_now = True', '                pass  # mutated', 'L132: statement removed'),
    _m('        flush_now = False', '        flush_now = True', 'L126: False -> True'),
    _m('                flush_now = True', '                flush_now = False', 'L132: True -> False')
]


def _verify(course_dir):
    spec = importlib.util.spec_from_file_location(
        "infra_course_mutate", os.path.join(course_dir, "course.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    getattr(mod, f"check_{STAGE}")()


def _grade(source, prefix):
    tmp = tempfile.mkdtemp(prefix=prefix)
    try:
        shutil.copy(os.path.join(HERE, "course.py"),
                    os.path.join(tmp, "course.py"))
        os.makedirs(os.path.join(tmp, "templates"))
        with open(os.path.join(tmp, "templates", MODULE), "w") as f:
            f.write(source)
        signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(
            TimeoutError("mutant too slow")))
        signal.setitimer(signal.ITIMER_REAL, BUDGET)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                _verify(tmp)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    with open(os.path.join(HERE, "solutions", MODULE)) as f:
        content = f.read()
    try:
        _grade(content, "mut07-base-")
    except Exception as e:
        print(f"mutate_07: BASELINE BROKEN — check fails on the "
              f"unmutated solution: {e}")
        return 1

    caught = 0
    missed = 0
    for i, (t, r, l) in enumerate(MUTATIONS):
        if content.count(t) != 1:
            missed += 1
            print(f"  M{i + 1:03d}: SKIP  (anchor not unique)  {l}")
            continue
        try:
            _grade(content.replace(t, r, 1), f"mut07-{i}-")
        except TimeoutError:
            missed += 1
            print(f"  M{i + 1:03d}: MISSED (hang)  {l}")
        except Exception:
            caught += 1
            print(f"  M{i + 1:03d}: CAUGHT  {l}")
        else:
            missed += 1
            print(f"  M{i + 1:03d}: MISSED  {l}")
    print(f"\nMUTATE: CAUGHT {caught} / {caught + missed}  MISSED {missed}")
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
