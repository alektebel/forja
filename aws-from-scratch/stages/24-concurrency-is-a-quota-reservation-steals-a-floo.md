# Stage 24: concurrency is a quota; reservation steals a floor

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** availability

## The mechanism

Async failures retry to 3 total attempts, then the event lands in the dead-letter queue; sync failures return to the caller instead.

## Why the requirement is what it is

Same bug, different blast radius: sync surfaces the error to whoever can react; async retries blindly — so a non-idempotent handler runs THREE times: three charges, three emails.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 24
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 24
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> attempts for a failing async handler.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 25
```
