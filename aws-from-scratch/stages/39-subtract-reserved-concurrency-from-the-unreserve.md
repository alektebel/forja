# Stage 39: Subtract reserved concurrency from the unreserved pool

**Edit:** `lambda_svc.py` → `LambdaService.unreserved_capacity`

## Context

Reserved concurrency reduces the shared unreserved pool.

## Your task

Subtract reserved concurrency from the unreserved pool.

## Predict

> After reserving 6 of 10 slots, how many can an unrelated function use?

## Check

```bash
forja test aws-from-scratch --stage 39
```

Next: `forja stage aws-from-scratch 40`
