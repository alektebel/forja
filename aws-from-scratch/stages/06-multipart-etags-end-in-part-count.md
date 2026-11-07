# Stage 6: multipart ETags end in -<part count>

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `s3.py`
**Tags:** storage

## The mechanism

Multipart ETags end in '-<part count>' and are NOT the object's MD5: parts assemble in order at complete().

## Why the requirement is what it is

A multipart ETag is the MD5 of the concatenated PART MD5s — hence the suffix. The practical consequence: you cannot verify a multipart upload by md5-ing your local file, and people burn hours on exactly that.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 6
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 6
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> the ETag of a two-part multipart upload.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 7
```
