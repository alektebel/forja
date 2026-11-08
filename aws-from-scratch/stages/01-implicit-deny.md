# Stage 1: Implicit deny

**Edit:** `iam.py` → `evaluate`

## Context

A request with no policies has no Allow statement, so IAM denies it by default. The supplied Decision class takes an allowed boolean and a reason string.

## Your task

In iam.py, find evaluate() and replace its raise NotImplementedError with the return statement below. The stage-1 checker passes an empty policies list. You will handle matching statements in stage 2.

## Example edit

```python
return Decision(False, "implicit deny")
```

## Predict

> What is allowed for a request with no policies?

## Check

```bash
forja test aws-from-scratch --stage 1
```

Next: `forja stage aws-from-scratch 2`
