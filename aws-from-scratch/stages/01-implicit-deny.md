# Stage 1: Implicit deny

**Edit:** `iam.py` → `evaluate`

## Context

A request with no policies has no Allow statement, so IAM denies it by default. The supplied Decision class takes an allowed boolean and a reason string.

## Your task

In iam.py, replace the raise in evaluate() with one return statement: Decision(False, "implicit deny"). The stage-1 checker calls evaluate with an empty policies list; matching statements comes in stage 2.

## Predict

> What is allowed for a request with no policies?

## Check

```bash
forja test aws-from-scratch --stage 1
```

Next: `forja stage aws-from-scratch 2`
