# Stage 26: Suppress a duplicate deduplication ID inside the toy window

**Edit:** `sqs.py` → `Queue.send`

## Context

A bounded deduplication window absorbs producer retries.

## Your task

Suppress a duplicate deduplication ID inside the toy window.

## Predict

> What happens to a repeated dedup ID at t=10 and t=400?

## Check

```bash
forja test aws-from-scratch --stage 26
```

Next: `forja stage aws-from-scratch 27`
