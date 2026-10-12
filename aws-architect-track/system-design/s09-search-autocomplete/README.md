# S9 — Search Autocomplete

> **After:** W3 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/cache.py`, `data_locality.py`

## Problem

Suggest completions as the user types.

## Functional requirements

- Top suggestions for a prefix
- Suggestions reflect recent popularity
- Filter out blocked terms

## Non-functional requirements

- Under 50 ms per keystroke end to end
- Updates within an hour are fine
- Works per region and language

## Scale to design for

- 10 B queries/day, each keystroke a request
- Vocabulary of 100 M distinct queries

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- Trie in memory, precomputed top-k per prefix, or a search engine — what does each cost?
- How are popularity counts aggregated and how often is the index rebuilt?
- What can the client and the CDN cache?
- How do you remove a term everywhere quickly?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- OpenSearch
- ElastiCache
- Kinesis + Firehose for query logs
- Athena / Glue for aggregation
- CloudFront

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Precomputed top-k per prefix built from a query log in S3, served from a cache; latency measured.
