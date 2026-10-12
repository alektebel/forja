# S3 — Notification System

> **After:** W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/message_queue.py`, `idempotency_keys.py`, `circuit_breaker.py`

## Problem

Send email, SMS and push notifications triggered by many internal services.

## Functional requirements

- Any service can request a notification to a user
- User preferences and quiet hours are respected
- Delivery status is queryable

## Non-functional requirements

- At-least-once delivery without user-visible duplicates
- A slow or failing provider must not block the others
- Priority traffic (security codes) is never stuck behind marketing

## Scale to design for

- 10 M notifications/day, bursts of 50x during campaigns
- Three external providers with their own rate limits

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- One queue or one per channel and priority — and why?
- Where does deduplication happen, and for how long do you remember an id?
- How do you respect a provider's rate limit with many consumers?
- What is retried, how many times, and what goes to a DLQ for a human?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- EventBridge
- SNS
- SQS (FIFO vs standard) + DLQ
- Lambda / ECS workers
- DynamoDB for preferences and status
- Amazon SES / End User Messaging

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Two channels with separate priority queues, a fake provider that fails 20% of the time, and dedup measured.
