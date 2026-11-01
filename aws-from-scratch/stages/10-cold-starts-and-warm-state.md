# Stage 10: cold starts and warm state

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `lambda_svc.py`
**Tags:** lifecycle

## The mechanism

Lambda cold start initialises the container once; warm invocations reuse whatever the container kept in memory.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many inits over six invocations.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 11
```
