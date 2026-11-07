# Stage 18: conditional writes fail atomically

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** capacity

## The mechanism

A strongly consistent read costs exactly TWICE an eventually consistent one.

## Why the requirement is what it is

Consistency is paid per read, not configured once: strong reads hit enough replicas to confirm, eventual ones hit one. Pricing it 2x is what makes people ask 'do I need consistent here?' instead of defaulting to yes.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 18
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 18
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> consistent cost for a 0.5-unit eventual read.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 19
```
