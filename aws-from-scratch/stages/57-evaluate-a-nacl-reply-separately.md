# Stage 57: Evaluate a NACL reply separately

**Edit:** `vpc.py` → `test_connection`

## Context

A NACL checks the reply packet separately.

## Your task

Evaluate a NACL reply separately.

## Predict

> Does a NACL allow the reply when only port 443 is open outbound?

## Check

```bash
forja test aws-from-scratch --stage 57
```

Next: `forja stage aws-from-scratch 58`
