# Stage 28: Query only a named partition key

**Edit:** `dynamodb.py` → `Table.query`

## Context

A query is routed by its partition key.

## Your task

Query only a named partition key.

## Predict

> Does query(alice) return any bob items?

## Check

```bash
forja test aws-from-scratch --stage 28
```

Next: `forja stage aws-from-scratch 29`
