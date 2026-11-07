# Stage 16: composite key = partition + sort

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** storage

## The mechanism

DynamoDB composite key = partition + sort: get_item is keyed by BOTH, and query reads only one partition.

## Why the requirement is what it is

Keying by sort key alone would make alice/000 and bob/000 collide — silent data loss. And query's demand for the partition key is not a limitation, it is the CONTRACT that buys O(items returned) instead of O(table).


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 16
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 16
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether Query can span partitions.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 17
```
