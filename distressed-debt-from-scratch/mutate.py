"""Mutation battery for distressed-debt-from-scratch.

At least two planted bugs per stage (24+ total). Each mutation is a copy →
patch → run → assert-fail → restore. MISSED = error.
"""
import os
import shutil
import subprocess
import sys
import tempfile

COURSE = "distressed-debt-from-scratch"
REPO_ROOT = os.environ.get("DDFS_REPO", os.path.dirname(os.path.abspath(__file__)))

# Find repo root (look for codecraft/api.py)
def find_repo(root):
    for _ in range(8):
        if os.path.isdir(os.path.join(root, "codecraft")) and \
           os.path.isfile(os.path.join(root, "codecraft", "api.py")):
            return root
        root = os.path.dirname(root)
    return root

REPO_ROOT = find_repo(REPO_ROOT)

COURSE_DIR = os.path.join(REPO_ROOT, COURSE)

def _run_check(check_name, dir_path):
    """Run a single check function in a directory, return (passed, err)."""
    result = subprocess.run(
        [sys.executable, "-c", f"import course; course.{check_name}()"],
        cwd=dir_path, capture_output=True, text=True,
        env={**os.environ, "DDFS_REPO": REPO_ROOT},
    )
    return result.returncode == 0, result.stderr[:2000]


def mutate():
    """Run the mutation battery. Each mutation patches one solution file,
    runs the corresponding check, and expects it to FAIL."""

    checks = {
        1: "check_1",
        2: "check_2",
        3: "check_3",
        4: "check_4",
        5: "check_5",
        6: "check_6",
        7: "check_7",
        8: "check_8",
        9: "check_9",
        10: "check_10",
    }

    MUTATIONS = [
        # Stage 1: waterfall and pay
        (1, "solutions/stage_01.py",
         "take = face if face < remaining else remaining",
         "take = remaining  # BUG: pay more than face"),
        (1, "solutions/stage_01.py",
         "if kind not in market.CLASSES:",
         "pass  # BUG: skip kind validation"),
        (1, "solutions/stage_01.py",
         "previous = market.CLASSES.index(kind)",
         "previous = -1  # BUG: reset previous to break order check"),
        # Stage 2: entry
        (2, "solutions/stage_02.py",
         "cost = face * price_bp // PAR_BP",
         "cost = face * price_bp // (PAR_BP + 1)  # BUG: wrong divisor"),
        (2, "solutions/stage_02.py",
         '"discount_bp": PAR_BP - price_bp}',
         '"discount_bp": PAR_BP + price_bp}  # BUG: add instead of subtract'),
        # Stage 3: expected recovery
        (3, "solutions/stage_03.py",
         "expected_bp = discounted * PAR_BP // par",
         "expected_bp = discounted * PAR_BP // (par + 1)  # BUG: par + 1"),
        (3, "solutions/stage_03.py",
         "if steps < 0:\n                steps = 0",
         "if steps < 0:\n                steps = 1  # BUG: forward-discount even past recoveries"),
        # Stage 4: Merton distance
        (4, "solutions/stage_04.py",
         "return (asset_value - debt) * DD_SCALE * DD_SCALE // (asset_value * band_bp)",
         "return (asset_value - debt) * DD_SCALE // (asset_value * band_bp)  # BUG: one DD_SCALE too few"),
        (4, "solutions/stage_04.py",
         "if row[\"from_dd\"] <= dd_units:",
         "if row[\"from_dd\"] < dd_units:  # BUG: strict < misses exact bounds"),
        # Stage 5: three readings and spread
        (5, "solutions/stage_05.py",
         "middle_bp = sorted((forecast_bp, merton_bp, comps_bp))[1]",
         "middle_bp = sorted((forecast_bp, merton_bp, comps_bp))[0]  # BUG: best case not middle"),
        (5, "solutions/stage_05.py",
         "\"forecast_merton_bp\": forecast - merton,",
         "\"forecast_merton_bp\": merton - forecast,  # BUG: swapped subtraction"),
        # Stage 6: restructuring
        (6, "solutions/stage_06.py",
         "remaining = remaining - take",
         "remaining = remaining + take  # BUG: add instead of subtract"),
        (6, "solutions/stage_06.py",
         "pool = pool - cents",
         "pool = pool + cents  # BUG: add decree back instead of subtract"),
        # Stage 7: exchange
        (7, "solutions/stage_07.py",
         "tendered = sum(row[\"face_cents\"] for row in rows if row[\"vote\"] == \"tender\")",
         "tendered = sum(row[\"face_cents\"] for row in rows)  # BUG: count holds too"),
        (7, "solutions/stage_07.py",
         "received = row[\"face_cents\"] * restructuring[\"issue_bp\"] // PAR_BP",
         "received = row[\"face_cents\"] * PAR_BP // restructuring[\"issue_bp\"]  # BUG: inverted"),
        # Stage 8: PV and IRR
        (8, "solutions/stage_08.py",
         '"residue_cents": cost_cents - pv_cents}',
         '"residue_cents": cost_cents - pv_cents + 1}  # BUG: off by one residue'),
        (8, "solutions/stage_08.py",
         "factor = factor * rules.DISCOUNT_SCALE // (rules.DISCOUNT_SCALE + period_bp)",
         "factor = factor * (rules.DISCOUNT_SCALE + period_bp) // rules.DISCOUNT_SCALE  # BUG: inverted discount"),
        # Stage 9: carry and hold
        (9, "solutions/stage_09.py",
         "booked = annual * months // 12",
         "booked = annual * (months + 1) // 12  # BUG: extra month"),
        (9, "solutions/stage_09.py",
         "decision = DECISIONS[0] if upside > hold_cents else DECISIONS[1]",
         "decision = DECISIONS[1] if upside > hold_cents else DECISIONS[0]  # BUG: inverted"),
        # Stage 10: thesis and audit
        (10, "solutions/stage_10.py",
         "receipts_cents = class_receipts * position_face // face",
         "receipts_cents = class_receipts * face // position_face  # BUG: inverted ratio"),
        (10, "solutions/stage_10.py",
         "grade = GRADES[0] if gap_bp <= tolerance_bp else GRADES[1]",
         "grade = GRADES[1] if gap_bp <= tolerance_bp else GRADES[0]  # BUG: inverted grade"),
    ]

    tmpdir = tempfile.mkdtemp(dir="/tmp/opencode")
    dst = os.path.join(tmpdir, COURSE)
    shutil.copytree(COURSE_DIR, dst)

    killed = 0
    missed = []
    skipped = []

    for stage_num, sol_path, old_text, new_text in MUTATIONS:
        check_name = checks[stage_num]
        # Copy solutions over templates first
        sol_dir = os.path.join(dst, "solutions")
        for f in os.listdir(sol_dir):
            if f.startswith("stage_") and f.endswith(".py"):
                shutil.copy2(os.path.join(sol_dir, f), os.path.join(dst, f))

        # Apply mutation to the stage file (the copy in the course dir, not solutions/)
        stage_file = f"stage_{stage_num:02d}.py"
        target = os.path.join(dst, stage_file)
        with open(target, "r") as f:
            content = f.read()

        if old_text not in content:
            skipped.append((stage_num, sol_path, old_text[:50]))
            continue

        content = content.replace(old_text, new_text)
        with open(target, "w") as f:
            f.write(content)

        # Run the check — expect it to FAIL
        passed, err = _run_check(check_name, dst)

        if passed:
            missed.append((stage_num, sol_path, old_text[:50], new_text[:50]))
        else:
            killed += 1

        # Restore original
        content = content.replace(new_text, old_text)
        with open(target, "w") as f:
            f.write(content)

    shutil.rmtree(tmpdir, ignore_errors=True)

    # Report
    print(f"MUTATIONS {killed}/{killed + len(missed) + len(skipped)}, MISSED: {len(missed)}")
    for stage_num, sol_path, old_text, new_text in missed:
        print(f"  MISSED stage {stage_num}: {sol_path} — {old_text[:40]}")
    for stage_num, sol_path, old_text in skipped:
        print(f"  SKIPPED stage {stage_num}: {sol_path} — could not find {old_text[:30]}")

    if missed:
        print("\nMISSED mutations detected — strengthen the check!")
        sys.exit(1)
    else:
        print("All mutations killed.")


if __name__ == "__main__":
    mutate()