# Stage 7: delimiter invents folders at list time

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage

## The mechanism

Listing: without a delimiter every key returns flat; with delimiter='/', shared prefixes collapse into common_prefixes.

## Why the requirement is what it is

Folders do not exist in S3 — reports/2024/q1.csv is one opaque key. The delimiter INVENTS folders at list time, which is why an empty folder cannot exist and why 'renaming a folder' is O(every object under it).


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 7
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 7
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what list_objects returns for a/1.txt, a/2.txt, top.txt with delimiter='/'.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 8
```
