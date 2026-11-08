# Stage 11: Compute the toy's single-part MD5 ETag

**Edit:** `s3.py` → `compute_etag`

## Context

This toy uses MD5 for an ordinary single-part ETag.

## Your task

Compute the toy's single-part MD5 ETag.

## Predict

> What digest is returned for the single-part body hello?

## Check

```bash
forja test aws-from-scratch --stage 11
```

Next: `forja stage aws-from-scratch 12`
