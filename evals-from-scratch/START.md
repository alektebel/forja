# Evals From Scratch

An evaluation harness from the parts up: honest splits, operational metrics, deterministic assertions, EM/F1, ranking metrics, an LLM judge with its biases, calibration, paired significance, multiple comparisons, a regression gate, structured field metrics, confidence ECE, and format sensitivity.

**13 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke evals-from-scratch
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `stage_01.py` — the eval set, and the split that must not leak

Implement load() with validation and copies, and split() that keeps whole groups on one side of the split, seeded.

```bash
forja guide evals-from-scratch 1     # the full stage page
forja test evals-from-scratch --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint evals-from-scratch` · `forja explain evals-from-scratch`
