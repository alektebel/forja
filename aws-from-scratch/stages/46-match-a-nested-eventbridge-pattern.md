# Stage 46: Match a nested EventBridge pattern

**Edit:** `sns.py` → `matches_event_pattern`

## Context

EventBridge patterns can describe nested event fields.

## Your task

Match a nested EventBridge pattern.

## Predict

> Does a nested pattern for terminated match a running event?

## Check

```bash
forja test aws-from-scratch --stage 46
```

Next: `forja stage aws-from-scratch 47`
