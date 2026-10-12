# S2 — Distributed Rate Limiter

> **After:** W3, W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/rate_limiter.py`, `throttling.py`

## Problem

Limit requests per API key across a fleet of stateless servers.

## Functional requirements

- Per-key limits with different tiers
- Return 429 with a retry hint
- Limits change without a deploy

## Non-functional requirements

- Adds under 5 ms to the request path
- A limiter outage must not take the API down — decide fail-open or fail-closed and defend it
- Small over-admission is acceptable; large is not

## Scale to design for

- 50 k requests/s peak across 40 servers
- 1 M API keys, heavy-tailed usage

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Token bucket, sliding window log, or sliding window counter — what does each cost in memory and accuracy?
- Where does the counter live, and what happens to accuracy when it is local vs central?
- How do you make check-and-decrement atomic?
- What does API Gateway usage plans already give you, and where does it stop?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- API Gateway usage plans
- ElastiCache (atomic scripts)
- DynamoDB conditional updates
- WAF rate-based rules

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): A central counter in ElastiCache with an atomic script, load-tested to measure over-admission.
