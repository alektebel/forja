# Stage 32: Spread distinct partition keys across partitions

**Edit:** `dynamodb.py` → `Table._partition`

## Context

A stable hash lets different keys use different partitions.

## Your task

Replace the single-slot starting point in Table._partition with a stable hash of the partition key.

## Predict

> Can 20 distinct keys fit when each of four partitions allows 10 writes?

## Check

```bash
forja test aws-from-scratch --stage 32
```

Next: `forja stage aws-from-scratch 33`
