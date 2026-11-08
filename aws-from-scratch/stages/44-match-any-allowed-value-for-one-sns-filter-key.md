# Stage 44: Match any allowed value for one SNS filter key

**Edit:** `sns.py` → `matches_filter`

## Context

A filter key can admit several alternative values.

## Your task

Match any allowed value for one SNS filter key.

## Predict

> Does staging match a filter allowing prod or staging?

## Check

```bash
forja test aws-from-scratch --stage 44
```

Next: `forja stage aws-from-scratch 45`
