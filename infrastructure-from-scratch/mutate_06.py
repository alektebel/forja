"""mutate_06 — throttling: 23 anchored mutations, each caught by check_06.

Every mutation replaces one exact, once-occurring line of
`solutions/throttling.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_6()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/throttling.py`. If a line ever loses its uniqueness or its
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

MODULE = "throttling.py"
STAGE = 6
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.capacity = capacity', '        pass  # mutated', 'L13: statement removed'),
    _m('        self.drain_rate = drain_rate', '        pass  # mutated', 'L14: statement removed'),
    _m('        self.interval = window_seconds / rate', '        pass  # mutated', 'L40: statement removed'),
    _m('        sleep_time = allowed_at - time.time()', '        pass  # mutated', 'L49: statement removed'),
    _m('        self._task_counter = 0', '        pass  # mutated', 'L62: statement removed'),
    _m('        t = threading.Thread(target=self._worker_loop, daemon=True)', '        pass  # mutated', 'L66: statement removed'),
    _m('        deadline = time.time() + timeout', '        pass  # mutated', 'L88: statement removed'),
    _m('            self._level = max(0.0, self._level - elapsed * self.drain_rate)', '            pass  # mutated', 'L23: statement removed'),
    _m('            self._level += amount', '            pass  # mutated', 'L27: statement removed'),
    _m('            return True', '            return None', 'L28: return -> None'),
    _m('            allowed_at = max(now, self._next_allowed.get(key, now))', '            pass  # mutated', 'L47: statement removed'),
    _m('            self._next_allowed[key] = allowed_at + self.interval', '            pass  # mutated', 'L48: statement removed'),
    _m('            time.sleep(sleep_time)', '            pass  # mutated', 'L51: statement removed'),
    _m('            task_id = self._task_counter', '            pass  # mutated', 'L83: statement removed'),
    _m('                return False', '                return None', 'L26: return -> None'),
    _m('                    return self._results.pop(task_id)', '                    return None', 'L92: return -> None'),
    _m('        self._level: float = 0.0', '        self._level: float = 1.0', 'L15: 0.0 -> 1.0'),
    _m('            self._level += amount', '            self._level -= amount', 'L27: aug-assign flipped'),
    _m('            self._level = max(0.0, self._level - elapsed * self.drain_rate)', '            self._level = min(0.0, self._level - elapsed * self.drain_rate)', 'L23: max -> min'),
    _m('            return True', '            return False', 'L28: True -> False'),
    _m('            allowed_at = max(now, self._next_allowed.get(key, now))', '            allowed_at = min(now, self._next_allowed.get(key, now))', 'L47: max -> min'),
    _m('            self._level = max(0.0, self._level - elapsed * self.drain_rate)', '            self._level = max(1.0, self._level - elapsed * self.drain_rate)', 'L23: 0.0 -> 1.0'),
    _m('                return False', '                return True', 'L26: False -> True')
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
        _grade(content, "mut06-base-")
    except Exception as e:
        print(f"mutate_06: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut06-{i}-")
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
