#!/usr/bin/env python3
"""Mutation testing for collections-workout-from-scratch course.

Uses function-level mutations via string replacement on the solution files.
"""
import os
import shutil
import sys
import subprocess
import ast

COURSE_DIR = "/home/diego/Desarrollo/learn-stuff-from-scratch/collections-workout-from-scratch"
REPO_DIR = "/home/diego/Desarrollo/learn-stuff-from-scratch"
TMP_DIR = "/tmp/opencode/verify_cws"
SOL_DIR = os.path.join(COURSE_DIR, "solutions")

_CHECK_RUNNER = r'''import os
import sys
import importlib.util

check_num = int(os.environ.get('CWS_CHECK_NUM', 1))
course_dir = os.getcwd()

stage_name = f"stage_{check_num:02d}"
stage_file = os.path.join(course_dir, f'{stage_name}.py')
if os.path.exists(stage_file):
    spec = importlib.util.spec_from_file_location(stage_name, stage_file)
    stage_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage_mod)
    sys.modules[stage_name] = stage_mod

import collections as _stdlib_col
if 'collections' in sys.modules:
    del sys.modules['collections']
for key in list(sys.modules.keys()):
    if key.startswith('collections.'):
        del sys.modules[key]

sys.path = [p for p in sys.path if p and 'collections-workout' not in p]
if course_dir not in sys.path:
    sys.path.insert(0, course_dir)

import course
import collections as col_mod
for name in dir(_stdlib_col):
    if name.startswith('_'):
        continue
    try:
        val = getattr(_stdlib_col, name)
        if not hasattr(col_mod, name):
            setattr(col_mod, name, val)
    except:
        pass

CHECKS = [course.check_1, course.check_2, course.check_3, course.check_4,
          course.check_5, course.check_6, course.check_7, course.check_8,
          course.check_9, course.check_10]
fn = CHECKS[check_num - 1]

try:
    fn()
    print(f"  check_{check_num}: PASS")
    print(f"CHECK_RESULT:PASS")
except NotImplementedError:
    print(f"  check_{check_num}: RAISES NotImplementedError")
    print(f"CHECK_RESULT:RAISES")
except Exception as e:
    msg = str(e)
    if len(msg) > 200:
        msg = msg[:200]
    print(f"  check_{check_num}: FAIL - {type(e).__name__}: {msg}")
    print(f"CHECK_RESULT:FAIL:{type(e).__name__}")
    raise
'''


def clean():
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)


def copytree_nocache(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=lambda d, f: ["__pycache__", "*.pyc"])


# Mutations: (stage_num, name, before_replacement, replacement_text)
# Each mutation replaces ALL content between the function def line and the
# next function/class boundary (or end of file) with the replacement.
# The replacement must be valid Python that the function body would return.
MUTATIONS = [
    # Stage 1: dpd, state
    (1, "dpd returns zero", "return 0"),
    (1, "dpd returns one", "return 1"),
    (1, "dpd off by one", "return dates.days_between(ref, day) + 1"),
    
    # Stage 2: due_actions
    (2, "due_actions returns empty", "return ()"),
    (2, "due_actions returns wrong state", "return \"wrong\""),
    
    # Stage 3: replay, vault
    (3, "replay returns empty", "return ()"),
    (3, "vault returns gaps", "return (1, 2)"),
    
    # Stage 4: eligible, terms
    (4, "eligible returns False", "return (False, [])"),
    (4, "terms wrong probation", "return {\"probation_months\": 1}"),
    (4, "eligible returns empty tuple", "return ()"),
    
    # Stage 6: apply, ledger
    (6, "apply returns zero cash", "return {\"cash_cents\": 0, \"applied\": (), \"balance\": (), \"carried_cents\": 0}"),
    (6, "apply returns empty", "return ()"),
    
    # Stage 7: sale
    (7, "sale returns zero deficiency", "return {\"deficiency_cents\": 0}"),
    (7, "sale returns empty dict", "return {}"),
    
    # Stage 8: deficiency, writeoff
    (8, "deficiency returns zero", "return {\"deficiency_cents\": 0}"),
    (8, "writeoff returns None", "return None"),
    (8, "deficiency returns empty dict", "return {}"),
    
    # Stage 9: lgd, flows
    (9, "lgd returns zero", "return {\"realised_lgd_bp\": 0}"),
    (9, "flows returns empty", "return ()"),
    (9, "lgd returns empty dict", "return {}"),
    
    # Stage 10: story, audit
    (10, "story returns empty", "return ()"),
    (10, "audit returns empty dict", "return {}"),
    (10, "story returns dict", "return {}"),
]


def apply_mutations(content, stage_num, name, replacement_text):
    """Apply mutation by replacing the function body in the content."""
    try:
        tree = ast.parse(content)
    except:
        return content

    lines = content.split('\n')

    # Map mutation name to function name
    func_name_map = {
        "dpd returns zero": "dpd",
        "dpd returns one": "dpd",
        "dpd off by one": "dpd",
        "due_actions returns empty": "due_actions",
        "due_actions returns wrong state": "due_actions",
        "replay returns empty": "replay",
        "vault returns gaps": "vault",
        "eligible returns False": "eligible",
        "terms wrong probation": "terms",
        "eligible returns empty tuple": "eligible",
        "apply returns zero cash": "apply",
        "apply returns empty": "apply",
        "sale returns zero deficiency": "sale",
        "sale returns empty dict": "sale",
        "deficiency returns zero": "deficiency",
        "deficiency returns empty dict": "deficiency",
        "writeoff returns None": "writeoff",
        "lgd returns zero": "lgd_against",
        "lgd returns empty dict": "lgd_against",
        "flows returns empty": "flows",
        "story returns empty": "story",
        "audit returns empty dict": "audit",
        "story returns dict": "story",
    }
    func_name = func_name_map.get(name, name)

    # Find the function in AST
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            func_node = node
            break

    if not func_node:
        return content  # Function not found, return unchanged

    # Get line range (0-based)
    start_idx = func_node.lineno - 1  # 0-based index of def line
    end_idx_exclusive = func_node.end_lineno  # 0-based exclusive end

    # Use AST to find the body: the function node has a body list
    # which are the AST nodes in the function body (not including docstring)
    # Actually, ast.FunctionDef.body includes the docstring as first stmt
    # if the first thing is a string literal. We need to skip it.
    
    # Get body start from AST - skip the docstring (first stmt if it's an Expr with constant value)
    body_start_idx = start_idx  # Default: start from def line
    if func_node.body:
        first_stmt = func_node.body[0]
        # If first stmt is a docstring, skip it
        if (isinstance(first_stmt, ast.Expr) and 
            isinstance(first_stmt.value, ast.Constant) and
            isinstance(first_stmt.value.value, str)):
            # Docstring ends at first_stmt.end_lineno (1-based)
            doc_end_idx = first_stmt.end_lineno - 1  # 0-based
            body_start_idx = doc_end_idx + 1 if doc_end_idx + 1 < end_idx_exclusive else start_idx + 1

    # Fallback: find first non-docstring line
    if body_start_idx == start_idx:
        for i in range(start_idx + 1, min(end_idx_exclusive, len(lines))):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
                # Check if this line is part of a multi-line docstring
                # If we haven't seen closing """, skip it
                pass
                body_start_idx = i
                break

    # Get body indentation
    func_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    body_indent = ' ' * (func_indent + 4)

    # Apply replacement
    new_lines = list(lines)
    for i in range(body_start_idx, end_idx_exclusive):
        if i == body_start_idx:
            new_lines[i] = body_indent + replacement_text
        else:
            new_lines[i] = ''

    return '\n'.join(new_lines)


def run_mutation_test():
    print("=" * 60)
    print("MUTATION TESTING")
    print("=" * 60)
    print()

    total = len(MUTATIONS)
    killed = 0
    missed = 0
    skipped = 0

    for idx, (stage_num, name, replacement_text) in enumerate(MUTATIONS, 1):
        print(f"[{idx}/{total}] {name} (stage {stage_num})...", end=" ", flush=True)

        clean()
        verify_dir = os.path.join(TMP_DIR, f"mut_{idx}")
        copytree_nocache(COURSE_DIR, verify_dir)

        sol_file = os.path.join(SOL_DIR, f'stage_{stage_num:02d}.py')
        if not os.path.exists(sol_file):
            print("SKIP (no solution)")
            skipped += 1
            continue

        with open(sol_file) as f:
            content = f.read()

        mutated = apply_mutations(content, stage_num, name, replacement_text)

        if mutated == content:
            print("SKIP (no change)")
            skipped += 1
            continue

        # Write mutated file as the stage file
        mut_file = os.path.join(verify_dir, f'stage_{stage_num:02d}.py')
        with open(mut_file, 'w') as f:
            f.write(mutated)

        # Write check runner
        runner_file = os.path.join(verify_dir, "check_runner.py")
        with open(runner_file, 'w') as f:
            f.write(_CHECK_RUNNER)

        env = os.environ.copy()
        env["PYTHONPATH"] = REPO_DIR

        results = {}
        for i in range(1, 11):
            result = subprocess.run(
                [sys.executable, runner_file],
                cwd=verify_dir,
                env={**env, "CWS_CHECK_NUM": str(i)},
                capture_output=True,
                text=True,
                timeout=60,
            )
            for line in result.stdout.split('\n'):
                if line.startswith("CHECK_RESULT:"):
                    rtype = line.split(':', 1)[1]
                    # Handle both "FAIL:AssertionError" and just "FAIL"
                    results[i] = rtype.split(':')[0] if ':' in rtype else rtype
                    break

        killed_check = None
        for i, status in results.items():
            if status == "FAIL":
                killed_check = i
                break

        if killed_check:
            print(f"KILLED (check {killed_check})")
            killed += 1
        else:
            print(f"MISSED")
            missed += 1

    print()
    print(f"Results: {killed}/{total} killed, {missed}/{total} missed")
    print("=" * 60)
    return killed == total


if __name__ == "__main__":
    missed = 0  # Define for the finally clause
    ok = run_mutation_test()
    if ok:
        print("ALL MUTATIONS KILLED - 0 MISSED")
    else:
        print(f"WARNING: {missed} mutations NOT killed")
    sys.exit(0 if ok else 1)