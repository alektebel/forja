# Stage 30: one KMS call per object, not per byte

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** authorization, security

## The mechanism

The encryption context must MATCH on decrypt — wrong, empty or missing context all fail.

## Why the requirement is what it is

The context is authenticated data: not secret, but bound into the unwrap. It is what lets an IAM condition scope a key to a tenant — decrypt refuses to run outside the context the key was created under.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 30
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 30
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> decrypt with a mismatched context.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 31
```
