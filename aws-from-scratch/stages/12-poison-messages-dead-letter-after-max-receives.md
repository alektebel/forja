# Stage 12: poison messages dead-letter after max_receives

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging

## The mechanism

Dead-letter queue: after max_receives the message moves to the DLQ instead of being delivered again.

## Why the requirement is what it is

Without a DLQ a poison message retries forever: it eats throughput AND hides every message behind it. Bounded retries plus a DLQ convert 'queue stuck' into 'queue moving, alarm on the DLQ depth'.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 12
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many times a failing message is delivered.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 13
```
