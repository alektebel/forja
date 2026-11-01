# Stage 15: encryption context and rotation

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** authorization

## The mechanism

Encryption context must match on decrypt; rotation changes the CMK but old ciphertext still decrypts.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 15
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 15
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> decrypt with a mismatched context.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 16
```
