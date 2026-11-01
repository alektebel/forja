# Stage 1: the eval set, and the split that must not leak

**Course:** Evals From Scratch (`evals-from-scratch`)
**File:** `stage_01.py`
**Tags:** datasets, leakage

## The mechanism

Implement load() with validation and copies, and split() that keeps whole groups on one side of the split, seeded.

## Tests

The tester runs your code like this:

```bash
forja test evals-from-scratch --stage 1
# same as:
python3 codecraft/cli.py run evals-from-scratch --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> 10 groups of 3 rows, ratios 0.6/0.2/0.2: how many rows in train?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- shuffle the GROUPS, then fill the splits to their target sizes
- a random row split puts five phrasings of one ticket on both sides of the line

## Next

When this stage is green:

```bash
forja stage evals-from-scratch 2
```
