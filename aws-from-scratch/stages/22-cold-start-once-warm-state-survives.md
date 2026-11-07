# Stage 22: cold start once; warm state survives

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** lifecycle

## The mechanism

An environment past its TTL is replaced (fresh state); a timeout is reported and billed in full.

## Why the requirement is what it is

Warm state is an optimisation, never a guarantee — AWS reclaims environments whenever it wants. Code that works only because the cache was warm is a bug with a timer on it. Timeouts bill fully because the capacity was truly occupied.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 22
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 22
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the counter value after an invocation past the TTL.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 23
```
