# Stage 11: change_visibility extends the lease

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging

## The mechanism

change_visibility extends a lease: a consumer whose work outlasts the timeout renews instead of racing redelivery.

## Why the requirement is what it is

Lease expiry exists for CRASHED consumers. A live slow consumer should never hit it — extending the deadline is the fix, and heartbeat loops in real systems are exactly this call on a timer.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 11
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 11
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether the message returns at the original timeout after an extension.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 12
```
