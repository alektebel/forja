# Stage 3: Give a matching explicit Deny precedence over Allow

**Edit:** `iam.py` → `evaluate`

## Context

Several policy statements may apply to the same request.

## Your task

Give a matching explicit Deny precedence over Allow.

## Predict

> If Allow and Deny both match, does reversing policy order change the result?

## Check

```bash
forja test aws-from-scratch --stage 3
```

Next: `forja stage aws-from-scratch 4`
