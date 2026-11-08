# Stage 21: Delete the message with its current handle

**Edit:** `sqs.py` → `Queue.delete`

## Context

Acknowledging a message is separate from receiving it.

## Your task

Delete the message with its current handle.

## Predict

> Will the message return after its current handle is deleted?

## Check

```bash
forja test aws-from-scratch --stage 21
```

Next: `forja stage aws-from-scratch 22`
