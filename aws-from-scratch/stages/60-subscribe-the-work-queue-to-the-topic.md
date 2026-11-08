# Stage 60: Subscribe the work queue to the topic

**Edit:** `capstone.py` → `build`

## Context

An SNS subscription can deliver that notification to SQS.

## Your task

In build(), subscribe the processing queue to the uploads topic with the PDF filter policy.

## Predict

> Is that event visible in SQS after the queue is subscribed?

## Check

```bash
forja test aws-from-scratch --stage 60
```

Next: `forja stage aws-from-scratch 61`
