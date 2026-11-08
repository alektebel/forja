# Stage 25: Let a different FIFO group progress

**Edit:** `sqs.py` → `Queue.receive`

## Context

Different FIFO groups can proceed independently.

## Your task

Let a different FIFO group progress.

## Predict

> Can group B progress while a group A message is in flight?

## Check

```bash
forja test aws-from-scratch --stage 25
```

Next: `forja stage aws-from-scratch 26`
