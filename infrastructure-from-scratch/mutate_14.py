"""mutate_14 — data_locality: 21 anchored mutations, each caught by check_14.

Every mutation replaces one exact, once-occurring line of
`solutions/data_locality.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_14()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/data_locality.py`. If a line ever loses its uniqueness or its
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

MODULE = "data_locality.py"
STAGE = 14
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.num_shards = num_shards', '        pass  # mutated', 'L13: statement removed'),
    _m('        return int(hashlib.md5(partition_key.encode()).hexdigest(), 16) % self.num_shards', '        return None', 'L17: return -> None'),
    _m('        self._shards[shard_id] = shard', '        pass  # mutated', 'L20: statement removed'),
    _m('        return self._shards[self.get_shard_id(partition_key)]', '        return None', 'L23: return -> None'),
    _m('        shard.setdefault(entity_type, {})[entity_id] = data', '        pass  # mutated', 'L34: statement removed'),
    _m('        return shard.get(entity_type, {}).get(entity_id)', '        return None', 'L38: return -> None'),
    _m('        return list(shard.get(entity_type, {}).values())', '        return None', 'L42: return -> None'),
    _m('        self._user_orders.setdefault(user_id, []).append(order_id)', '        pass  # mutated', 'L60: statement removed'),
    _m('        return self._orders.get(order_id)', '        return None', 'L63: return -> None'),
    _m('        order_ids = self._user_orders.get(user_id, [])', '        pass  # mutated', 'L66: statement removed'),
    _m('        return len(order_ids)', '        return None', 'L70: return -> None'),
    _m('        self._time = _time', '        pass  # mutated', 'L77: statement removed'),
    _m('        shard_id = self._router.get_shard_id(partition_key)', '        pass  # mutated', 'L83: statement removed'),
    _m('        return self._caches[shard_id]', '        return None', 'L84: return -> None'),
    _m('        entry = cache.get(entity_key)', '        pass  # mutated', 'L88: statement removed'),
    _m('        value, expires_at = entry', '        pass  # mutated', 'L91: statement removed'),
    _m('        return value', '        return None', 'L95: return -> None'),
    _m('        cache[entity_key] = (value, self._time.time() + ttl)', '        pass  # mutated', 'L100: statement removed'),
    _m('        cache.pop(entity_key, None)', '        pass  # mutated', 'L104: statement removed'),
    _m('            router.add_shard(shard_id, {})', '            pass  # mutated', 'L30: statement removed'),
    _m('                self._orders[oid]["user_name"] = new_name', '                pass  # mutated', 'L69: statement removed')
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
        _grade(content, "mut14-base-")
    except Exception as e:
        print(f"mutate_14: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut14-{i}-")
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
