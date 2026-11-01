# Stage 5: prefix listing and delete markers

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage, lifecycle

## The mechanism

Listing uses prefix + delimiter; a delete marker HIDES a version without destroying it.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 5
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 5
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what GET returns after a delete marker is added.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 6
```
