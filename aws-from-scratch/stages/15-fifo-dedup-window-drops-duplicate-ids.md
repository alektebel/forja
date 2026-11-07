# Stage 15: FIFO dedup window drops duplicate ids

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging

## The mechanism

FIFO dedup: a duplicate dedup_id inside the 5-minute window is dropped; outside it is accepted again.

## Why the requirement is what it is

Producers retry on network flakiness; without dedup every retry is a duplicate order. A time window instead of forever keeps the dedup table bounded — the cost of the guarantee, and its expiry surprise.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 15
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 15
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the second send with the same dedup_id at t=10 and at t=400.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 16
```
