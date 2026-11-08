# Stage 12: Compute a multipart ETag from part digests

**Edit:** `s3.py` → `compute_etag`

## Context

Multipart ETags describe parts rather than a full-body digest.

## Your task

Compute a multipart ETag from part digests.

## Predict

> Will the ETag for two parts equal the MD5 of their combined body?

## Check

```bash
forja test aws-from-scratch --stage 12
```

Next: `forja stage aws-from-scratch 13`
