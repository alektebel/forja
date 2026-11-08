"""Dev-only grader: run course.py's check_N against the stage modules in the
CURRENT working directory — the mutation harness's mutated copies.

    G11_COURSE=<course dir> python3 _build/grade.py [step ...]

Prints the standard block (`✓` pass, `·` todo, `✗` fail) and exits non-zero
unless every requested step passed. `_build/` is excluded from exports, so
this never reaches a learner, and course.py never imports it.
"""
import importlib.util
import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))


def _course_dir():
    env = os.environ.get("G11_COURSE")
    if env:
        return os.path.abspath(env)
    probe = HERE
    while True:
        if os.path.exists(os.path.join(probe, "course.py")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            raise SystemExit("set G11_COURSE to the course directory")
        probe = parent


def main(argv):
    work = os.getcwd()
    course = _course_dir()
    os.environ.setdefault("G11_REPO", os.path.dirname(course))
    sys.path.insert(0, work)
    if course not in sys.path:
        sys.path.append(course)
    sys.path.append(os.path.dirname(course))        # codecraft.api
    # Preload every module under test: course.py's own `sys.path.insert(0,
    # HERE)` would otherwise import the pristine course copies instead of the
    # mutated ones the harness planted in `work`.
    import graphs                                    # noqa: F401
    for n in range(1, 11):
        name = "stage_%02d" % n
        if os.path.exists(os.path.join(work, name + ".py")):
            __import__(name)
    spec = importlib.util.spec_from_file_location(
        "g11_course", os.path.join(course, "course.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    wanted = [int(a) for a in argv if a.isdigit()] or list(range(1, 11))
    ok = True
    for step in wanted:
        fn = getattr(module, "check_%d" % step)
        try:
            fn()
        except NotImplementedError:
            print("· %d. stage_%02d.py not implemented yet" % (step, step))
            ok = False
        except AssertionError as err:
            first = (str(err) or "assertion failed").splitlines()[0]
            print("✗ %d. stage_%02d.py %s" % (step, step, first))
            ok = False
        except Exception as err:                     # noqa: BLE001
            print("✗ %d. stage_%02d.py %s: %s"
                  % (step, step, type(err).__name__, err))
            ok = False
        else:
            print("✓ %d. stage_%02d.py" % (step, step))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
