"""Ejecuta la batería de mutaciones contra los checks reales del curso.

Copia `course.py`, `sasmini.py`, `world.py` y las soluciones a un directorio
temporal, planta una mutación en el `.sas` de la etapa y llama a su `check_N`.
Un check que levanta cualquier excepción cuenta como CAUGHT; un check que
devuelve sin excepción es MISSED. Antes de mutar, comprueba que la solución
sin tocar pasa, para no confundir un error de importación con una detección.

    python3 _build/run_mutations.py
"""

import importlib.util
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
REPO = os.path.dirname(COURSE)


def load_mutations():
    path = os.path.join(HERE, "mutations.py")
    spec = importlib.util.spec_from_file_location("sas_lgd_mutations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MUTATIONS


def prepare(work):
    for name in ("course.py", "sasmini.py", "world.py"):
        shutil.copy(os.path.join(COURSE, name), os.path.join(work, name))
    solutions = os.path.join(COURSE, "solutions")
    for name in os.listdir(solutions):
        if name.endswith(".sas"):
            shutil.copy(os.path.join(solutions, name), os.path.join(work, name))


def load_course(work):
    sys.path.insert(0, work)
    sys.path.insert(0, REPO)
    spec = importlib.util.spec_from_file_location(
        "sas_lgd_course_mut", os.path.join(work, "course.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(module, step):
    try:
        getattr(module, "check_%d" % step)()
    except Exception:                                # noqa: BLE001
        return False
    return True


def main():
    mutations = load_mutations()
    baseline = tempfile.mkdtemp(prefix="sas-lgd-base-")
    try:
        prepare(baseline)
        module = load_course(baseline)
        for step in range(1, 12):
            if not check(module, step):
                sys.exit("baseline: la solución de la etapa %d no pasa" % step)
    finally:
        shutil.rmtree(baseline, ignore_errors=True)
    print("baseline: 11/11 PASS")

    missed = []
    for name, filename, old, new, step in mutations:
        work = tempfile.mkdtemp(prefix="sas-lgd-mut-")
        try:
            prepare(work)
            target = os.path.join(work, filename)
            with open(target, encoding="utf-8") as handle:
                text = handle.read()
            if old not in text:
                sys.exit("mutación %r: no se encontró el texto en %s" % (name, filename))
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text.replace(old, new, 1))
            module = load_course(work)
            caught = not check(module, step)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        print("%s  etapa %2d  %s" % ("CAUGHT" if caught else "MISSED", step, name))
        if not caught:
            missed.append(name)

    print("MISSED: %d/%d" % (len(missed), len(mutations)))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
