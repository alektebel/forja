# Stage 7: what the judge is worth

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_07.py`
**Tags:** calibration, statistics

## The mechanism

Implement confusion, agreement, cohen_kappa and threshold_for, sweeping the pass/fail cut by F1 on the labelled set.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 7
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> A judge that always says pass, on a set that is 85% passes: kappa?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- kappa subtracts the agreement chance would give
- the threshold trades false passes against false failures

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 8
```
