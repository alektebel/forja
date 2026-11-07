# Stage 14: FIFO: one in-flight message per group

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging

## The mechanism

FIFO: only ONE in-flight message per message group; a different group is never blocked.

## Why the requirement is what it is

Ordering within a group is the entire point of groups — and it is exactly what forbids parallelism inside one. The group id is your concurrency dial: coarse enough to keep order, fine enough to keep throughput.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 14
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 14
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many of 3 same-group messages one receive returns.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 15
```
