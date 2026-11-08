# Stage 55: Select the longest matching route prefix

**Edit:** `vpc.py` → `Subnet.route_for`

## Context

Routing chooses the most specific matching destination.

## Your task

Select the longest matching route prefix.

## Predict

> Which route wins for 10.1.5.7: /0, /16, or /24?

## Check

```bash
forja test aws-from-scratch --stage 55
```

Next: `forja stage aws-from-scratch 56`
