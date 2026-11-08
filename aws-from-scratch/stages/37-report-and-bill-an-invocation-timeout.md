# Stage 37: Report and bill an invocation timeout

**Edit:** `lambda_svc.py` → `LambdaService.invoke`

## Context

A timed-out invocation still occupied capacity.

## Your task

Report and bill an invocation timeout.

## Predict

> What error and billed duration result from work exceeding a one-second timeout?

## Check

```bash
forja test aws-from-scratch --stage 37
```

Next: `forja stage aws-from-scratch 38`
