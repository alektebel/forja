# Stage 3: permissions boundaries subtract, never grant

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

Permissions boundaries: a boundary only SUBTRACTS from what identity policies grant, it can never grant.

## Why the requirement is what it is

If a boundary could grant, handing someone a boundary would be a privilege escalation, and delegation would be unsafe. Subtract-only is what makes 'you may be an admin of this project, never of IAM' expressible at all.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> Allow outside the boundary.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 4
```
