# Stage 31: encryption context must match on decrypt

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** security, lifecycle

## The mechanism

Rotation creates a new key VERSION: new encryptions use it, old versions are retained, and ALL old ciphertext still decrypts. Deleting a version makes its ciphertext unrecoverable.

## Why the requirement is what it is

Re-encrypting all data on rotation would be an outage, so rotation re-encrypts KEYS, never DATA. The mandatory waiting period on deletion exists because 'unrecoverable' must be hard to do by accident.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 31
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 31
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether last year's ciphertext decrypts after rotation.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 32
```
