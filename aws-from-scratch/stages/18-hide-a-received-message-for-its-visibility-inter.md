# Stage 18: Hide a received message for its visibility interval

**Edit:** `sqs.py` → `Queue.receive`

## Context

Receiving an SQS message temporarily hides it from other consumers.

## Your task

Queue.send is supplied. Implement receive so one message becomes invisible until its visibility timeout. Lease expiry arrives in stage 19.

## Predict

> Can a second consumer receive the message five seconds after the first?

## Check

```bash
forja test aws-from-scratch --stage 18
```

Next: `forja stage aws-from-scratch 19`
