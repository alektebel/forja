# Stage 22: Change visibility relative to the call time

**Edit:** `sqs.py` → `Queue.change_visibility`

## Context

Slow work can renew the visibility period.

## Your task

Change visibility relative to the call time.

## Predict

> At t=11, is a lease extended by 60 seconds at t=5 visible?

## Check

```bash
forja test aws-from-scratch --stage 22
```

Next: `forja stage aws-from-scratch 23`
