# S10 — Ride-Hailing Geo Matching

> **After:** W6 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/consistent_hash.py`, `hot_partition_mitigation.py`

## Problem

Match riders with nearby available drivers.

## Functional requirements

- Drivers send their location every few seconds
- Find the nearest available drivers for a rider
- Assign one driver exactly once

## Non-functional requirements

- Match in under 1 s
- Location data can be seconds stale
- A driver is never assigned to two riders

## Scale to design for

- 1 M active drivers, update every 4 s
- City centres concentrate most of the load

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Geohash, quadtree or H3 — how do you index moving points?
- Where do location updates go, and are they ever persisted?
- How do you make the assignment atomic?
- What happens to a busy city cell — the hot partition again?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- Kinesis Data Streams
- ElastiCache geospatial commands
- DynamoDB conditional writes
- Location Service (compare)

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Synthetic drivers streaming locations into a geo index, with atomic assignment under concurrent riders.
