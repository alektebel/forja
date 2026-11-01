# Stage 8: is the difference real?

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_08.py`
**Tags:** statistics, significance

## The mechanism

Implement binom_two_sided, mcnemar, paired_bootstrap, independent_ci and decide — paired, with three outcomes.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 8
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Same data, paired and independent intervals: which is narrower?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- resample ITEMS, both systems together
- an interval containing zero is not a win

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 9
```
