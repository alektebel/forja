# Stage 20: capacity divides across partitions; hot key throttles

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** capacity

## The mechanism

Scan reads EVERY item and filters afterwards: a scan returning 3 of a million items costs a million reads.

## Why the requirement is what it is

Scan has no key to route by, so it walks every partition — you pay for what you read, not what you keep. Query, given the partition key, reads only what can match. That asymmetry is the whole data model.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 20
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 20
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which costs more: query('alice') or scan(pk=='alice') on a 3-item table.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 21
```
