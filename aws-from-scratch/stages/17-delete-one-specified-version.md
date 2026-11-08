# Stage 17: Delete one specified version

**Edit:** `s3.py` → `S3.delete_object`

## Context

Deleting by version ID removes only the chosen version.

## Your task

Delete one specified version.

## Predict

> Which versions remain after deleting the first version ID?

## Check

```bash
forja test aws-from-scratch --stage 17
```

Next: `forja stage aws-from-scratch 18`
