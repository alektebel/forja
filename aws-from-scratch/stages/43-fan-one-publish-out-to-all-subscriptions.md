# Stage 43: Fan one publish out to all subscriptions

**Edit:** `sns.py` → `Topic.publish / Topic._deliver`

## Context

SNS sends a copy of one publication to each subscriber.

## Your task

Topic.subscribe is supplied. Implement publish and delivery so one message reaches every subscribed queue. Filtering arrives next.

## Predict

> How many copies arrive when a topic has two queue subscribers?

## Check

```bash
forja test aws-from-scratch --stage 43
```

Next: `forja stage aws-from-scratch 44`
