# Stage 4: objects, ETags and multipart

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage

## The mechanism

Objects carry an ETag (MD5 simple, part-hash multipart); multipart assembles the parts in order.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 4
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 4
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the ETag of a two-part multipart upload.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 5
```
