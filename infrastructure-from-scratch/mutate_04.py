"""mutate_04 — cdn_caching: 30 anchored mutations, each caught by check_04.

Every mutation replaces one exact, once-occurring line of
`solutions/cdn_caching.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_4()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/cdn_caching.py`. If a line ever loses its uniqueness or its
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

MODULE = "cdn_caching.py"
STAGE = 4
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    parsed = urlparse(url)', '    pass  # mutated', 'L147: statement removed'),
    _m('    params = parse_qs(parsed.query, keep_blank_values=True)', '    pass  # mutated', 'L148: statement removed'),
    _m('    sorted_query = urlencode(sorted(params.items()), doseq=True)', '    pass  # mutated', 'L152: statement removed'),
    _m('    normalized = parsed._replace(query=sorted_query, fragment="").geturl()', '    pass  # mutated', 'L153: statement removed'),
    _m('    return normalized', '    return None', 'L157: return -> None'),
    _m('        self.body = body', '        pass  # mutated', 'L14: statement removed'),
    _m('        self.max_age = max_age', '        pass  # mutated', 'L16: statement removed'),
    _m('        self.surrogate_keys = surrogate_keys', '        pass  # mutated', 'L18: statement removed'),
    _m('        directives = self._parse_cache_control(cache_control)', '        pass  # mutated', 'L40: statement removed'),
    _m('        swr = float(directives.get("stale-while-revalidate", 0))', '        pass  # mutated', 'L54: statement removed'),
    _m('        entry = CacheEntry(body, max_age, surrogate_keys or set(), swr)', '        pass  # mutated', 'L55: statement removed'),
    _m('        return len(to_delete)', '        return None', 'L66: return -> None'),
    _m('        directives = {}', '        pass  # mutated', 'L83: statement removed'),
    _m('        return directives', '        return None', 'L91: return -> None'),
    _m('        self._cache = EdgeCache()', '        pass  # mutated', 'L100: statement removed'),
    _m('        self.origin_requests = 0', '        pass  # mutated', 'L106: statement removed'),
    _m('        return result', '        return None', 'L142: return -> None'),
    _m('        vary_part = "&".join(f"{k}={v}" for k, v in sorted(vary_headers.items()))', '        pass  # mutated', 'L155: statement removed'),
    _m('        normalized = f"{normalized}#{vary_part}"', '        pass  # mutated', 'L156: statement removed'),
    _m('            entry = self._store.get(key)', '            pass  # mutated', 'L29: statement removed'),
    _m('            return False', '            return None', 'L43: return -> None'),
    _m('            self._store[key] = entry', '            pass  # mutated', 'L57: statement removed'),
    _m('            event.wait()', '            pass  # mutated', 'L128: statement removed'),
    _m('            return self._inflight_result.get(key)', '            return None', 'L129: return -> None'),
    _m('            self.origin_requests += 1', '            pass  # mutated', 'L134: statement removed'),
    _m('            params.pop(p, None)', '            pass  # mutated', 'L151: statement removed'),
    _m('            max_age = float(directives["max-age"])', '            pass  # mutated', 'L48: statement removed'),
    _m('                k, v = part.split("=", 1)', '                pass  # mutated', 'L87: statement removed'),
    _m('                directives[part] = True', '                pass  # mutated', 'L90: statement removed'),
    _m('                event = threading.Event()', '                pass  # mutated', 'L123: statement removed')
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
        _grade(content, "mut04-base-")
    except Exception as e:
        print(f"mutate_04: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut04-{i}-")
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
