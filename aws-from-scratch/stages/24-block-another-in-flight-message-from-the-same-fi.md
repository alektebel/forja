# Stage 24: Block another in-flight message from the same FIFO group

**Edit:** `sqs.py` → `Queue.receive`

## Context

FIFO ordering serializes work within one group.

## Your task

Block another in-flight message from the same FIFO group.

## Predict

> How many A-group messages can one FIFO batch receive at once?

## Check

```bash
forja test aws-from-scratch --stage 24
```

Next: `forja stage aws-from-scratch 25`
