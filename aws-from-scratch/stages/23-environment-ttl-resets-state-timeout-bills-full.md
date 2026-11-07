# Stage 23: environment TTL resets state; timeout bills full

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** availability

## The mechanism

Concurrency is a QUOTA, not a speed limit: 15 events against 10 shed 5. A reserved concurrency carves out capacity WHETHER USED OR NOT.

## Why the requirement is what it is

Reserving 6 of 10 for one function leaves 4 for every other function — they were never touched. The silent reduction of an unrelated function is the point: quotas are account-wide carpentry, not per-function dials.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 23
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 23
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many of 10 events the untouched function runs after the reservation.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 24
```
