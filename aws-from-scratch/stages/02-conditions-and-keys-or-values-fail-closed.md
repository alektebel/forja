# Stage 2: conditions: AND keys, OR values, fail closed

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

Policy conditions: AND across keys, OR within one key's values, and a MISSING context key never matches.

## Why the requirement is what it is

Fail-closed is not a style choice — it is the difference between a bug and a vulnerability. Treat an absent aws:SourceIp as 'any IP' and a request with no context at all bypasses every IP restriction. The AND/OR shape also returns in SNS filters (stage 16): learn it once here.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 2
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 2
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> a request with NO context keys against a policy requiring two conditions.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 3
```
