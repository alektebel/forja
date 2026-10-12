# S12 — Multi-Tenant LLM Platform

> **After:** W13, W16 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `context-caching`, `agent-harness-from-scratch`, phase I (I3, I4, I11)

## Problem

An internal platform that serves LLM capabilities to many teams.

## Functional requirements

- One API for several models (managed and self-hosted)
- Per-team quotas and cost reporting
- Prompt and response caching
- Audit log

## Non-functional requirements

- TTFT and ITL SLOs per tier
- No team can exhaust another's capacity
- No prompt data leaves the account boundary you choose

## Scale to design for

- 200 teams, 3 k requests/s peak, long-tailed prompt sizes
- Mix of chat, batch and agent traffic

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Managed models vs self-hosted on SageMaker/EKS: where is the break-even?
- Where do quotas count tokens, and what happens mid-stream when one runs out?
- Which caches are exact and which can be wrong (semantic)?
- How do you route by cost and complexity without hurting quality — and how do you know?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- Bedrock
- SageMaker / EKS with GPU nodes
- API Gateway / ALB
- DynamoDB for quotas
- ElastiCache
- CloudWatch + Cost and Usage Report

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): A gateway with per-team token quotas and an exact prompt cache in front of one managed model; quota exhaustion tested mid-stream.
