# Stage 34: Initialize an execution environment on first use

**Edit:** `lambda_svc.py` → `LambdaService.invoke / LambdaService._acquire_environment`

## Context

An execution environment has an initialization cost.

## Your task

Function registration is supplied. Make the first LambdaService.invoke create an environment and include its init cost.

## Predict

> Does the first invocation include environment initialization cost?

## Check

```bash
forja test aws-from-scratch --stage 34
```

Next: `forja stage aws-from-scratch 35`
