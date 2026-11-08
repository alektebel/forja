# Stage 62: Authorize before the upload's first side effect

**Edit:** `capstone.py` → `upload`

## Context

Authorization must happen before an upload's first side effect.

## Your task

Authorize before the upload's first side effect.

## Predict

> What storage or queue side effects remain after a denied upload?

## Check

```bash
forja test aws-from-scratch --stage 62
```

Next: `forja stage aws-from-scratch 63`
