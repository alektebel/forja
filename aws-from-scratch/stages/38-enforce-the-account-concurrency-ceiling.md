# Stage 38: Enforce the account concurrency ceiling

**Edit:** `lambda_svc.py` → `LambdaService.concurrent_invoke`

## Context

Lambda concurrency limits simultaneous work.

## Your task

Enforce the account concurrency ceiling.

## Predict

> At concurrency 10, how many of 15 simultaneous calls run?

## Check

```bash
forja test aws-from-scratch --stage 38
```

Next: `forja stage aws-from-scratch 39`
