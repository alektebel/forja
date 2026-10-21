"""mutate_03 — cache: 30 anchored mutations, each caught by check_03.

Every mutation replaces one exact, once-occurring line of
`solutions/cache.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_3()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/cache.py`. If a line ever loses its uniqueness or its
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

MODULE = "cache.py"
STAGE = 3
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.key = key', '        pass  # mutated', 'L12: statement removed'),
    _m('        self.value = value', '        pass  # mutated', 'L13: statement removed'),
    _m('        self._head = _Node()', '        pass  # mutated', 'L22: statement removed'),
    _m('        self._tail = _Node()', '        pass  # mutated', 'L23: statement removed'),
    _m('        self._head.next = self._tail', '        pass  # mutated', 'L24: statement removed'),
    _m('        node.prev = self._head', '        pass  # mutated', 'L28: statement removed'),
    _m('        node.next = self._head.next', '        pass  # mutated', 'L29: statement removed'),
    _m('        self._head.next.prev = node', '        pass  # mutated', 'L30: statement removed'),
    _m('        self._head.next = node', '        pass  # mutated', 'L31: statement removed'),
    _m('        node.next.prev = node.prev', '        pass  # mutated', 'L35: statement removed'),
    _m('        node = self._tail.prev', '        pass  # mutated', 'L42: statement removed'),
    _m('        return node.value', '        return None', 'L51: return -> None'),
    _m('        return len(self._cache)', '        return None', 'L67: return -> None'),
    _m('        self.default_ttl = default_ttl', '        pass  # mutated', 'L73: statement removed'),
    _m('        self._inner = LRUCache(capacity)', '        pass  # mutated', 'L74: statement removed'),
    _m('        result = self._inner.get(key)', '        pass  # mutated', 'L77: statement removed'),
    _m('        value, expires_at = result', '        pass  # mutated', 'L80: statement removed'),
    _m('        effective_ttl = ttl if ttl is not None else self.default_ttl', '        pass  # mutated', 'L87: statement removed'),
    _m('        expires_at = time.time() + effective_ttl if effective_ttl else None', '        pass  # mutated', 'L88: statement removed'),
    _m('        self._inner.put(key, (value, expires_at))', '        pass  # mutated', 'L89: statement removed'),
    _m('        self.cache_hits = 0', '        pass  # mutated', 'L96: statement removed'),
    _m('        self.cache_misses = 0', '        pass  # mutated', 'L97: statement removed'),
    _m('        self.cache_misses += 1', '        pass  # mutated', 'L104: statement removed'),
    _m('        cache = self._cache', '        pass  # mutated', 'L117: statement removed'),
    _m('        total = self.cache_hits + self.cache_misses', '        pass  # mutated', 'L124: statement removed'),
    _m('        return self.cache_hits / total if total > 0 else 0.0', '        return None', 'L125: return -> None'),
    _m('            node = _Node(key, value)', '            pass  # mutated', 'L59: statement removed'),
    _m('            self._cache[key] = node', '            pass  # mutated', 'L60: statement removed'),
    _m('            self._add_to_head(node)', '            pass  # mutated', 'L61: statement removed'),
    _m('            self.cache_hits += 1', '            pass  # mutated', 'L102: statement removed')
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
        _grade(content, "mut03-base-")
    except Exception as e:
        print(f"mutate_03: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut03-{i}-")
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
