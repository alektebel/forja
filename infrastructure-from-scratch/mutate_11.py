"""mutate_11 — message_queue: 18 anchored mutations, each caught by check_11.

Every mutation replaces one exact, once-occurring line of
`solutions/message_queue.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_11()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/message_queue.py`. If a line ever loses its uniqueness or its
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

MODULE = "message_queue.py"
STAGE = 11
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    raw_delay = min(cap, base * (2 ** attempt))', '    pass  # mutated', 'L27: statement removed'),
    _m('    return random.uniform(0, raw_delay) if jitter else raw_delay', '    return None', 'L28: return -> None'),
    _m('        self.visibility_timeout = visibility_timeout', '        pass  # mutated', 'L33: statement removed'),
    _m('        self.dedup_ttl = dedup_ttl', '        pass  # mutated', 'L34: statement removed'),
    _m('        self._lock = threading.Lock()', '        pass  # mutated', 'L40: statement removed'),
    _m('        return len(self._queue)', '        return None', 'L111: return -> None'),
    _m('        return len(self._dlq)', '        return None', 'L115: return -> None'),
    _m('            msg_id = str(uuid.uuid4())', '            pass  # mutated', 'L48: statement removed'),
    _m('                self._idempotency_keys[idempotency_key] = msg_id', '                pass  # mutated', 'L57: statement removed'),
    _m('                delay = exponential_backoff(msg.attempts - 1, jitter=True)', '                pass  # mutated', 'L85: statement removed'),
    _m('                self._queue.append(msg)', '                pass  # mutated', 'L87: statement removed'),
    _m('                self._dlq.append(msg)', '                pass  # mutated', 'L89: statement removed'),
    _m('                    self._queue.pop(i)', '                    pass  # mutated', 'L65: statement removed'),
    _m('                    self._in_flight[msg.id] = (msg, now + self.visibility_timeout)', '                    pass  # mutated', 'L67: statement removed'),
    _m('                    return msg', '                    return None', 'L68: return -> None'),
    _m('    raw_delay = min(cap, base * (2 ** attempt))', '    raw_delay = max(cap, base * (2 ** attempt))', 'L27: min -> max'),
    _m('                delay_seconds: float = 0.0) -> str:', '                delay_seconds: float = 1.0) -> str:', 'L43: 0.0 -> 1.0'),
    _m('    raw_delay = min(cap, base * (2 ** attempt))', '    raw_delay = min(cap, base * (3 ** attempt))', 'L27: 2 -> 3')
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
        _grade(content, "mut11-base-")
    except Exception as e:
        print(f"mutate_11: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut11-{i}-")
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
