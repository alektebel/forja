# Stage 19: Make an undeleted message visible after the interval

**Edit:** `sqs.py` → `Queue.receive`

## Context

A consumer may crash before deleting a message.

## Your task

Make an undeleted message visible after the interval.

## Predict

> Can that message be received at t=11 if it was not deleted?

## Check

```bash
forja test aws-from-scratch --stage 19
```

Next: `forja stage aws-from-scratch 20`
