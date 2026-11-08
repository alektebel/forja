# Stage 42: Send an exhausted asynchronous event to the dead-letter queue

**Edit:** `lambda_svc.py` → `LambdaService.invoke_async`

## Context

An exhausted asynchronous event can be preserved for inspection.

## Your task

Send an exhausted asynchronous event to the dead-letter queue.

## Predict

> Where does an async event go after its last failed attempt?

## Check

```bash
forja test aws-from-scratch --stage 42
```

Next: `forja stage aws-from-scratch 43`
