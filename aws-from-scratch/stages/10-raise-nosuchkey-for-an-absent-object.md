# Stage 10: Raise `NoSuchKey` for an absent object

**Edit:** `s3.py` → `S3.get_object`

## Context

An empty object and a missing key are different states.

## Your task

Raise `NoSuchKey` for an absent object.

## Predict

> How can GET distinguish an empty object from an absent key?

## Check

```bash
forja test aws-from-scratch --stage 10
```

Next: `forja stage aws-from-scratch 11`
