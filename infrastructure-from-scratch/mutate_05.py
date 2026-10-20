"""mutate_05 — API Gateway: generic mutator using _test().

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
    solution_path = os.path.join(HERE, "solutions", "request_batching.py")
    if not os.path.exists(solution_path):
        solution_path = os.path.join(HERE, "request_batching.py")
    with open(solution_path) as f:
        content = f.read()

    mutations = [
        _m('= []', '= [None]  # broken', 'broken list'),
        _m('= {}', "= {'broken': True}", 'broken dict'),
        _m('.append(', '.append(None)  # broken', 'broken append'),
        _m('+= 1', 'pass  # no increment', 'no increment'),
        _m('self._lock', 'None  # no lock', 'no lock'),
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
        tmpdir = tempfile.mkdtemp(prefix=f"m05-" + str(i) + "-")
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