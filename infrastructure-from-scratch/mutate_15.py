"""mutate_15 — eventual_consistency: 30 anchored mutations, each caught by check_15.

Every mutation replaces one exact, once-occurring line of
`solutions/eventual_consistency.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_15()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/eventual_consistency.py`. If a line ever loses its uniqueness or its
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

MODULE = "eventual_consistency.py"
STAGE = 15
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self._counts[self.node_id] = self._counts.get(self.node_id, 0) + 1', '        pass  # mutated', 'L16: statement removed'),
    _m('        return sum(self._counts.values())', '        return None', 'L19: return -> None'),
    _m('        ts = timestamp if timestamp is not None else time.time()', '        pass  # mutated', 'L34: statement removed'),
    _m('        current_ts = self._data.get(key, (None, float("-inf")))[1]', '        pass  # mutated', 'L35: statement removed'),
    _m('        entry = self._data.get(key)', '        pass  # mutated', 'L40: statement removed'),
    _m('        return entry[0] if entry is not None else None', '        return None', 'L41: return -> None'),
    _m('        all_nodes = set(self._clock) | set(other._clock)', '        pass  # mutated', 'L64: statement removed'),
    _m('        return less_or_equal and strictly_less', '        return None', 'L71: return -> None'),
    _m('        return self._store.get(key)', '        return None', 'L91: return -> None'),
    _m('        self._replicas = replicas', '        pass  # mutated', 'L96: statement removed'),
    _m('        self.repair_count = 0', '        pass  # mutated', 'L97: statement removed'),
    _m('        ts = time.time()', '        pass  # mutated', 'L100: statement removed'),
    _m('        responses = []', '        pass  # mutated', 'L105: statement removed'),
    _m('        missing = []', '        pass  # mutated', 'L106: statement removed'),
    _m('        newest = max(responses, key=lambda x: x[2])', '        pass  # mutated', 'L117: statement removed'),
    _m('        newest_ts = newest[2]', '        pass  # mutated', 'L118: statement removed'),
    _m('        newest_val = newest[1]', '        pass  # mutated', 'L119: statement removed'),
    _m('        stale = [r for r, v, ts in responses if ts < newest_ts] + missing', '        pass  # mutated', 'L121: statement removed'),
    _m('        return newest_val', '        return None', 'L125: return -> None'),
    _m('            self._counts[node_id] = max(self._counts.get(node_id, 0), count)', '            pass  # mutated', 'L23: statement removed'),
    _m('            self._data[key] = (value, ts)', '            pass  # mutated', 'L37: statement removed'),
    _m('            self.write(key, value, ts)', '            pass  # mutated', 'L45: statement removed'),
    _m('            self._clock[node] = max(self._clock.get(node, 0), t)', '            pass  # mutated', 'L59: statement removed'),
    _m('            self._store[key] = (value, timestamp)', '            pass  # mutated', 'L88: statement removed'),
    _m('            replica.write(key, value, ts)', '            pass  # mutated', 'L102: statement removed'),
    _m('            entry = replica.read(key)', '            pass  # mutated', 'L108: statement removed'),
    _m('            self._read_repair(key, newest_val, newest_ts, stale)', '            pass  # mutated', 'L123: statement removed'),
    _m('            replica.write(key, value, timestamp)', '            pass  # mutated', 'L130: statement removed'),
    _m('            self.repair_count += 1', '            pass  # mutated', 'L131: statement removed'),
    _m('                responses.append((replica, entry[0], entry[1]))', '                pass  # mutated', 'L110: statement removed')
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
        _grade(content, "mut15-base-")
    except Exception as e:
        print(f"mutate_15: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut15-{i}-")
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
