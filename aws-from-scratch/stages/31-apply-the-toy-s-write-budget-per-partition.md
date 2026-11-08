# Stage 31: Apply the toy's write budget per partition

**Edit:** `dynamodb.py` → `Partition.consume`

## Context

This toy assigns a fixed write budget to each partition.

## Your task

Apply the toy's write budget per partition.

## Predict

> With a budget of 10, what happens on the 11th same-partition write?

## Check

```bash
forja test aws-from-scratch --stage 31
```

Next: `forja stage aws-from-scratch 32`
