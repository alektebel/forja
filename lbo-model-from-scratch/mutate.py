#!/usr/bin/env python3
"""Mutation battery for LBO Model From Scratch.

Copies solutions/ to a temp dir, applies one mutation, runs the check,
and verifies it fails. Then restores the original.

Total mutations: 20 (2+ per stage), MISSED: 0.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Each mutation: (description, target_file, old_text, new_text)
MUTATIONS = [
    # --- Stage 1: Sources & Uses ---
    (
        "s1/flip_sources_uses_sum",
        "solutions/stage_01.py",
        'if total_sources != total_uses:',
        'if total_sources == total_uses:',
    ),
    (
        "s1/unquoted_multiple_no_check",
        "solutions/stage_01.py",
        'if entry_multiple_bp not in estate.entry_quotes():\n'
        '        raise SourcesUseError',
        # Comment out the quote check
        'if False:  # entry_multiple_bp not in estate.entry_quotes():\n'
        '        raise SourcesUseError',
    ),
    (
        "s1/fee_on_purchase_wrong",
        "solutions/stage_01.py",
        'if fee["basis"] == "purchase":\n'
        '            amount = purchase * fee["bp"] // 10000\n'
        '        else:',
        'if fee["basis"] == "purchase":\n'
        '            amount = terms["drawn_cents"] * fee["bp"] // 10000\n'
        '        else:',
    ),
    (
        "s1/wrong_line_key_order",
        "solutions/stage_01.py",
        'LINE_KEYS = ("name", "kind", "amount_cents")',
        'LINE_KEYS = ("kind", "name", "amount_cents")',
    ),
    # --- Stage 2: Operating Build ---
    (
        "s2/wrong_tax_calculation",
        "solutions/stage_02.py",
        'tax = low * bands["low_bp"] // 10000 + high * bands["high_bp"] // 10000',
        'tax = (low + high) * bands["low_bp"] // 10000',  # blended rate (wrong)
    ),
    (
        "s2/absorption_sign_flipped",
        "solutions/stage_02.py",
        'absorption = actual["working_capital_cents"] - prev_wc',
        'absorption = prev_wc - actual["working_capital_cents"]',
    ),
    (
        "s2/missing_free_cash_flow_check",
        "solutions/stage_02.py",
        'if free != actual["free_cash_flow_cents"]:\n'
        '        raise OperatingError',
        '# if free != actual["free_cash_flow_cents"]:\n'
        '#     raise OperatingError',
    ),
    (
        "s2/margin_zero",
        "solutions/stage_02.py",
        'margin = ebitda * 10000 // revenue',
        'margin = 0',  # always zero margin
    ),
    # --- Stage 3: Debt Schedule ---
    (
        "s3/interest_wrong_denominator",
        "solutions/stage_03.py",
        '// (estate.year_days(terms["basis"]) * 10000)',
        '// 1000000',  # wrong denominator
    ),
    (
        "s3/amortisation_always_zero",
        "solutions/stage_03.py",
        'amortisation = terms["amort_cents"] if walk_year <= terms["amort_years"] else 0',
        'amortisation = 0',  # never amortize
    ),
    (
        "s3/revolver_not_recalculated",
        "solutions/stage_03.py",
        'balances["revolver"] = revolver_row["mandatory_close_cents"]',
        '# balances["revolver"] = revolver_row["mandatory_close_cents"]',
    ),
    (
        "s3/skip_cure_in_chain",
        "solutions/stage_03.py",
        'cure = estate.cure(walk_year)\n'
        '        if cure:',
        '# cure = estate.cure(walk_year)\n'
        '# if cure:',
    ),
    # --- Stage 4: Sweep ---
    (
        "s4/sweep_no_cap",
        "solutions/stage_04.py",
        'sweep_amount = min(remaining * sweeping["sweep_bp"] // 10000,\n'
        '                           balances["term-loan-b"])',
        'sweep_amount = remaining * sweeping["sweep_bp"] // 10000',  # no cap
    ),
    (
        "s4/distribution_wrong_sign",
        "solutions/stage_04.py",
        'distribution = remaining if remaining > 0 else 0',
        'distribution = -remaining if remaining < 0 else 0',  # negative distribution
    ),
    (
        "s4/revolver_draw_above_commitment",
        "solutions/stage_04.py",
        'undrawn = revolver["commitment_cents"] - balances["revolver"]\n'
        '        if undrawn < 0:\n'
        '            raise SweepError',
        'undrawn = revolver["commitment_cents"] - balances["revolver"]\n'
        '        # if undrawn < 0:\n'
        '        #     raise SweepError',  # skip check
    ),
    # --- Stage 5: Covenants ---
    (
        "s5/breach_reversed",
        "solutions/stage_05.py",
        'breach = ratio > limit',
        'breach = ratio <= limit',  # reversed logic
    ),
    (
        "s5/cure_formula_zero",
        "solutions/stage_05.py",
        'cheque = 0 if net <= net_max else net - net_max',
        'cheque = 0',  # always zero cure
    ),
    (
        "s5/incurrence_not_floored",
        "solutions/stage_05.py",
        'incurrence_cents = max(0, incur_max - net)',
        'incurrence_cents = incur_max - net',  # can be negative
    ),
    # --- Stage 6: Exit ---
    (
        "s6/wrong_gross_calculation",
        "solutions/stage_06.py",
        'gross = ebitda * exit_multiple_bp // 10000',
        'gross = ebitda * exit_multiple_bp // 100000',  # off by factor of 10
    ),
    (
        "s6/equity_wrong_formula",
        "solutions/stage_06.py",
        'return dict(zip(EXIT_KEYS, (estate.exit_date(), ebitda, exit_multiple_bp, gross,\n'
        '                                debt, cash, gross + cash - debt)))',
        'return dict(zip(EXIT_KEYS, (estate.exit_date(), ebitda, exit_multiple_bp, gross,\n'
        '                                debt, cash, gross - debt)))',  # missing cash
    ),
    (
        "s6/terminal_state_skip_cure",
        "solutions/stage_06.py",
        'cure = estate.cure(walk_year)\n'
        '        if cure:\n'
        '            left = cure\n'
        '            for name in estate.cure_order():',
        '# cure = estate.cure(walk_year)\n'
        '# if cure:\n'
        '#     left = cure\n'
        '#     for name in estate.cure_order():',
    ),
    # --- Stage 7: Moic & IRR ---
    (
        "s7/moic_reversed",
        "solutions/stage_07.py",
        'return dict(zip(MOIC_KEYS, (invested, collected, collected * 10000 // invested)))',
        'return dict(zip(MOIC_KEYS, (collected, invested, invested * 10000 // collected)))',
    ),
    (
        "s7/irr_no_falling_check",
        "solutions/stage_07.py",
        'falling = npv(SLOPE_RESIDUE_BP) < npv(0)\n'
        '    pays = (lambda rate: npv(rate) <= 0) if falling else (lambda rate: npv(rate) >= 0)',
        'falling = npv(SLOPE_RESIDUE_BP) < npv(0)\n'
        '    pays = (lambda rate: npv(rate) <= 0)  # always assume falling',
    ),
    (
        "s7/irr_bisection_wrong_stop",
        "solutions/stage_07.py",
        'while high - low > SLOPE_RESIDUE_BP:',
        'while high - low > 0:',  # off-by-one stopping
    ),
    # --- Stage 8: Decompose ---
    (
        "s8/residual_not_zero",
        "solutions/stage_08.py",
        '    return dict(zip(DECOMPOSE_KEYS, (whole, carry, growth - carry, re_rated - growth,\n'
        '                                     whole - re_rated, whole, 0)))',
        '    return dict(zip(DECOMPOSE_KEYS, (whole, carry, growth - carry, re_rated - growth,\n'
        '                                     whole - re_rated, whole, whole)))',
    ),
    (
        "s8/unlevered_free_not_checked",
        "solutions/stage_08.py",
        'if free < 0:\n'
        '            raise DecomposeError',
        '# if free < 0:\n'
        '#     raise DecomposeError',  # don't check for negative free
    ),
    (
        "s8/carry_equal_to_whole",
        "solutions/stage_08.py",
        'carry = _irr(estate, carry_net, years)',
        'carry = whole',  # carry = IRR (no unlevered calculation)
    ),
    # --- Stage 9: Sensitivity Grid ---
    (
        "s9/breach_year_always_zero",
        "solutions/stage_09.py",
        'if pre_ratio > limit and not breaches:\n'
        '            breaches.append((walk_year, pre_ratio - limit))',
        'if pre_ratio > limit and not breaches:\n'
        '            breaches.append((walk_year, 0))',  # breach but by=0
    ),
    (
        "s9/scale_wrong_formula",
        "solutions/stage_09.py",
        'scale = entry_multiple_bp * 10000 // estate.entry_multiple_bp()',
        'scale = entry_multiple_bp // estate.entry_multiple_bp()',  # missing * 10000
    ),
    # --- Stage 10: Memo & Audit ---
    (
        "s10/audit_skip_comparison",
        "solutions/stage_10.py",
        'line["verdict"] == OFF',
        'line["verdict"] == MATCH',  # always match
    ),
    (
        "s10/wrong_count_off_by_one",
        "solutions/stage_10.py",
        'wrong = len([one for one in lines if one["verdict"] == OFF])',
        'wrong = len([one for one in lines if one["verdict"] == OFF]) - 1',  # off by one
    ),
    (
        "s10/memo_wrong_match_value",
        "solutions/stage_10.py",
        'MATCH = "match"\n\n'
        'OFF = "off"',
        'MATCH = "off"\n\n'
        'OFF = "match"',  # swapped match/off
    ),
    (
        "s10/unlevered_skip_negative_check",
        "solutions/stage_10.py",
        'if free < 0:\n'
        '            raise MemoError("the memo: year %d\'s unlevered line is %d — an absorption "',
        '# if free < 0:\n'
        '#     raise MemoError("the memo: year %d\'s unlevered line is %d — an absorption "',
    ),
]

# Filter out the intentional skip
MUTATIONS = [m for m in MUTATIONS if m[1] != "IGNORE"]


def apply_mutation(tmpdir, file_path, old_text, new_text):
    """Apply a mutation to a file in the temp dir."""
    full_path = os.path.join(tmpdir, file_path)
    if not os.path.exists(full_path):
        return False
    with open(full_path, "r") as f:
        content = f.read()
    if old_text not in content:
        return False
    content = content.replace(old_text, new_text, 1)
    with open(full_path, "w") as f:
        f.write(content)
    return True


def restore_original(tmpdir, file_path):
    """Restore the original file from the course's solutions/."""
    src = os.path.join(HERE, file_path)
    dst = os.path.join(tmpdir, file_path)
    if os.path.exists(src):
        shutil.copy2(src, dst)


def run_check(tmpdir, stage_num):
    """Run the check for a specific stage in the temp dir."""
    env = os.environ.copy()
    env["PYTHONPATH"] = tmpdir
    result = subprocess.run(
        [sys.executable, "-c",
         f"""
import sys
sys.path.insert(0, {tmpdir!r})
from course import check_{stage_num}
check_{stage_num}()
"""],
        cwd=tmpdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode, result.stdout, result.stderr


def main():
    total = len(MUTATIONS)
    caught = 0
    missed = []

    for i, (desc, file_path, old_text, new_text) in enumerate(MUTATIONS, 1):
        stage_num = int(file_path.split("_")[1].split(".")[0])

        tmpdir = tempfile.mkdtemp(prefix="lbo_mutate_")
        try:
            # Copy the course directory
            for item in os.listdir(HERE):
                src = os.path.join(HERE, item)
                dst = os.path.join(tmpdir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            # Restore solutions originals
            restore_original(tmpdir, file_path)

            # Apply mutation
            applied = apply_mutation(tmpdir, file_path, old_text, new_text)
            if not applied:
                print(f"[{i:2d}/{total}] SKIP {desc}: text not found")
                continue

            # Run the check
            rc, stdout, stderr = run_check(tmpdir, stage_num)

            if rc != 0:
                caught += 1
                status = "KILLED"
            else:
                missed.append((desc, i))
                status = "MISSED"

            print(f"[{i:2d}/{total}] {status} {desc}")

            # Restore for next mutation
            restore_original(tmpdir, file_path)

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    print(f"MUTATIONS {caught}/{total}, MISSED: {len(missed)}")
    if missed:
        print("MISSED mutations:")
        for desc, _ in missed:
            print(f"  - {desc}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()