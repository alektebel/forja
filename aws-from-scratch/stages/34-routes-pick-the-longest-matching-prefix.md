# Stage 34: routes pick the longest matching prefix

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `vpc.py`
**Tags:** stateless-vs-stateful, networking

## The mechanism

Security groups are STATEFUL: allow the request in and the reply out is automatic. NACLs are STATELESS: same rules fail, because the reply goes to an EPHEMERAL port.

## Why the requirement is what it is

The reply is a new packet to 49152-65535, and nobody remembers to allow that. This is the single most common VPC bug, and it is invisible unless you model the whole connection — evaluate only the request and SG vs NACL look identical.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 34
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 34
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> why a NACL blocks the reply to an allowed request.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 35
```
