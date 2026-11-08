# Stage 35: Reuse an environment between invocations

**Edit:** `lambda_svc.py` → `LambdaService._acquire_environment`

## Context

A reused execution environment retains memory between calls.

## Your task

Reuse an environment between invocations.

## Predict

> What does a counter stored outside the handler return on the second call?

## Check

```bash
forja test aws-from-scratch --stage 35
```

Next: `forja stage aws-from-scratch 36`
