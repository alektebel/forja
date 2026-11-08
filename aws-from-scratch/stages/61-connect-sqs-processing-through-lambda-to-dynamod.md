# Stage 61: Connect SQS processing through Lambda to DynamoDB

**Edit:** `capstone.py` → `drain`

## Context

A worker can consume one queued event and write one row.

## Your task

Connect SQS processing through Lambda to DynamoDB.

## Predict

> How many DynamoDB rows result after draining one queued PDF?

## Check

```bash
forja test aws-from-scratch --stage 61
```

Next: `forja stage aws-from-scratch 62`
