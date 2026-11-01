# Stage 2: conditions and permissions boundaries

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

Evaluate conditions and permissions boundaries — a boundary only SHRINKS the permission, it can never grant one.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Allow outside the boundary.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 3
```
