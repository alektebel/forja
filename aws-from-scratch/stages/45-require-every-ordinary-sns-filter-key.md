# Stage 45: Require every ordinary SNS filter key

**Edit:** `sns.py` → `matches_filter`

## Context

Ordinary SNS filter keys must all be present and match.

## Your task

Require every ordinary SNS filter key.

## Predict

> Does a message missing environment match a filter requiring it?

## Check

```bash
forja test aws-from-scratch --stage 45
```

Next: `forja stage aws-from-scratch 46`
