# Stage 56: Permit reply traffic for an allowed security-group connection

**Edit:** `vpc.py` → `test_connection`

## Context

A security group tracks allowed connection state.

## Your task

Permit reply traffic for an allowed security-group connection.

## Predict

> Does a reply need its own outbound security-group rule?

## Check

```bash
forja test aws-from-scratch --stage 56
```

Next: `forja stage aws-from-scratch 57`
