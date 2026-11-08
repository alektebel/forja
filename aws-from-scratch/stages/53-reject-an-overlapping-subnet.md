# Stage 53: Reject an overlapping subnet

**Edit:** `vpc.py` → `Vpc.add_subnet`

## Context

Overlapping subnets make address assignment ambiguous.

## Your task

Reject an overlapping subnet.

## Predict

> Can 10.0.1.128/25 be added after 10.0.1.0/24?

## Check

```bash
forja test aws-from-scratch --stage 53
```

Next: `forja stage aws-from-scratch 54`
