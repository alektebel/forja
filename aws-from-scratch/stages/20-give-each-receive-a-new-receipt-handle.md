# Stage 20: Give each receive a new receipt handle

**Edit:** `sqs.py` → `Queue.receive`

## Context

A new receive issues a new handle for the same message.

## Your task

Give each receive a new receipt handle.

## Predict

> Are the receipt handles from two receives equal?

## Check

```bash
forja test aws-from-scratch --stage 20
```

Next: `forja stage aws-from-scratch 21`
