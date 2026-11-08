"""Mutation-test this course: plant known bugs in copies of the solutions and
require that the stage's own check catches each one.

    python3 _build/run_mutations.py [_build/mutations.py]

Same contract as `.claude/skills/graded-module/scripts/mutate.py`, but the
checker here is course.py's `check_N` (an authored course has no check.py),
run through `_build/grade.py` in a temporary copy holding the mutated
solutions. A mutant is CAUGHT when the step prints `✗`; a hang is caught.
Exit code 1 if any mutation is MISSED — that means the check is too weak.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)


def main(argv):
    path = argv[0] if argv else os.path.join(HERE, "mutations.py")
    spec = importlib.util.spec_from_file_location("mutations", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sol = os.path.join(COURSE, "solutions")
    ok = True
    for name, filename, old, new, step in m.MUTATIONS:
        work = tempfile.mkdtemp(prefix="mutate-")
        try:
            for f in os.listdir(sol):
                if f.endswith(".py"):
                    shutil.copy(os.path.join(sol, f), work)
            target = os.path.join(work, filename)
            text = open(target).read()
            if old not in text:
                sys.exit("mutation %r: text not found in solutions/%s"
                         % (name, filename))
            open(target, "w").write(text.replace(old, new, 1))
            env = dict(os.environ, G11_COURSE=COURSE)
            try:
                r = subprocess.run(
                    [sys.executable, os.path.join(HERE, "grade.py"), str(step)],
                    cwd=work, capture_output=True, text=True, timeout=900,
                    env=env)
                caught = "✗" in r.stdout
            except subprocess.TimeoutExpired:
                caught = True                    # a hang counts as caught
        finally:
            shutil.rmtree(work, ignore_errors=True)
        ok &= caught
        print("%s  step %2s  %s" % ("CAUGHT" if caught else "MISSED",
                                    step, name))
    print("MISSED OR BROKEN: %d" % (0 if ok else 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
