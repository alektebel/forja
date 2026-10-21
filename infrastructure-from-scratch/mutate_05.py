"""mutate_05 — rate_limiter: 29 anchored mutations, each caught by check_05.

Every mutation replaces one exact, once-occurring line of
`solutions/rate_limiter.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_5()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/rate_limiter.py`. If a line ever loses its uniqueness or its
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

MODULE = "rate_limiter.py"
STAGE = 5
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.capacity = capacity', '        pass  # mutated', 'L34: statement removed'),
    _m('        self.refill_rate = refill_rate', '        pass  # mutated', 'L35: statement removed'),
    _m('            window_id, count = self._windows.get(key, (-1, 0))', '            pass  # mutated', 'L23: statement removed'),
    _m('            self._windows[key] = (current_window, count + 1)', '            pass  # mutated', 'L28: statement removed'),
    _m('            tokens, last_refill = self._buckets.get(key, (float(self.capacity), now))', '            pass  # mutated', 'L42: statement removed'),
    _m('            elapsed = now - last_refill', '            pass  # mutated', 'L43: statement removed'),
    _m('            tokens = min(self.capacity, tokens + elapsed * self.refill_rate)', '            pass  # mutated', 'L44: statement removed'),
    _m('            self._buckets[key] = (tokens - 1.0, now)', '            pass  # mutated', 'L48: statement removed'),
    _m('            cutoff = now - self.window_seconds', '            pass  # mutated', 'L62: statement removed'),
    _m('            log = self._logs.setdefault(key, deque())', '            pass  # mutated', 'L63: statement removed'),
    _m('            log.append(now)', '            pass  # mutated', 'L68: statement removed'),
    _m('            elapsed_in_window = now % self.window_seconds', '            pass  # mutated', 'L83: statement removed'),
    _m('            overlap = 1.0 - (elapsed_in_window / self.window_seconds)', '            pass  # mutated', 'L84: statement removed'),
    _m('            stored_window, curr_count, prev_count = self._windows.get(key, (current_window, 0, 0))', '            pass  # mutated', 'L86: statement removed'),
    _m('            estimated = prev_count * overlap + curr_count', '            pass  # mutated', 'L96: statement removed'),
    _m('            self._windows[key] = (stored_window, curr_count + 1, prev_count)', '            pass  # mutated', 'L100: statement removed'),
    _m('            if window_id != current_window:', '            if window_id == current_window:', 'L24: != -> =='),
    _m('            if count >= self.limit:', '            if count > self.limit:', 'L26: >= -> >'),
    _m('            tokens = min(self.capacity, tokens + elapsed * self.refill_rate)', '            tokens = max(self.capacity, tokens + elapsed * self.refill_rate)', 'L44: min -> max'),
    _m('            if len(log) >= self.limit:', '            if len(log) > self.limit:', 'L66: >= -> >'),
    _m('            if stored_window != current_window:', '            if stored_window == current_window:', 'L88: != -> =='),
    _m('            if estimated >= self.limit:', '            if estimated > self.limit:', 'L97: >= -> >'),
    _m('                count = 0', '                count = 1', 'L25: 0 -> 1'),
    _m('            if tokens < 1.0:', '            if tokens < 2.0:', 'L45: 1.0 -> 2.0'),
    _m('            self._windows[key] = (current_window, count + 1)', '            self._windows[key] = (current_window, count + 2)', 'L28: 1 -> 2'),
    _m('            self._buckets[key] = (tokens - 1.0, now)', '            self._buckets[key] = (tokens - 2.0, now)', 'L48: 1.0 -> 2.0'),
    _m('            stored_window, curr_count, prev_count = self._windows.get(key, (current_window, 0, 0))', '            stored_window, curr_count, prev_count = self._windows.get(key, (current_window, 1, 0))', 'L86: 0 -> 1'),
    _m('            self._windows[key] = (stored_window, curr_count + 1, prev_count)', '            self._windows[key] = (stored_window, curr_count + 2, prev_count)', 'L100: 1 -> 2'),
    _m('            while log and log[0] <= cutoff:', '            while log and log[1] <= cutoff:', 'L64: 0 -> 1')
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
        _grade(content, "mut05-base-")
    except Exception as e:
        print(f"mutate_05: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut05-{i}-")
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
