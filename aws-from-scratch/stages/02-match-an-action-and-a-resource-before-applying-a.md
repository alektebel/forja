# Stage 2: Match an action and a resource before applying a statement

**Edit:** `iam.py` → `evaluate`

## Context

A policy statement applies only to its named action and resource.

## Your task

Match an action and a resource before applying a statement.

## Predict

> Does GetObject on bucket A pass? What about PutObject or bucket B?

## Check

```bash
forja test aws-from-scratch --stage 2
```

Next: `forja stage aws-from-scratch 3`
