"""mutate_17 — edge_computing: 30 anchored mutations, each caught by check_17.

Every mutation replaces one exact, once-occurring line of
`solutions/edge_computing.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_17()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/edge_computing.py`. If a line ever loses its uniqueness or its
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

MODULE = "edge_computing.py"
STAGE = 17
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.node_id = node_id', '        pass  # mutated', 'L13: statement removed'),
    _m('        self.healthy = True', '        pass  # mutated', 'L16: statement removed'),
    _m('        self._nodes[node.node_id] = node', '        pass  # mutated', 'L24: statement removed'),
    _m('        healthy = [n for n in self._nodes.values() if n.healthy]', '        pass  # mutated', 'L27: statement removed'),
    _m('        return min(healthy, key=lambda n: client_latencies.get(n.node_id, float("inf")))', '        return None', 'L30: return -> None'),
    _m('        self._nodes[node_id].healthy = False', '        pass  # mutated', 'L33: statement removed'),
    _m('        self.status = status', '        pass  # mutated', 'L56: statement removed'),
    _m('        self._middlewares = []', '        pass  # mutated', 'L63: statement removed'),
    _m('        self._middlewares.append(middleware)', '        pass  # mutated', 'L66: statement removed'),
    _m('        chain = final_handler', '        pass  # mutated', 'L69: statement removed'),
    _m('        return chain(request)', '        return None', 'L77: return -> None'),
    _m('        self._experiments[name] = (variants, weights)', '        pass  # mutated', 'L87: statement removed'),
    _m('        variants, weights = self._experiments[experiment_name]', '        pass  # mutated', 'L90: statement removed'),
    _m('        bucket = int(hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest(), 16) % 100', '        pass  # mutated', 'L91: statement removed'),
    _m('        cumulative = 0.0', '        pass  # mutated', 'L92: statement removed'),
    _m('        self.cpu_limit_ms = cpu_limit_ms', '        pass  # mutated', 'L106: statement removed'),
    _m('        self._functions[name] = fn', '        pass  # mutated', 'L110: statement removed'),
    _m('        fn = self._functions[name]', '        pass  # mutated', 'L113: statement removed'),
    _m('        result = [None]', '        pass  # mutated', 'L114: statement removed'),
    _m('        exc = [None]', '        pass  # mutated', 'L115: statement removed'),
    _m('        t = threading.Thread(target=target, daemon=True)', '        pass  # mutated', 'L123: statement removed'),
    _m('        t.start()', '        pass  # mutated', 'L124: statement removed'),
    _m('        return result[0]', '        return None', 'L130: return -> None'),
    _m('            next_handler = chain', '            pass  # mutated', 'L71: statement removed'),
    _m('            chain = make_chain(mw, next_handler)', '            pass  # mutated', 'L76: statement removed'),
    _m('            cumulative += weight * 100', '            pass  # mutated', 'L94: statement removed'),
    _m('            raise EdgeFunctionError(f"{name}: exceeded CPU limit")', '            pass  # mutated', 'L127: statement removed'),
    _m('                return chained', '                return None', 'L75: return -> None'),
    _m('                return variant', '                return None', 'L96: return -> None'),
    _m('                result[0] = fn(request)', '                pass  # mutated', 'L119: statement removed')
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
        _grade(content, "mut17-base-")
    except Exception as e:
        print(f"mutate_17: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut17-{i}-")
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
