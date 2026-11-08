# Stage 40: Return synchronous handler failure to its caller

**Edit:** `lambda_svc.py` → `LambdaService.invoke`

## Context

Synchronous invocation reports a handler error to its caller.

## Your task

Return synchronous handler failure to its caller.

## Predict

> How many times does a failing synchronous handler run?

## Check

```bash
forja test aws-from-scratch --stage 40
```

Next: `forja stage aws-from-scratch 41`
