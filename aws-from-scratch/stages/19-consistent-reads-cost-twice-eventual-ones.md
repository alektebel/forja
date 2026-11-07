# Stage 19: consistent reads cost twice eventual ones

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `dynamodb.py`
**Tags:** capacity

## The mechanism

Table capacity divides ACROSS partitions: 40 WCU on 4 partitions is 10 per partition, so 30 writes to ONE key throttle after 10 — with the table 75% idle.

## Why the requirement is what it is

Adding capacity does not help a hot key: the limit is per partition, and the key decides the partition. The fix is the data model (spread the key), not the bill — the most common DynamoDB surprise.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 19
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 19
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many of 30 same-key writes succeed (40 WCU, 4 partitions).

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 20
```
