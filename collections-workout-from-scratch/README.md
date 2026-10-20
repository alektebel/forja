# Collections, Workout and Recovery From Scratch

A loan's collections life as numbers, over a provided book and the bank's own collections operation. Ten graded stages: delinquency state, the pyramid, replay, forbearance, cure rate, waterfall, sale, settlement, discounted LGD, and the capstone per-loan story.

Standard library only, no float, no math, no decimal, no fractions, no random, no clock, no socket. Every number is integer cents or basis points.

## Stages

| # | Stage | Tags | Action |
|---|-------|------|--------|
| 1 | Days past due and the delinquency state | dpd, bucket, materiality | Write `DelinquencyError`, `STATE_KEYS`, `dpd` and `state` in `stage_01.py`. |
| 2 | The pyramid and its triggers | pyramid, dunning, referral | Write `TraversalError`, `ACTION_KEYS` and `due_actions` in `stage_02.py`. |
| 3 | Replaying the actual action log | replay, vault, integrity | Write `ReplayError`, `LOG_RECORD_KEYS`, `replay` and `vault` in `stage_03.py`. |
| 4 | Forbearance as the bank's decision | forbearance, remedy, eligibility | Write `ForbearanceError`, `REMEDY_KEYS`, `eligible`, `terms` and `probation` in `stage_04.py`. |
| 5 | Cure rate and re-default | cure, re-default, cohort | Write `MeasureError`, `COHORT_KEYS` and `cures` in `stage_05.py`. |
| 6 | The collections waterfall over the cash | waterfall, split, cent-precision | Write `WaterfallError`, `APPLY_KEYS`, `apply` and `ledger` in `stage_06.py`. |
| 7 | The workout on default: the collateral sale | workout, sale, proceeds | Write `WorkoutError`, `SALE_KEYS` and `sale` in `stage_07.py`. |
| 8 | Settlement, deficiency and the write-off | settlement, deficiency, write-off | Write `WriteoffError`, `WRITEOFF_KEYS`, `deficiency`, `settlement` and `writeoff` in `stage_08.py`. |
| 9 | The recovery flows, discounted to the default date | recovery, discounting, lgd | Write `RecoveryError`, `RECOVERY_KEYS`, `flows`, `discounted` and `lgd_against` in `stage_09.py`. |
| 10 | The per-loan story (capstone) | story, audit, capstone | Write `CapstoneError`, `STORY_KEYS`, `story` and `audit` in `stage_10.py`. |

## World modules (provided, do not modify)

- `book.py` — The bank's raw facts and accounting records
- `workout.py` — The bank's collections operation as data (pyramid, waterfall, workout, etc.)
- `dates.py` — Date arithmetic
- `rules.py` — Policy rules

## Running

```bash
# Verify solution files
python3 verify_cws.py

# Run mutation testing (20+ mutations, all must be killed)
python3 mutate_cws.py
```

## Verifying your stage

Each `stage_NN.py` file has a `if __name__ == "__main__"` block you can run directly:

```bash
python3 stage_01.py
python3 stage_06.py
```

## Design principles

1. **The book is never written** — stages read from the book and produce answers
2. **Cent-precision** — every amount is an integer count of cents
3. **Basis points** — every rate is an integer count of basis points
4. **No float** — all arithmetic is fixed-point integer math
5. **Deterministic** — no random, no clock, no socket