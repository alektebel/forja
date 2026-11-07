# Stage 17: query reads one partition; missing key raises

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** storage

## The mechanism

Conditional writes: put with a condition raises ConditionalCheckFailed when it fails, and the failed write changes nothing.

## Why the requirement is what it is

The check and the write happen atomically inside one partition, which is how you get idempotent creates and optimistic locking with no lock service at all. Failing cleanly is the feature: it means someone got there first, exactly what you asked to know.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 17
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 17
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the value after a failed conditional put.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 18
```
