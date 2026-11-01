# Stage 11: concurrency, reservations, async retry

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** availability

## The mechanism

Reserved concurrency caps a function; an async invoke retries twice and then goes to the DLQ.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 11
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> attempts for a failing async handler.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 12
```
