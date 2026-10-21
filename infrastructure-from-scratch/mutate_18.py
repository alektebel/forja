"""mutate_18 — capacity_planner: 20 anchored mutations, each caught by check_18.

Every mutation replaces one exact, once-occurring line of
`solutions/capacity_planner.py` with a wrong-behaviour variant. The verifier is the
shipped grader itself: `course.check_18()` (surface + probe + the module's
own `_test()`) run against a copy of the solution with the mutation planted
in `templates/capacity_planner.py`. If a line ever loses its uniqueness or its
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

MODULE = "capacity_planner.py"
STAGE = 18
BUDGET = 12  # seconds per mutant; a hang is a MISSED, not a free pass


def _m(t, r, l):
    return (t, r, l)


MUTATIONS = [
    _m('SECONDS_PER_DAY = 86_400', 'pass  # mutated', 'L9: statement removed'),
    _m('BYTES_PER_KB = 1_024', 'pass  # mutated', 'L11: statement removed'),
    _m('BYTES_PER_MB = 1_024 ** 2', 'pass  # mutated', 'L12: statement removed'),
    _m('BYTES_PER_GB = 1_024 ** 3', 'pass  # mutated', 'L13: statement removed'),
    _m('BYTES_PER_TB = 1_024 ** 4', 'pass  # mutated', 'L14: statement removed'),
    _m('PEAK_MULTIPLIER = 3', 'pass  # mutated', 'L15: statement removed'),
    _m('    daily = dau * actions_per_user_per_day', '    pass  # mutated', 'L48: statement removed'),
    _m('    avg = daily / SECONDS_PER_DAY', '    pass  # mutated', 'L49: statement removed'),
    _m('    return QPSResult(average_qps=avg, peak_qps=avg * PEAK_MULTIPLIER, daily_requests=daily)', '    return None', 'L50: return -> None'),
    _m('    per_day = write_qps * bytes_per_write * SECONDS_PER_DAY * replication_factor', '    pass  # mutated', 'L69: statement removed'),
    _m('    per_year = per_day * 365', '    pass  # mutated', 'L70: statement removed'),
    _m('    return StorageResult(bytes_per_day=per_day, bytes_per_year=per_year, bytes_5_years=per_year * 5)', '    return None', 'L71: return -> None'),
    _m('    db_qps = total_read_qps * (1 - cache_hit_ratio)', '    pass  # mutated', 'L111: statement removed'),
    _m('    cache_qps = total_read_qps * cache_hit_ratio', '    pass  # mutated', 'L112: statement removed'),
    _m('    concurrent = peak_qps * (avg_latency_ms / 1000.0)', '    pass  # mutated', 'L135: statement removed'),
    _m('    servers = math.ceil(concurrent / threads_per_server)', '    pass  # mutated', 'L136: statement removed'),
    _m('    return ServerEstimate(servers_needed=servers, qps_per_server=peak_qps / servers)', '    return None', 'L139: return -> None'),
    _m('            return f"{n / divisor:.1f} {unit}"', '            return None', 'L22: return -> None'),
    _m('BYTES_PER_GB = 1_024 ** 3', 'BYTES_PER_GB = 1_024 ** 4', 'L13: 3 -> 4'),
    _m('    db_qps = total_read_qps * (1 - cache_hit_ratio)', '    db_qps = total_read_qps * (2 - cache_hit_ratio)', 'L111: 1 -> 2')
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
        _grade(content, "mut18-base-")
    except Exception as e:
        print(f"mutate_18: BASELINE BROKEN — check fails on the "
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
            _grade(content.replace(t, r, 1), f"mut18-{i}-")
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
