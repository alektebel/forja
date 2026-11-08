# Stage 23: Move a repeatedly received message to a dead-letter queue

**Edit:** `sqs.py` → `Queue.receive`

## Context

A poison message needs a place to go after repeated attempts.

## Your task

Move a repeatedly received message to a dead-letter queue.

## Predict

> Where is a poison message after it passes the receive limit?

## Check

```bash
forja test aws-from-scratch --stage 23
```

Next: `forja stage aws-from-scratch 24`
