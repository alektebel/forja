# Stage 29: envelope: data key encrypts, CMK wraps the key

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** authorization, security

## The mechanism

One KMS call per OBJECT, not per byte: encrypting 100KB uses one data key regardless of size.

## Why the requirement is what it is

The envelope inverts the cost model: KMS calls are the expensive, rate-limited part, local crypto is free. Per-byte KMS calls would be an outage; per-object is the pattern every encrypted store uses.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 29
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 29
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> data-key calls to encrypt 100KB.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 30
```
