# Stage 28: EventBridge matches nested shape, fires every rule

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sns.py`
**Tags:** authorization, security

## The mechanism

Envelope encryption: generate a data key (plaintext + wrapped copy), encrypt the data locally, store only the wrapped key alongside.

## Why the requirement is what it is

KMS is a vault with a 4KB door: you do not push data through it. The data never leaves you — size is unchanged — and KMS only ever touches the small key. That is the whole reason the payload limit never constrains you.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 28
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 28
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what you must store alongside the ciphertext.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 29
```
