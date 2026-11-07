# Stage 5: put/get objects and the NoSuchKey error

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage

## The mechanism

S3 objects: put/get with an ETag (the body's MD5), and a missing key raises NoSuchKey.

## Why the requirement is what it is

The ETag is the content hash because S3 is a flat KV store with no directories to hide consistency behind — the tag is your only cheap integrity check, and the NoSuchKey error (not a null) is how you distinguish 'absent' from 'present but empty'.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what GET returns for a key that was never written.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 6
```
