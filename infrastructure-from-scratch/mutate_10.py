"""mutate_10 — circuit_breaker: 30 anchored mutations, each caught by check_10.

Every mutation replaces one exact, once-occurring line of
`solutions/circuit_breaker.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_10()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/circuit_breaker.py`. If a line ever loses its uniqueness or its
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

MODULE = "circuit_breaker.py"
STAGE = 10
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    CLOSED = "CLOSED"', '    pass  # mutated', 'L66: statement removed'),
    _m('    OPEN = "OPEN"', '    pass  # mutated', 'L67: statement removed'),
    _m('    HALF_OPEN = "HALF_OPEN"', '    pass  # mutated', 'L68: statement removed'),
    _m('        self.failure_threshold = failure_threshold', '        pass  # mutated', 'L78: statement removed'),
    _m('        self.recovery_timeout = recovery_timeout', '        pass  # mutated', 'L79: statement removed'),
    _m('        return self._state', '        return None', 'L89: return -> None'),
    _m('        self.max_concurrent = max_concurrent', '        pass  # mutated', 'L134: statement removed'),
    _m('        self.timeout = timeout', '        pass  # mutated', 'L135: statement removed'),
    _m('        sem = self._get_semaphore(key)', '        pass  # mutated', 'L146: statement removed'),
    _m('        acquired = sem.acquire(timeout=self.timeout)', '        pass  # mutated', 'L147: statement removed'),
    _m('        self._queue = queue.Queue(maxsize=capacity)', '        pass  # mutated', 'L159: statement removed'),
    _m('        self.rejected = 0', '        pass  # mutated', 'L161: statement removed'),
    _m('            result = [None]', '            pass  # mutated', 'L23: statement removed'),
    _m('            exc = [None]', '            pass  # mutated', 'L24: statement removed'),
    _m('            t = threading.Thread(target=target, daemon=True)', '            pass  # mutated', 'L32: statement removed'),
    _m('            t.start()', '            pass  # mutated', 'L33: statement removed'),
    _m('            return result[0]', '            return None', 'L39: return -> None'),
    _m('            result = fn(*args, **kwargs)', '            pass  # mutated', 'L100: statement removed'),
    _m('            self._record_success()', '            pass  # mutated', 'L101: statement removed'),
    _m('            self._failure_count += 1', '            pass  # mutated', 'L117: statement removed'),
    _m('            return self._semaphores[key]', '            return None', 'L143: return -> None'),
    _m('            raise RuntimeError(f"Bulkhead full for {key}")', '            pass  # mutated', 'L149: statement removed'),
    _m('            return True', '            return None', 'L170: return -> None'),
    _m('            return self._queue.get(block=block, timeout=timeout)', '            return None', 'L178: return -> None'),
    _m('                raise TimeoutError(f"Function timed out after {seconds}s")', '                pass  # mutated', 'L36: statement removed'),
    _m('            self._record_failure()', '            pass  # mutated', 'L106: statement removed'),
    _m('                self._state = CircuitState.OPEN', '                pass  # mutated', 'L121: statement removed'),
    _m('                self._opened_at = time.time()', '                pass  # mutated', 'L122: statement removed'),
    _m('                self._semaphores[key] = threading.Semaphore(self.max_concurrent)', '                pass  # mutated', 'L142: statement removed'),
    _m('                self._queue.put_nowait(item)', '                pass  # mutated', 'L169: statement removed')
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
        _grade(content, "mut10-base-")
    except Exception as e:
        print(f"mutate_10: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut10-{i}-")
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
