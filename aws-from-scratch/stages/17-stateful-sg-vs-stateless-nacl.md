# Stage 17: stateful SG vs stateless NACL

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `vpc.py`
**Tags:** stateless-vs-stateful

## The mechanism

Security groups are STATEFUL (return traffic is automatic); NACLs are STATELESS (allow both directions explicitly).

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 17
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 17
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why a NACL blocks the reply to an allowed request.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 18
```
