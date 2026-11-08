# Stage 47: Fire every matching EventBridge rule

**Edit:** `sns.py` → `EventBus.put_event`

## Context

More than one EventBridge rule may match one event.

## Your task

Fire every matching EventBridge rule.

## Predict

> How many rule handlers run when two rules match one event?

## Check

```bash
forja test aws-from-scratch --stage 47
```

Next: `forja stage aws-from-scratch 48`
