# Stage 32: rotation re-encrypts keys, never data

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `kms.py`
**Tags:** networking

## The mechanism

CIDR: containment and overlap of subnets, and AWS reserves 5 addresses per subnet — a /28 has 11 usable hosts, not 16.

## Why the requirement is what it is

The reserved five (network, DNS x2, broadcast, future) are the number people get wrong when sizing subnets — and overlapping subnets are rejected because routing must have exactly one answer for any address.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 32
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 32
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> usable hosts in a /28.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 33
```
