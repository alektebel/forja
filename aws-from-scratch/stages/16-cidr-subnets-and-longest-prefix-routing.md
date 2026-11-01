# Stage 16: CIDR, subnets and longest-prefix routing

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `vpc.py`
**Tags:** networking, boundary

## The mechanism

VPC: CIDR -> subnets, and routes pick the LONGEST matching prefix, not the first or the shortest.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 16
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 16
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which route wins for 10.0.1.5.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 17
```
