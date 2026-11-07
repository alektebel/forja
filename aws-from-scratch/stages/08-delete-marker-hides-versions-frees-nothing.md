# Stage 8: delete marker hides versions, frees nothing

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage, lifecycle

## The mechanism

In a versioned bucket, DELETE pushes a delete marker: plain GET then 404s, but every version is still stored — only deleting a version_id frees bytes.

## Why the requirement is what it is

Versioning makes buckets immutable-by-default, and DELETE must be undoable, so it appends instead of mutating. Consequence: 'I emptied the bucket' and 'the bill went down' are different claims — the bytes sit there, billable, under the marker.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 8
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 8
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> what GET returns after a delete marker is added.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 9
```
