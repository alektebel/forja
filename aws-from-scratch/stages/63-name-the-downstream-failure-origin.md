# Stage 63: Name the downstream failure origin

**Edit:** `capstone.py` → `failure_origin`

## Context

A downstream database limit can appear as a worker failure.

## Your task

Implement failure_origin: return "dynamodb" when the worker failed and a database partition reports throttling; otherwise return None.

## Predict

> When the worker fails and a partition reports throttling, what should failure_origin return?

## Check

```bash
forja test aws-from-scratch --stage 63
```

You finished the course.
