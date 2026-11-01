# Stage 3: STS assume-role: both directions

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

Assume-role needs trust on both sides: the caller may assume, AND the role must allow the action.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> identity policy Allows but trust policy does not.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 4
```
