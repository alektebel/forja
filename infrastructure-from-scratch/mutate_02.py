"""mutate_02 — consistent_hash: 26 anchored mutations, each caught by check_02.

Every mutation replaces one exact, once-occurring line of
`solutions/consistent_hash.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_2()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/consistent_hash.py`. If a line ever loses its uniqueness or its
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

MODULE = "consistent_hash.py"
STAGE = 2
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)', '    return None', 'L11: return -> None'),
    _m('        self.virtual_nodes = virtual_nodes', '        pass  # mutated', 'L16: statement removed'),
    _m('        self._ring = [(pos, n) for pos, n in self._ring if n != node]', '        pass  # mutated', 'L27: statement removed'),
    _m('        self._nodes.discard(node)', '        pass  # mutated', 'L28: statement removed'),
    _m('        pos = _hash(key)', '        pass  # mutated', 'L33: statement removed'),
    _m('        positions = [p for p, _ in self._ring]', '        pass  # mutated', 'L34: statement removed'),
    _m('        idx = bisect.bisect_left(positions, pos)', '        pass  # mutated', 'L35: statement removed'),
    _m('        return self._ring[idx][1]', '        return None', 'L38: return -> None'),
    _m('        return set(self._nodes)', '        return None', 'L42: return -> None'),
    _m('        return counts', '        return None', 'L50: return -> None'),
    _m('        count = 0', '        pass  # mutated', 'L53: statement removed'),
    _m('        self._nodes.append(node)', '        pass  # mutated', 'L65: statement removed'),
    _m('        return max(self._nodes, key=lambda n: _hash(f"{n}:{key}"))', '        return None', 'L73: return -> None'),
    _m('            pos = _hash(f"{node}#vnode{i}")', '            pass  # mutated', 'L22: statement removed'),
    _m('            bisect.insort(self._ring, (pos, node))', '            pass  # mutated', 'L23: statement removed'),
    _m('            idx = 0', '            pass  # mutated', 'L37: statement removed'),
    _m('            node = self.get_node(f"key:{i}")', '            pass  # mutated', 'L47: statement removed'),
    _m('                counts[node] = counts.get(node, 0) + 1', '                pass  # mutated', 'L49: statement removed'),
    _m('                count += 1', '                pass  # mutated', 'L56: statement removed'),
    _m('        if idx == len(self._ring):', '        if idx != len(self._ring):', 'L36: == -> !='),
    _m('        return self._ring[idx][1]', '        return self._ring[idx][2]', 'L38: 1 -> 2'),
    _m('            if self.get_node(key) != old_ring.get_node(key):', '            if self.get_node(key) == old_ring.get_node(key):', 'L55: != -> =='),
    _m('                count += 1', '                count -= 1', 'L56: aug-assign flipped'),
    _m('        self._ring = [(pos, n) for pos, n in self._ring if n != node]', '        self._ring = [(pos, n) for pos, n in self._ring if n == node]', 'L27: != -> =='),
    _m('                count += 1', '                count += 2', 'L56: 1 -> 2'),
    _m('                counts[node] = counts.get(node, 0) + 1', '                counts[node] = counts.get(node, 0) + 2', 'L49: 1 -> 2')
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
        _grade(content, "mut02-base-")
    except Exception as e:
        print(f"mutate_02: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut02-{i}-")
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
