# Stage 9: ten configs, one winner, no correction

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_09.py`
**Tags:** statistics, multiple-comparisons

## The mechanism

Implement holm (with the running maximum) and significant (step-down thresholds) over a family of p-values.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> p=0.04 as 1 test, and as the best of 10: significant?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- adjusted_i = max(adjusted_{i-1}, p_i * (m - i + 1))
- the family is decided before the p-values are read

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 10
```
