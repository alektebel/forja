# Stage 27: Use both partition and sort values as a composite key

**Edit:** `dynamodb.py` → `Table._keys`

## Context

A composite DynamoDB key has partition and sort components.

## Your task

The table already stores and reads items. Implement Table._keys to extract both parts of each item key.

## Predict

> Do alice/001 and bob/001 hold separate values?

## Check

```bash
forja test aws-from-scratch --stage 27
```

Next: `forja stage aws-from-scratch 28`
