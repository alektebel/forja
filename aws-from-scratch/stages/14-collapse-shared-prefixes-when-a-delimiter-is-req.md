# Stage 14: Collapse shared prefixes when a delimiter is requested

**Edit:** `s3.py` → `S3.list_objects`

## Context

A delimiter groups keys only during a listing.

## Your task

Collapse shared prefixes when a delimiter is requested.

## Predict

> What appears under common_prefixes when those keys are listed with / as delimiter?

## Check

```bash
forja test aws-from-scratch --stage 14
```

Next: `forja stage aws-from-scratch 15`
