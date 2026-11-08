# Stage 33: Apply a scan filter after reading items

**Edit:** `dynamodb.py` → `Table.scan`

## Context

A scan reads items before applying its filter.

## Your task

Apply a scan filter after reading items.

## Predict

> If a scan returns one of three rows, how many rows does it count as scanned?

## Check

```bash
forja test aws-from-scratch --stage 33
```

Next: `forja stage aws-from-scratch 34`
