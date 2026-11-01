# Stage 9: capacity, hot partitions, scan cost

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** capacity

## The mechanism

Capacity: RCU/WCU from item size; a hot partition is a bad key distribution; Scan costs roughly the whole table.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> WCU for a 2KB write with no batching.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 10
```
