# Stage 30: Charge the toy's strong read twice its eventual read

**Edit:** `dynamodb.py` → `Table.get_item`

## Context

A strong read has a higher read-unit cost in this toy.

## Your task

Charge the toy's strong read twice its eventual read.

## Predict

> How many read units does a strong read use relative to an eventual read?

## Check

```bash
forja test aws-from-scratch --stage 30
```

Next: `forja stage aws-from-scratch 31`
