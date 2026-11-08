# Stage 13: List object keys as a flat sequence

**Edit:** `s3.py` → `S3.list_objects`

## Context

S3 stores keys in a flat namespace.

## Your task

List object keys as a flat sequence.

## Predict

> How many keys appear when listing a/1, a/2, and top without a delimiter?

## Check

```bash
forja test aws-from-scratch --stage 13
```

Next: `forja stage aws-from-scratch 14`
