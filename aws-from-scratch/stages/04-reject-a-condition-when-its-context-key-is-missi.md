# Stage 4: Reject a condition when its context key is missing

**Edit:** `iam.py` → `evaluate_condition`

## Context

A condition cannot be checked when its input is absent.

## Your task

Reject a condition when its context key is missing.

## Predict

> What happens when a required source IP is absent?

## Check

```bash
forja test aws-from-scratch --stage 4
```

Next: `forja stage aws-from-scratch 5`
