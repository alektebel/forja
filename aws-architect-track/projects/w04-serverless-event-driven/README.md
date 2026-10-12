# W4 — Serverless, Event-Driven

> **Exam:** SAA-C03 — Resilient / High-Performing  
> **After:** W0  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/sqs.py`, `lambda_svc.py`, `dynamodb.py`, `sns.py`; `system-design/idempotency_keys.py`

## Goal

An event-driven backend where redelivery is the design. Prove that duplicates and poison messages are handled, not hoped away.

## What you build

- API Gateway → Lambda → DynamoDB
- SQS queue with a DLQ and `maxReceiveCount`; Lambda consumer with partial batch failure reporting
- SNS or EventBridge fan-out to two consumers with a filter policy
- Idempotent writes with a DynamoDB conditional put on an idempotency key

## Acceptance — measured, not "it deployed"

- [ ] A poison message lands in the DLQ after exactly `maxReceiveCount` attempts
- [ ] Delivering the same message twice produces one write
- [ ] A message without the filtered attribute reaches neither filtered consumer
- [ ] A burst above reserved concurrency throttles instead of overloading DynamoDB

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Why must the SQS visibility timeout be longer than the Lambda timeout?
- What does partial batch failure change compared with failing the whole batch?
- Where exactly can a duplicate come from in this pipeline? List every hop.

## Layout (to create when you start)

```
w04-serverless-event-driven/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
