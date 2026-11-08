# Stage 16: Append a delete marker for a plain delete in a versioned bucket

**Edit:** `s3.py` → `S3.delete_object`

## Context

A delete marker hides a versioned key without erasing history.

## Your task

Append a delete marker for a plain delete in a versioned bucket.

## Predict

> What does plain GET do after a delete marker is written?

## Check

```bash
forja test aws-from-scratch --stage 16
```

Next: `forja stage aws-from-scratch 17`
