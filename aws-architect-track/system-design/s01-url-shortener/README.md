# S1 — URL Shortener

> **After:** W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/url_shortener.py`, `consistent_hash.py`

## Problem

Turn long URLs into short codes and redirect, at a read/write ratio far from 1:1.

## Functional requirements

- Create a short code for a URL, optionally with a custom alias and an expiry
- Redirect a code to its URL
- Count clicks per code

## Non-functional requirements

- Redirect p99 well under 100 ms from the user's region
- Codes never collide; a code is never reused while live
- Click counts may lag; redirects may not fail

## Scale to design for

- 100 M new URLs per month
- Read:write ratio 100:1
- Keep links for 5 years

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- How do you generate codes: hash, counter, or pre-generated pool — and what does each do under concurrency?
- Where does the redirect get served from, and what is the cache key?
- 301 or 302 — and what does that choice do to your click counts?
- How do counts get written without putting a write on the redirect path?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- API Gateway / ALB
- Lambda / ECS
- DynamoDB
- ElastiCache
- CloudFront + Lambda@Edge or CloudFront Functions
- Kinesis / SQS for click events

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): The redirect path only: CloudFront in front of a DynamoDB-backed Lambda, measured with and without the edge cache.
