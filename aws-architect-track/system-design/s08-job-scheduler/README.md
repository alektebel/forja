# S8 — Distributed Job Scheduler

> **After:** W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/message_queue.py`, `circuit_breaker.py`

## Problem

Run millions of scheduled and recurring jobs for many tenants.

## Functional requirements

- One-off and cron-style jobs
- Retries with backoff
- Job status and history
- Cancel a job

## Non-functional requirements

- A job runs at least once, close to its time
- One tenant cannot starve the others
- A worker dying mid-job is detected and the job reassigned

## Scale to design for

- 10 M scheduled jobs, 5 k firing per second at peak minutes
- Job duration from seconds to an hour

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- How do you find the jobs due now without scanning everything?
- Lease vs lock: how does a worker claim a job, and what happens when it dies?
- How is fairness between tenants enforced?
- When is EventBridge Scheduler enough, and when do you need your own?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- EventBridge Scheduler
- Step Functions
- SQS with visibility timeout
- DynamoDB with TTL / time-bucketed keys
- ECS / Lambda workers

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Time-bucketed job table + lease-based workers; kill a worker mid-job and measure reassignment time.
