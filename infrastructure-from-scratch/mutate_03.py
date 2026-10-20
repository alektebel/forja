"""mutate_03 — Object Storage: generic mutator using _test().

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
    solution_path = os.path.join(HERE, "solutions", "cache.py")
    if not os.path.exists(solution_path):
        solution_path = os.path.join(HERE, "cache.py")
    with open(solution_path) as f:
        content = f.read()

    mutations = [
        _m('def _add_to_head(self, node: _Node) -> None:', 'pass  # broken _add_to_head', 'broken _add_to_head'),
        _m('def _remove_node(self, node: _Node) -> None:', 'pass  # broken _remove_node', 'broken _remove_node'),
        _m('def _move_to_head(self, node: _Node) -> None:', 'pass  # broken _move_to_head', 'broken _move_to_head'),
        _m('def _remove_tail(self) -> _Node:', 'return self._tail  # broken return', 'broken _remove_tail'),
        _m('self._cache: Dict[Any, _Node] = {}', "self._cache = {'broken': None}", 'broken cache init'),
        _m('cache.put(4, "d")', 'pass  # broken put', 'broken put'),
        _m('assert cache.get(2) == -1', "cache._cache['broken'] = None", 'broken assertion'),
        _m('assert ttl_cache.get("x") == -1', 'pass  # broken assert', 'broken assert'),
        _m('time.sleep(1.1)', 'time.sleep(0.01)', 'broken sleep'),
        _m('store.cache_misses == 1', 'store.cache_misses = 999', 'broken counter'),
        _m('assert store.cache_hits == 1', 'store.cache_hits = 999', 'broken hits'),
        _m('= {}', "= {'broken': True}", 'broken dict'),
        _m('+= 1', 'pass  # no increment', 'no increment'),
        _m('class ', '# class removed -\n', 'class removed'),
        _m('self.', 'self._broken = True  # attr broken\n        self.', 'attr broken'),
        _m('return self.', 'return None  # broken\n        return self.', 'return null'),
    ]

    caught = 0
    missed = 0
    for i, (t, r, l) in enumerate(mutations):
        if t not in content:
            missed += 1
            print(f"  M{i+1:03d}: SKIP  {l}")
            continue
        tmpdir = tempfile.mkdtemp(prefix=f"m03-" + str(i) + "-")
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

main()