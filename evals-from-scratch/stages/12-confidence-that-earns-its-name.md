# Stage 12: confidence that earns its name

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_12.py`
**Tags:** calibration, ece, confidence

## The mechanism

Implement reliability_bins, ece (count-weighted) and auto_approve_threshold under a precision floor.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 12
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> All confidences 0.9, half correct, 10 bins: ECE?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- ECE weights each bin by n_b/N — empty bins must not dilute it
- confidence 1.0 belongs in the last bin, not off the end
- the threshold is the lowest cut that still meets min_precision

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 13
```
