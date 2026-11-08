# Stage 7: Check a role's trust policy when assuming it

**Edit:** `iam.py` → `assume_role`

## Context

A role controls who may assume it through a trust policy.

## Your task

Check a role's trust policy when assuming it.

## Predict

> Can a caller assume a role when their policy allows it but the role trust rejects them?

## Check

```bash
forja test aws-from-scratch --stage 7
```

Next: `forja stage aws-from-scratch 8`
