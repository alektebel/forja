# Stage 1: explicit deny > allow > implicit deny

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `iam.py`
**Tags:** authorization

## The mechanism

IAM: an explicit Deny wins; otherwise any matching Allow applies; otherwise implicit Deny.

## Why the requirement is what it is

This rule is what makes a policy SET composable: order never matters, so appending a guard policy can never break existing grants. Evaluate it like a firewall (first or last match wins) and the same policies behave differently depending on document order — no property you can reason about at scale.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 1
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 1
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the result when Allow and Deny both match.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 2
```
