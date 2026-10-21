"""mutate_12 — leaderboard: 30 anchored mutations, each caught by check_12.

Every mutation replaces one exact, once-occurring line of
`solutions/leaderboard.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_12()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/leaderboard.py`. If a line ever loses its uniqueness or its
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

MODULE = "leaderboard.py"
STAGE = 12
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        new_entry = (-score, member)', '        pass  # mutated', 'L34: statement removed'),
    _m('        bisect.insort(self._sorted, new_entry)', '        pass  # mutated', 'L35: statement removed'),
    _m('        self._scores[member] = score', '        pass  # mutated', 'L36: statement removed'),
    _m('        new_score = self._scores.get(member, 0.0) + delta', '        pass  # mutated', 'L39: statement removed'),
    _m('        self.zadd(member, new_score)', '        pass  # mutated', 'L40: statement removed'),
    _m('        return new_score', '        return None', 'L41: return -> None'),
    _m('        return self._scores.get(member)', '        return None', 'L44: return -> None'),
    _m('        score = self._scores[member]', '        pass  # mutated', 'L49: statement removed'),
    _m('        entry = (-score, member)', '        pass  # mutated', 'L50: statement removed'),
    _m('        idx = bisect.bisect_left(self._sorted, entry)', '        pass  # mutated', 'L51: statement removed'),
    _m('        slice_ = self._sorted[start:stop + 1]', '        pass  # mutated', 'L57: statement removed'),
    _m('        return [(member, -neg_score) for neg_score, member in slice_]', '        return None', 'L58: return -> None'),
    _m('        return len(self._scores)', '        return None', 'L70: return -> None'),
    _m('        self._set = SortedSet()', '        pass  # mutated', 'L76: statement removed'),
    _m('        self._set.zadd(member, score)', '        pass  # mutated', 'L80: statement removed'),
    _m('        return self._set.zincrby(member, delta)', '        return None', 'L83: return -> None'),
    _m('        rank = self._set.zrevrank(member)', '        pass  # mutated', 'L86: statement removed'),
    _m('        return rank + 1 if rank is not None else None', '        return None', 'L87: return -> None'),
    _m('        entries = self._set.zrevrange(0, n - 1)', '        pass  # mutated', 'L93: statement removed'),
    _m('        rank0 = self._set.zrevrank(member)', '        pass  # mutated', 'L106: statement removed'),
    _m('        start = max(0, rank0 - n // 2)', '        pass  # mutated', 'L109: statement removed'),
    _m('        stop = start + n - 1', '        pass  # mutated', 'L110: statement removed'),
    _m('        total = self._set.zcard()', '        pass  # mutated', 'L111: statement removed'),
    _m('        entries = self._set.zrevrange(start, stop)', '        pass  # mutated', 'L115: statement removed'),
    _m('            old_score = self._scores[member]', '            pass  # mutated', 'L29: statement removed'),
    _m('            old_entry = (-old_score, member)', '            pass  # mutated', 'L30: statement removed'),
    _m('            idx = bisect.bisect_left(self._sorted, old_entry)', '            pass  # mutated', 'L31: statement removed'),
    _m('            return idx', '            return None', 'L53: return -> None'),
    _m('            rank = i + 1', '            pass  # mutated', 'L96: statement removed'),
    _m('            rank = start + i + 1', '            pass  # mutated', 'L118: statement removed')
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
        _grade(content, "mut12-base-")
    except Exception as e:
        print(f"mutate_12: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut12-{i}-")
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
