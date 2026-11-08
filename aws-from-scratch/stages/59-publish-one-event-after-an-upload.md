# Stage 59: Publish one event after an upload

**Edit:** `capstone.py` → `upload`

## Context

An upload can publish a notification after storing an object.

## Your task

The system setup is supplied. Implement upload so it stores one encrypted object and publishes one notification. The topic has no queue subscriber yet.

## Predict

> After uploading one PDF, how many events has the topic published?

## Check

```bash
forja test aws-from-scratch --stage 59
```

Next: `forja stage aws-from-scratch 60`
