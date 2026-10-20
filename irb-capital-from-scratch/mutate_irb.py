"""IRB and Regulatory Capital — mutation battery (20+ planted bugs, 2+ per stage).

Run from the irb-capital-from-scratch directory:
    python3 mutate_irb.py

Every mutation replaces the exact old_text with new_text in a copy of the
solution, runs check_N from course.py, and expects it to FAIL.

If a check passes (the mutation is MISSED), strengthen the check.
Never drop or weaken a mutation.
"""

import os
import sys
import shutil
import tempfile
import subprocess

MUTATIONS = [
    # Stage 1: PIT vs TTC ---
    (
        "pit: return ttc instead of pit",
        "stage_01",
        'return book.grade(loan, at)',
        'return book.grade(loan, at) if book.grade(loan, at) != "B" else "C"',
        1,
    ),
    (
        "legal: always return True",
        "stage_01",
        'return True',
        'return True  # always allow',
        1,
    ),

    # Stage 2: Quantile grid ---
    (
        "quantile: off-grid PD clamps instead of refusing",
        "stage_02",
        'if row[0] != checked:\n        raise QuantileError',
        'if checked < row[0]:\n        return rows[low - 1][1] if low else row[1]\n    return row[1]',
        2,
    ),
    (
        "grid: add a duplicate row (breaks strict-increasing)",
        "stage_02",
        'return rows',
        'return rows + ((0, -3439),)',  # duplicate first row
        2,
    ),

    # Stage 3: Correlation & maturity ---
    (
        "correlation: use corporate table for retail",
        "stage_03",
        'if asset_class == "corporate":\n        return irb.CORPORATE_CORRELATION_BP[band]\n    return irb.RETAIL_CORRELATION_BP[asset_class]',
        'return irb.CORPORATE_CORRELATION_BP.get(band, irb.RETAIL_CORRELATION_BP[asset_class])',
        3,
    ),
    (
        "maturity_factor: allow m=0 (outside walls)",
        "stage_03",
        'if m_years < M_MIN or m_years > M_MAX:\n        raise WeightError',
        'pass  # skip clamp',
        3,
    ),

    # Stage 4: K requirement ---
    (
        "k_requirement: double the k_bp sum",
        "stage_04",
        '"k_bp": sum(discounted)}',
        '"k_bp": sum(discounted) * 2}',
        4,
    ),
    (
        "k_requirement: use max(pd) instead of first marginal for year 1",
        "stage_04",
        'marginal = series[0]',
        'marginal = series[-1]',
        4,
    ),

    # Stage 5: Downturn LGD ---
    (
        "best_estimate_lgd: multiply answer by 2",
        "stage_05",
        'return min(max(answer, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)',
        'return min(max(answer * 2, rules.LGD_FLOOR_BP), rules.LGD_CAP_BP)',
        5,
    ),
    (
        "downturn_lgd: skip floor clamp",
        "stage_05",
        'return min(max(multiplied, irb.DOWNTURN_FLOOR_BP), irb.DOWNTURN_CAP_BP)',
        'return min(multiplied, irb.DOWNTURN_CAP_BP)',
        5,
    ),
    (
        "downturn_lgd: always use treat treatment (invert refrigerate)",
        "stage_05",
        'if treatment == "refrigerate":\n        return be_bp',
        'if treatment == "treat":\n        return be_bp',
        5,
    ),

    # Stage 6: BE-EAD & CCF ---
    (
        "be_ead: ignore undrawn portion",
        "stage_06",
        'return drawn + undrawn * ccf_bp // BP_SCALE',
        'return drawn',
        6,
    ),
    (
        "ccf: return CCF_CAP instead of estimated",
        "stage_06",
        'return min(max(estimated, CCF_FLOOR_BP), CCF_CAP_BP)',
        'return CCF_CAP_BP',
        6,
    ),

    # Stage 7: Risk weight & RWA ---
    (
        "risk_weight: double the rw_bp",
        "stage_07",
        'rw_bp = k_bp * mf * CAPITAL_SCALING_BP // (BP_SCALE * BP_SCALE)',
        'rw_bp = k_bp * mf * CAPITAL_SCALING_BP * 2 // (BP_SCALE * BP_SCALE)',
        7,
    ),
    (
        "total_rwa: only sum corporate segment loans",
        "stage_07",
        'for loan_id in book.on_book(at):',
        'for loan_id in book.on_book(at):\n        if "corporate" not in str(book.loan(loan_id).get("segment", "")): continue',
        7,
    ),

    # Stage 8: Output floor ---
    (
        "applied: take min instead of max",
        "stage_08",
        'applied_total += max(own, share)',
        'applied_total += min(own, share)',
        8,
    ),
    (
        "phase: return 100 for every year",
        "stage_08",
        'return FLOOR_PHASE_PERCENT[year]',
        'return 100',
        8,
    ),

    # Stage 9: Two books reconciliation ---
    (
        "per_grade: return empty list",
        "stage_09",
        'return tuple(rows)',
        'return tuple()',
        9,
    ),
    (
        "irreconcilable: include ALL grades (remove continue)",
        "stage_09",
        'else:\n            continue\n        named.append({"grade": row["grade"], "reason": reason,\n                      "ifrs9_ids": row["ifrs9_ids"],\n                      "irb_ids": row["irb_ids"],',
        'named.append({"grade": row["grade"], "reason": "all",\n                      "ifrs9_ids": row["ifrs9_ids"],\n                      "irb_ids": row["irb_ids"],',
        9,
    ),

    # Stage 10: Audit pack ---
    (
        "capital_pack: set total_rwa to 0",
        "stage_10",
        'total_rwa = sum(row["rwa_cents"] for row in rows)',
        'total_rwa = 0',
        10,
    ),
    (
        "capital_pack: set capital_cents to 0",
        "stage_10",
        'total_capital = sum(row["capital_cents"] for row in rows)',
        'total_capital = 0',
        10,
    ),
]


def run_check(stage_num, sol_dir):
    """Run check_N from course.py with the given solutions active."""
    code = f'''
import os, sys, importlib
sys.path.insert(0, "{sol_dir}")
os.chdir("{sol_dir}")
for mod_name in list(sys.modules):
    if "stage_0{stage_num}" in mod_name or "course" in mod_name:
        del sys.modules[mod_name]
exec(open("course.py").read())
check_fn = globals().get("check_{stage_num}")
if check_fn:
    check_fn()
print("PASS")
'''
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
            cwd=sol_dir,
        )
        return result.returncode == 0 and "PASS" in result.stdout
    except subprocess.TimeoutExpired:
        return False


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    tmpdir = tempfile.mkdtemp(prefix="irb_mutate_")
    try:
        # Copy course files to tmpdir (recursively)
        for f in os.listdir("."):
            src = os.path.join(".", f)
            dst = os.path.join(tmpdir, f)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        sol_dir = os.path.join(tmpdir, "solutions")
        mutated_count = 0
        killed = 0
        missed = 0
        skipped = 0

        for desc, stage_file, old_text, new_text, stage_num in MUTATIONS:
            sol_file = os.path.join(sol_dir, f"stage_{stage_num:02d}.py")
            if not os.path.exists(sol_file):
                sol_file = os.path.join(sol_dir, f"stage_{stage_num}.py")

            with open(sol_file, "r") as f:
                content = f.read()

            if old_text not in content:
                print(f"SKIP [{desc}]: old_text not found in stage_{stage_num:02d}.py")
                skipped += 1
                continue

            # Apply mutation
            mutated = content.replace(old_text, new_text, 1)
            with open(sol_file, "w") as f:
                f.write(mutated)

            # Run check
            ok = run_check(stage_num, sol_dir)
            if not ok:
                killed += 1
                print(f"✓ KILLED: {desc}")
            else:
                missed += 1
                print(f"✗ MISSED: {desc}")

            # Restore original
            with open(sol_file, "w") as f:
                f.write(content)

            mutated_count += 1

        print(f"\nTotal: {mutated_count} | Killed: {killed} | Missed: {missed} | Skipped: {skipped}")
        if missed > 0:
            print(f"⚠ {missed} mutations MISSED — strengthen the check!")
            sys.exit(1)
        print("✓ All mutations killed.")
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()