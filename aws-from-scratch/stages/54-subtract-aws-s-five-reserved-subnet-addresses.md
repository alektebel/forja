# Stage 54: Subtract AWS's five reserved subnet addresses

**Edit:** `vpc.py` → `Cidr.usable_hosts`

## Context

AWS reserves five addresses in each VPC subnet.

## Your task

Subtract AWS's five reserved subnet addresses.

## Predict

> How many usable addresses remain in an AWS /28 subnet?

## Check

```bash
forja test aws-from-scratch --stage 54
```

Next: `forja stage aws-from-scratch 55`
