# Stage 58: Evaluate NACL rules in number order

**Edit:** `vpc.py` → `NetworkAcl.evaluate`

## Context

NACL rules have numeric priority.

## Your task

Evaluate NACL rules in number order.

## Predict

> If allow 200 is added before deny 100, which rule wins for SSH?

## Check

```bash
forja test aws-from-scratch --stage 58
```

Next: `forja stage aws-from-scratch 59`
