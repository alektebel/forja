"""mutate_08 — connection_pooling: 30 anchored mutations, each caught by check_08.

Every mutation replaces one exact, once-occurring line of
`solutions/connection_pooling.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_8()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/connection_pooling.py`. If a line ever loses its uniqueness or its
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

MODULE = "connection_pooling.py"
STAGE = 8
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        return f"result:{query}"', '        return None', 'L25: return -> None'),
    _m('        return self._healthy', '        return None', 'L32: return -> None'),
    _m('        self._factory = factory', '        pass  # mutated', 'L46: statement removed'),
    _m('        self.min_size = min_size', '        pass  # mutated', 'L47: statement removed'),
    _m('        self.max_size = max_size', '        pass  # mutated', 'L48: statement removed'),
    _m('        self.acquire_timeout = acquire_timeout', '        pass  # mutated', 'L49: statement removed'),
    _m('        self.idle_timeout = idle_timeout', '        pass  # mutated', 'L50: statement removed'),
    _m('        self._validate = validate_fn or (lambda c: c.is_healthy)', '        pass  # mutated', 'L51: statement removed'),
    _m('        self._lock = threading.Lock()', '        pass  # mutated', 'L55: statement removed'),
    _m('        self._not_empty = threading.Condition(self._lock)', '        pass  # mutated', 'L56: statement removed'),
    _m('        deadline = time.time() + self.acquire_timeout', '        pass  # mutated', 'L65: statement removed'),
    _m('        now = time.time()', '        pass  # mutated', 'L101: statement removed'),
    _m('        evicted = 0', '        pass  # mutated', 'L102: statement removed'),
    _m('        self._pool = pool', '        pass  # mutated', 'L144: statement removed'),
    _m('        self._conn = self._pool.acquire()', '        pass  # mutated', 'L148: statement removed'),
    _m('        return self._conn', '        return None', 'L149: return -> None'),
    _m('            self._active.discard(conn)', '            pass  # mutated', 'L93: statement removed'),
    _m('            to_keep = []', '            pass  # mutated', 'L104: statement removed'),
    _m('            return len(self._idle)', '            return None', 'L129: return -> None'),
    _m('            return len(self._active)', '            return None', 'L134: return -> None'),
    _m('            self._pool.release(self._conn)', '            pass  # mutated', 'L153: statement removed'),
    _m('                remaining = deadline - time.time()', '                pass  # mutated', 'L85: statement removed'),
    _m('                self._idle.append(conn)', '                pass  # mutated', 'L95: statement removed'),
    _m('                age = now - conn.last_used_at', '                pass  # mutated', 'L106: statement removed'),
    _m('                    conn = self._idle.pop()', '                    pass  # mutated', 'L70: statement removed'),
    _m('                    conn = self._factory()', '                    pass  # mutated', 'L79: statement removed'),
    _m('                    self._total += 1', '                    pass  # mutated', 'L80: statement removed'),
    _m('                        self._active.add(conn)', '                        pass  # mutated', 'L72: statement removed'),
    _m('                        return conn', '                        return None', 'L73: return -> None'),
    _m('        self._healthy: bool = True', '        self._healthy: bool = False', 'L17: True -> False')
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
        _grade(content, "mut08-base-")
    except Exception as e:
        print(f"mutate_08: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut08-{i}-")
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
