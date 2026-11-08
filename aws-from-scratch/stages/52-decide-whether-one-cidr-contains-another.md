# Stage 52: Decide whether one CIDR contains another

**Edit:** `vpc.py` → `Cidr.contains`

## Context

CIDR containment describes an address range inside another.

## Your task

Decide whether one CIDR contains another.

## Predict

> Does 10.0.0.0/16 contain 10.0.1.0/24 or 10.1.0.0/24?

## Check

```bash
forja test aws-from-scratch --stage 52
```

Next: `forja stage aws-from-scratch 53`
