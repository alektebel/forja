"""mutate_NN — Cache Invalidation: generic mutator using _test().

Plants mutations in the solution file. Each mutation is a text replacement
that breaks behavior. Uses the solution's _test() to verify each is caught.
"""
import sys, os, tempfile, shutil, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def _load(p):
    spec = importlib.util.spec_from_file_location("mod", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _is_caught(tmp_path):
    try:
        mod = _load(tmp_path)
        if hasattr(mod, "_test"):
            mod._test()
        return False
    except Exception:
        return True

def _m(t, r, l=""):
    return (t, r, l)

def main():
    solution_path = os.path.join(HERE, "solutions", "capacity_planner.py")
    if not os.path.exists(solution_path):
        solution_path = os.path.join(HERE, "capacity_planner.py")
    with open(solution_path) as f:
        content = f.read()

    mutations = [
        _m('return ', 'return None  # broken', 'return broken'),
        _m('= 0', '= 999  # wrong value', 'wrong value'),
        _m('if ', 'if False:  # broken', 'if broken'),
        _m('for ', 'pass  # no loop', 'loop broken'),
        _m('def human_bytes(n: float) -> str:', 'def _broken_():\n        pass  # broken human_byteshuman_bytes(n: float) -> str:', 'broken human_bytes'),
        _m('def human_num(n: float) -> str:', 'def _broken_():\n        pass  # broken human_numhuman_num(n: float) -> str:', 'broken human_num'),
        _m('class QPSResult:', '# class broken - removed\n', 'removed QPSResult:'),
        _m('def __str__(self) -> str:', 'def _broken_():\n        pass  # broken __str____str__(self) -> str:', 'broken __str__'),
        _m('def compute_qps(dau: int, actions_per_user_per_day: float) -> QPSResult:', 'def _broken_():\n        pass  # broken compute_qpscompute_qps(dau: int, actions_per_user_per_day: float) -> QPSResult:', 'broken compute_qps'),
        _m('class StorageResult:', '# class broken - removed\n', 'removed StorageResult:'),
        _m('def compute_storage(write_qps: float, bytes_per_write: int,', 'def _broken_():\n        pass  # broken compute_storagecompute_storage(write_qps: float, bytes_per_write: int,', 'broken compute_storage'),
        _m('class BandwidthResult:', '# class broken - removed\n', 'removed BandwidthResult:'),
        _m('def compute_bandwidth(read_qps: float, read_payload_bytes: int,', 'def _broken_():\n        pass  # broken compute_bandwidthcompute_bandwidth(read_qps: float, read_payload_bytes: int,', 'broken compute_bandwidth'),
        _m('class CacheImpactResult:', '# class broken - removed\n', 'removed CacheImpactResult:'),
        _m('def cache_impact(total_read_qps: float, cache_hit_ratio: float) -> CacheImpactResult:', 'def _broken_():\n        pass  # broken cache_impactcache_impact(total_read_qps: float, cache_hit_ratio: float) -> CacheImpactResult:', 'broken cache_impact'),
        _m('class ServerEstimate:', '# class broken - removed\n', 'removed ServerEstimate:'),
        _m('def estimate_servers(peak_qps: float, avg_latency_ms: float,', 'def _broken_():\n        pass  # broken estimate_serversestimate_servers(peak_qps: float, avg_latency_ms: float,', 'broken estimate_servers'),
        _m('def capacity_plan(name: str, dau: int, reads_per_user_per_day: float,', 'def _broken_():\n        pass  # broken capacity_plancapacity_plan(name: str, dau: int, reads_per_user_per_day: float,', 'broken capacity_plan'),

    ]

    caught = 0
    missed = 0
    for i, (t, r, l) in enumerate(mutations):
        if t not in content:
            missed += 1
            print(f"  M{i+1:03d}: SKIP  {l}")
            continue
        tmpdir = tempfile.mkdtemp(prefix=f"m{15:02d}-{i}-")
        try:
            mutated = content.replace(t, r, 1)
            tmp = os.path.join(tmpdir, "mod.py")
            with open(tmp, "w") as f:
                f.write(mutated)
            if _is_caught(tmp):
                caught += 1
                print(f"  M{i+1:03d}: CAUGHT  {l}")
            else:
                missed += 1
                print(f"  M{i+1:03d}: MISSED  {l}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nMUTATE: CAUGHT {caught} / {caught+missed}  MISSED {missed}")
