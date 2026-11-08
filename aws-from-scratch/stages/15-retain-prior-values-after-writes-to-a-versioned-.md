# Stage 15: Retain prior values after writes to a versioned key

**Edit:** `s3.py` → `S3.put_object / S3.get_object`

## Context

Versioning preserves earlier object values.

## Your task

Retain prior values after writes to a versioned key.

## Predict

> Can the first version still be read after writing a second version?

## Check

```bash
forja test aws-from-scratch --stage 15
```

Next: `forja stage aws-from-scratch 16`
