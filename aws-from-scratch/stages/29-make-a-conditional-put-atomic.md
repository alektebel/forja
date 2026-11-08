# Stage 29: Make a conditional put atomic

**Edit:** `dynamodb.py` → `Table.put_item`

## Context

A conditional write protects a value from an unwanted overwrite.

## Your task

Make a conditional put atomic.

## Predict

> After a conditional create fails, what value remains?

## Check

```bash
forja test aws-from-scratch --stage 29
```

Next: `forja stage aws-from-scratch 30`
