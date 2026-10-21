"""mutate_16 — idempotency_keys: 30 anchored mutations, each caught by check_16.

Every mutation replaces one exact, once-occurring line of
`solutions/idempotency_keys.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_16()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/idempotency_keys.py`. If a line ever loses its uniqueness or its
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

MODULE = "idempotency_keys.py"
STAGE = 16
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    PENDING = "PENDING"', '    pass  # mutated', 'L13: statement removed'),
    _m('    COMPLETE = "COMPLETE"', '    pass  # mutated', 'L14: statement removed'),
    _m('    SUCCESS = "SUCCESS"', '    pass  # mutated', 'L109: statement removed'),
    _m('        self.status = IdempotencyStatus.PENDING', '        pass  # mutated', 'L20: statement removed'),
    _m('        self.ttl_seconds = ttl_seconds', '        pass  # mutated', 'L24: statement removed'),
    _m('        self._event = threading.Event()', '        pass  # mutated', 'L25: statement removed'),
    _m('        self.response = response', '        pass  # mutated', 'L28: statement removed'),
    _m('        self.status = IdempotencyStatus.COMPLETE', '        pass  # mutated', 'L29: statement removed'),
    _m('        return self._event.wait(timeout=timeout)', '        return None', 'L34: return -> None'),
    _m('        return time.time() - self.created_at > self.ttl_seconds', '        return None', 'L38: return -> None'),
    _m('        self.default_ttl = default_ttl', '        pass  # mutated', 'L43: statement removed'),
    _m('        return len(expired)', '        return None', 'L73: return -> None'),
    _m('        self._store = store', '        pass  # mutated', 'L83: statement removed'),
    _m('        self.wait_timeout = wait_timeout', '        pass  # mutated', 'L84: statement removed'),
    _m('        record, is_new = self._store.get_or_create(idempotency_key)', '        pass  # mutated', 'L87: statement removed'),
    _m('        self._store = IdempotencyStore(default_ttl=86400.0)', '        pass  # mutated', 'L116: statement removed'),
    _m('        self._handler = IdempotentHandler(self._store)', '        pass  # mutated', 'L117: statement removed'),
    _m('        return self._handler.handle(idempotency_key, self._do_charge, account_id, amount)', '        return None', 'L130: return -> None'),
    _m('            new_record = IdempotencyRecord(key, ttl_seconds=self.default_ttl)', '            pass  # mutated', 'L55: statement removed'),
    _m('            self._store[key] = new_record', '            pass  # mutated', 'L56: statement removed'),
    _m('            return (new_record, True)', '            return None', 'L57: return -> None'),
    _m('            expired = [k for k, r in self._store.items() if r.is_expired]', '            pass  # mutated', 'L70: statement removed'),
    _m('            record.wait(timeout=self.wait_timeout)', '            pass  # mutated', 'L93: statement removed'),
    _m('            result = fn(*args, **kwargs)', '            pass  # mutated', 'L98: statement removed'),
    _m('            return result', '            return None', 'L100: return -> None'),
    _m('            self._accounts[account_id] = self._accounts.get(account_id, 0.0) + amount', '            pass  # mutated', 'L123: statement removed'),
    _m('            return self._accounts.get(account_id, 0.0)', '            return None', 'L127: return -> None'),
    _m('            balance = self._accounts.get(account_id, 0.0)', '            pass  # mutated', 'L134: statement removed'),
    _m('                return record.response', '                return None', 'L91: return -> None'),
    _m('                self._accounts[account_id] = balance - amount', '                pass  # mutated', 'L136: statement removed')
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
        _grade(content, "mut16-base-")
    except Exception as e:
        print(f"mutate_16: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut16-{i}-")
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
