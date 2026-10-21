"""mutate_13 — hot_partition_mitigation: 24 anchored mutations, each caught by check_13.

Every mutation replaces one exact, once-occurring line of
`solutions/hot_partition_mitigation.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_13()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/hot_partition_mitigation.py`. If a line ever loses its uniqueness or its
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

MODULE = "hot_partition_mitigation.py"
STAGE = 13
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('        self.num_shards = num_shards', '        pass  # mutated', 'L14: statement removed'),
    _m('        shard_id = random.randint(0, self.num_shards - 1)', '        pass  # mutated', 'L17: statement removed'),
    _m('        sharded_key = f"{key}:{shard_id}"', '        pass  # mutated', 'L18: statement removed'),
    _m('        shard_store.setdefault(sharded_key, []).append(value)', '        pass  # mutated', 'L19: statement removed'),
    _m('        return [f"{key}:{i}" for i in range(self.num_shards)]', '        return None', 'L23: return -> None'),
    _m('        self._writer = writer', '        pass  # mutated', 'L28: statement removed'),
    _m('        shard_keys = self._writer.scatter_keys(key)', '        pass  # mutated', 'L32: statement removed'),
    _m('        self.window_seconds = window_seconds', '        pass  # mutated', 'L43: statement removed'),
    _m('        self._lock = threading.Lock()', '        pass  # mutated', 'L45: statement removed'),
    _m('        result = [(k, c) for k, c in counts.items() if c > threshold]', '        pass  # mutated', 'L62: statement removed'),
    _m('        return sorted(result, key=lambda x: x[1], reverse=True)', '        return None', 'L63: return -> None'),
    _m('        self.bucket_size = bucket_size_seconds', '        pass  # mutated', 'L74: statement removed'),
    _m('        bucket_id = int(timestamp // self.bucket_size)', '        pass  # mutated', 'L78: statement removed'),
    _m('        return f"{metric}:{bucket_id}"', '        return None', 'L79: return -> None'),
    _m('        ts = timestamp if timestamp is not None else time.time()', '        pass  # mutated', 'L82: statement removed'),
    _m('        key = self._bucket_key(metric, ts)', '        pass  # mutated', 'L83: statement removed'),
    _m('        self._store[key].append(value)', '        pass  # mutated', 'L84: statement removed'),
    _m('        first_bucket = int(start_ts // self.bucket_size)', '        pass  # mutated', 'L89: statement removed'),
    _m('        last_bucket = int(end_ts // self.bucket_size)', '        pass  # mutated', 'L90: statement removed'),
    _m('            collected.extend(shard_store.get(sk, []))', '            pass  # mutated', 'L35: statement removed'),
    _m('            self._access_log[key].append(now)', '            pass  # mutated', 'L51: statement removed'),
    _m('            collected.extend(self._store.get(f"{metric}:{bid}", []))', '            pass  # mutated', 'L93: statement removed'),
    _m('            return aggregate_fn(collected)', '            return None', 'L95: return -> None'),
    _m('        return sorted(result, key=lambda x: x[1], reverse=True)', '        return sorted(result, key=lambda x: x[2], reverse=True)', 'L63: 1 -> 2')
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
        _grade(content, "mut13-base-")
    except Exception as e:
        print(f"mutate_13: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut13-{i}-")
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
