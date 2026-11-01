# Stage 8: composite keys, query, conditions

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** storage

## The mechanism

DynamoDB composite key = partition + sort: Query is within one partition, and conditional writes fail cleanly on conflict.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 8
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether Query can span partitions.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 9
```
