# Stage 6: Intersect identity permissions with a permissions boundary

**Edit:** `iam.py` → `evaluate_with_boundary`

## Context

A boundary caps an identity policy without becoming a grant itself.

## Your task

Intersect identity permissions with a permissions boundary.

## Predict

> Can a boundary grant GetObject to an identity with no Allow?

## Check

```bash
forja test aws-from-scratch --stage 6
```

Next: `forja stage aws-from-scratch 7`
