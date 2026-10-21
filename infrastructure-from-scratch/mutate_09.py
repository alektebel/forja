"""mutate_09 — session_stickiness: 30 anchored mutations, each caught by check_09.

Every mutation replaces one exact, once-occurring line of
`solutions/session_stickiness.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_9()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/session_stickiness.py`. If a line ever loses its uniqueness or its
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

MODULE = "session_stickiness.py"
STAGE = 9
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    COOKIE_NAME = "SERVERID"', '    pass  # mutated', 'L59: statement removed'),
    _m('        self.backend_id = backend_id', '        pass  # mutated', 'L14: statement removed'),
    _m('        index = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % len(healthy)', '        pass  # mutated', 'L41: statement removed'),
    _m('        return healthy[index]', '        return None', 'L42: return -> None'),
    _m('        self._router = router', '        pass  # mutated', 'L62: statement removed'),
    _m('        self._backends = router._backends', '        pass  # mutated', 'L63: statement removed'),
    _m('        backend = self._pick_least_loaded()', '        pass  # mutated', 'L75: statement removed'),
    _m('        return (backend, f"{self.COOKIE_NAME}={backend.backend_id}")', '        return None', 'L78: return -> None'),
    _m('        return min(healthy, key=lambda b: b.active_sessions)', '        return None', 'L85: return -> None'),
    _m('        self.ttl = ttl_seconds', '        pass  # mutated', 'L90: statement removed'),
    _m('        session_id = str(uuid.uuid4())', '        pass  # mutated', 'L95: statement removed'),
    _m('        return session_id', '        return None', 'L101: return -> None'),
    _m('            self._backends[backend.backend_id] = backend', '            pass  # mutated', 'L27: statement removed'),
    _m('            self._backends[backend_id].healthy = False', '            pass  # mutated', 'L46: statement removed'),
    _m('            parts = session_cookie.split("=", 1)', '            pass  # mutated', 'L68: statement removed'),
    _m('            healthy = [b for b in self._backends.values() if b.healthy]', '            pass  # mutated', 'L82: statement removed'),
    _m('            entry = self._store.get(session_id)', '            pass  # mutated', 'L105: statement removed'),
    _m('            return entry["data"]', '            return None', 'L111: return -> None'),
    _m('            self._store[session_id]["data"] = data', '            pass  # mutated', 'L117: statement removed'),
    _m('            self._store.pop(session_id, None)', '            pass  # mutated', 'L123: statement removed'),
    _m('                backend_id = parts[1]', '                pass  # mutated', 'L70: statement removed'),
    _m('                backend = self._backends.get(backend_id)', '                pass  # mutated', 'L71: statement removed'),
    _m('                    return (backend, None)', '                    return None', 'L73: return -> None'),
    _m('        self.healthy: bool = True', '        self.healthy: bool = False', 'L16: True -> False'),
    _m('            self._backends[backend_id].healthy = False', '            self._backends[backend_id].healthy = True', 'L46: False -> True'),
    _m('            if len(parts) == 2 and parts[0] == self.COOKIE_NAME:', '            if len(parts) != 2 and parts[0] == self.COOKIE_NAME:', 'L69: == -> !='),
    _m('            if len(parts) == 2 and parts[0] == self.COOKIE_NAME:', '            if len(parts) == 2 and parts[0] != self.COOKIE_NAME:', 'L69: == -> !='),
    _m('            if len(parts) == 2 and parts[0] == self.COOKIE_NAME:', '            if len(parts) == 3 and parts[0] == self.COOKIE_NAME:', 'L69: 2 -> 3'),
    _m('                backend_id = parts[1]', '                backend_id = parts[2]', 'L70: 1 -> 2'),
    _m('            if len(parts) == 2 and parts[0] == self.COOKIE_NAME:', '            if len(parts) == 2 and parts[1] == self.COOKIE_NAME:', 'L69: 0 -> 1')
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
        _grade(content, "mut09-base-")
    except Exception as e:
        print(f"mutate_09: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut09-{i}-")
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
