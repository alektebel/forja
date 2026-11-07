# Stage 25: async failures retry to 3 attempts, then DLQ

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** messaging

## The mechanism

SNS fans out: one publish delivers to EVERY subscriber — queues and Lambda handlers alike — on the same clock it was given.

## Why the requirement is what it is

Push means no consumer polls, so no buffering: SNS delivers and drops on failure, which is exactly why SNS → SQS → consumer is the standard shape rather than an accident. The clock threading is the bug that makes messages land 'in the future' in tests.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 25
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 25
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> queue depths right after a publish to 3 subscribers.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 26
```
