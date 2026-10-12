# S5 — Real-Time Chat

> **After:** W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/session_stickiness.py`, `eventual_consistency.py`

## Problem

One-to-one and group chat with online presence.

## Functional requirements

- Send and receive messages in real time
- Message history
- Presence (online / last seen)
- Delivered / read receipts

## Non-functional requirements

- Per-conversation ordering
- No message lost once acknowledged
- Reconnects after network changes without duplicates

## Scale to design for

- 50 M daily users, 40 messages/user/day
- Groups up to 500 members
- Peak 5 M concurrent connections

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- How does the server that holds user B's connection learn about a message sent through another server?
- Where does ordering come from: client clock, server timestamp, or a per-conversation sequence?
- How is presence kept fresh without a write per heartbeat per user?
- What is acknowledged, by whom, and when can the sender stop retrying?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- API Gateway WebSocket APIs
- Lambda / ECS
- DynamoDB (connections, messages)
- ElastiCache pub/sub
- SNS for offline push

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): WebSocket API with a connection registry and per-conversation sequence numbers; ordering tested under concurrent senders.
