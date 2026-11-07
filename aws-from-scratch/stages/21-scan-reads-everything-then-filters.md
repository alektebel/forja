# Stage 21: scan reads everything, then filters

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** lifecycle

## The mechanism

Lambda cold start: the first invocation pays the init cost; warm invocations reuse the environment AND its memory.

## Why the requirement is what it is

The container outlives your invocation BY DESIGN — that is how init gets amortised. Consequence cut both ways: a connection pool is free, a cache you assumed empty is a correctness bug.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 21
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 21
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many inits over six invocations.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 22
```
