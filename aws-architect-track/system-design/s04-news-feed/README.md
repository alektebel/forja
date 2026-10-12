# S4 — News Feed / Timeline

> **After:** W3 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/hot_partition_mitigation.py`, `cache.py`, `leaderboard.py`

## Problem

Show each user a feed of posts from the accounts they follow.

## Functional requirements

- Post
- Follow / unfollow
- Read a feed, newest first, paginated

## Non-functional requirements

- Feed read p99 under 200 ms
- A post appears in followers' feeds within seconds, not instantly
- Accounts with millions of followers must not melt the system

## Scale to design for

- 200 M daily users, 2 posts/day average, 50 feed reads/day
- Median 200 followees; some accounts have 50 M followers

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Fan-out on write, on read, or hybrid — and where is the threshold?
- What exactly is cached per user, and how big is it?
- How does pagination stay stable while new posts arrive?
- What is the partition key of each table, and which one gets hot?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- DynamoDB
- ElastiCache
- SQS / Kinesis for fan-out
- S3 + CloudFront for media

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Fan-out on write with a celebrity threshold, measured on a synthetic follower graph.
