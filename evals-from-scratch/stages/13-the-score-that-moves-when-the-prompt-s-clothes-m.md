# Stage 13: the score that moves when the prompt's clothes move

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_13.py`
**Tags:** sensitivity, criteria, validity

## The mechanism

Implement format_spread, holds_under_formats, criteria_id (order-independent) and comparable.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 13
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 13
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Scores 0.91 / 0.88 / 0.40 across three formats: what does the mean hide?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- report the range and the worst format, not only the mean
- criteria_id sorts and normalises, or declaration order looks like drift

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 14
```
