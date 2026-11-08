# Stage 8: Give an assumed session the role's permissions

**Edit:** `iam.py` → `assume_role`

## Context

An assumed role uses the role's permissions during the session.

## Your task

Give an assumed session the role's permissions.

## Predict

> Which permissions does a successful assumed session carry?

## Check

```bash
forja test aws-from-scratch --stage 8
```

Next: `forja stage aws-from-scratch 9`
