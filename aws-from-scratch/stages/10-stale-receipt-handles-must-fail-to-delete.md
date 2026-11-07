# Stage 10: stale receipt handles must fail to delete

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging, lifecycle

## The mechanism

Each receive gets its OWN receipt handle; after the lease expires, the FIRST consumer's delete must fail.

## Why the requirement is what it is

If both consumers shared one Message object, the second receive would overwrite the first's handle and the stale delete would silently succeed — deleting work someone else is still doing. Distinct handles make every delete prove its lease is current.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 10
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 10
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether consumer A's delete succeeds after B's redelivery.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 11
```
