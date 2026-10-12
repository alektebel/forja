# S7 — Payments Ledger

> **After:** W3, W7 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/idempotency_keys.py`; `dynamo-paper` (why not eventual consistency here)

## Problem

Record money movements between accounts so that balances are always explainable.

## Functional requirements

- Transfer between accounts
- Balance and statement per account
- Integrate with an external payment provider via webhooks

## Non-functional requirements

- Never lose or double-apply a movement
- Every balance is reproducible from the entries
- Auditable: who did what, when

## Scale to design for

- 2 k transfers/s peak
- Retention 10 years
- Provider webhooks arrive late, twice, or out of order

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Why double-entry, and what invariant does it let you check?
- Where is the transaction boundary, and which database gives you it?
- How do you publish 'transfer done' to other services without a dual write? (outbox)
- What does an idempotency key cover: the request, the transfer, or the webhook?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- Aurora PostgreSQL
- DynamoDB transactions (compare)
- EventBridge
- SQS FIFO
- KMS
- CloudTrail / QLDB-style audit (and what replaced QLDB)

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Double-entry tables with an outbox and an idempotent webhook handler; a replay test that must leave balances unchanged.
