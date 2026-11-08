# Stage 41: Retry a failed asynchronous handler in the toy's three-attempt policy

**Edit:** `lambda_svc.py` → `LambdaService.invoke_async`

## Context

An asynchronous handler error can trigger another attempt.

## Your task

Retry a failed asynchronous handler in the toy's three-attempt policy.

## Predict

> How many attempts does one failing async event make by default in this toy?

## Check

```bash
forja test aws-from-scratch --stage 41
```

Next: `forja stage aws-from-scratch 42`
