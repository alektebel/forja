# Stage 5: Combine condition keys with AND and alternatives for one key with OR

**Edit:** `iam.py` → `evaluate_condition`

## Context

A condition can list alternatives for one key and require another key.

## Your task

Combine condition keys with AND and alternatives for one key with OR.

## Predict

> Does staging/data pass? Does prod/web pass?

## Check

```bash
forja test aws-from-scratch --stage 5
```

Next: `forja stage aws-from-scratch 6`
