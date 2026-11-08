# Stage 36: Replace an expired toy environment

**Edit:** `lambda_svc.py` → `LambdaService._acquire_environment`

## Context

The toy's deterministic TTL lets us observe environment replacement.

## Your task

Replace an expired toy environment.

## Predict

> What value does that counter return after the toy TTL expires?

## Check

```bash
forja test aws-from-scratch --stage 36
```

Next: `forja stage aws-from-scratch 37`
