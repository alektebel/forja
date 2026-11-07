# Stage 4: assume-role: caller policy AND role trust

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

Assume-role needs BOTH directions: the caller's own policy must allow sts:AssumeRole, AND the role's trust policy must allow that principal.

## Why the requirement is what it is

Two policies for two different attackers. Your own policy protects you from yourself (an intern's role-escape); the trust policy protects you from OTHER accounts — without it, anyone whose own policy says 'I may assume anything' walks into your roles.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> identity policy Allows but trust policy does not.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 5
```
