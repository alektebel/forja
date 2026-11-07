# Stage 33: CIDR containment, overlap, 5 reserved IPs

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `vpc.py`
**Tags:** networking

## The mechanism

Route tables match the LONGEST PREFIX, not the first or the shortest entry.

## Why the requirement is what it is

Most-specific wins is what lets a peering route (10.1.0.0/16) and a finer transit route (10.1.5.0/24) coexist with a default route — order in the table is irrelevant, exactly like IAM's deny-wins rule.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 33
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 33
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which route wins for 10.0.1.5.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 34
```
