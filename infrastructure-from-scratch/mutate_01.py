"""mutate_01 — url_shortener: 30 anchored mutations, each caught by check_01.

Every mutation replaces one exact, once-occurring line of
`solutions/url_shortener.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_1()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/url_shortener.py`. If a line ever loses its uniqueness or its
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

MODULE = "url_shortener.py"
STAGE = 1
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase', 'pass  # mutated', 'L9: statement removed'),
    _m('    result = []', '    pass  # mutated', 'L15: statement removed'),
    _m('    return "".join(reversed(result))', '    return None', 'L19: return -> None'),
    _m('    idx = {c: i for i, c in enumerate(BASE62_ALPHABET)}', '    pass  # mutated', 'L23: statement removed'),
    _m('    result = 0', '    pass  # mutated', 'L24: statement removed'),
    _m('    return result', '    return None', 'L27: return -> None'),
    _m('        return BASE62_ALPHABET[0]', '        return None', 'L14: return -> None'),
    _m('        result.append(BASE62_ALPHABET[num % 62])', '        pass  # mutated', 'L17: statement removed'),
    _m('        result = result * 62 + idx[c]', '        pass  # mutated', 'L26: statement removed'),
    _m('        now = time.time()', '        pass  # mutated', 'L35: statement removed'),
    _m('        entry = self._data.get(code)', '        pass  # mutated', 'L44: statement removed'),
    _m('        return entry["long_url"]', '        return None', 'L50: return -> None'),
    _m('        return self._data.get(code)', '        return None', 'L57: return -> None'),
    _m('        self.base_url = base_url', '        pass  # mutated', 'L62: statement removed'),
    _m('        self._counter = 1000', '        pass  # mutated', 'L63: statement removed'),
    _m('        self._store = URLStore()', '        pass  # mutated', 'L64: statement removed'),
    _m('        self._cache_max = 1000', '        pass  # mutated', 'L67: statement removed'),
    _m('        self._store.save(code, long_url, ttl_seconds)', '        pass  # mutated', 'L78: statement removed'),
    _m('        return f"{self.base_url}/{code}"', '        return None', 'L79: return -> None'),
    _m('        long_url = self._store.get(code)', '        pass  # mutated', 'L85: statement removed'),
    _m('        return long_url', '        return None', 'L92: return -> None'),
    _m('            self._data[code]["hits"] += 1', '            pass  # mutated', 'L54: statement removed'),
    _m('            code = base62_encode(self._counter)', '            pass  # mutated', 'L77: statement removed'),
    _m('    if num == 0:', '    if num != 0:', 'L13: == -> !='),
    _m('    result = 0', '    result = 1', 'L24: 0 -> 1'),
    _m('    if num == 0:', '    if num == 1:', 'L13: 0 -> 1'),
    _m('            self._data[code]["hits"] += 1', '            self._data[code]["hits"] -= 1', 'L54: aug-assign flipped'),
    _m('        return BASE62_ALPHABET[0]', '        return BASE62_ALPHABET[1]', 'L14: 0 -> 1'),
    _m('            "hits": 0,', '            "hits": 1,', 'L40: 0 -> 1'),
    _m('            self._data[code]["hits"] += 1', '            self._data[code]["hits"] += 2', 'L54: 1 -> 2')
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
        _grade(content, "mut01-base-")
    except Exception as e:
        print(f"mutate_01: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut01-{i}-")
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
