# Stage 6: visibility timeout and redelivery

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging, lifecycle

## The mechanism

The visibility timeout hides a message; if it is not deleted in time it is redelivered.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether the same message is received twice.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 7
```
