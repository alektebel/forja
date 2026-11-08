# Stage 1: Implicit deny

**Edit:** `iam.py` → `evaluate`

## Context

An IAM request starts denied until a policy grants it.

## Your task

In iam.py, replace the raise in evaluate() with an implicit-deny Decision when policies is empty. One return statement is enough.

## Predict

> What is allowed for a request with no policies?

## Check

```bash
forja test aws-from-scratch --stage 1
```

Next: `forja stage aws-from-scratch 2`
