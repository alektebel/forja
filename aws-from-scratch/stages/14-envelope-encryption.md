# Stage 14: envelope encryption

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** authorization

## The mechanism

KMS envelope encryption: a data key encrypts the data, and the CMK encrypts the data key.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 14
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 14
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what you must store alongside the ciphertext.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 15
```
