# S11 — Recommendation Serving

> **After:** W12, W13 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `evals-from-scratch` (offline vs online metrics)

## Problem

Serve personalised recommendations in real time from a model trained offline.

## Functional requirements

- Top-N items for a user and context
- Fresh signals (last clicks) affect results within minutes
- A/B test two models

## Non-functional requirements

- p99 under 100 ms including feature lookup
- Same features at training and serving time
- A model failure falls back to something sensible

## Scale to design for

- 20 k requests/s
- 10 M users, 1 M items

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Two-stage: candidate retrieval then ranking — why, and where does each run?
- Which features are precomputed, which are real-time, and where do they live?
- How do you split traffic for an A/B test and measure it honestly?
- What is the fallback when the model endpoint is slow?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- SageMaker Feature Store (online)
- SageMaker endpoints
- Kinesis for events
- ElastiCache
- OpenSearch / vector search for candidates

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Online feature lookup + endpoint call with a timeout and fallback, latency budget measured per hop.
