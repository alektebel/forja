# Audit — `aws-from-scratch` stage guides (2026-11-07)

**Criterion:** each stage = one thing to learn; every guide explains in prose
what to do and *why the requirement is what it is*.

**Status: findings fixed.** The course was restructured to the CodeCrafters
shape: 36 single-behavior stages (was 18 multi-topic ones), each with its own
test, a mechanism line, a why paragraph, and a predict prompt.

## What was wrong

1. **Guides were generated without a why.** `stages/*.md` render from
   `codecraft/curriculum.py` action strings, and those were one assertive
   sentence — the README had the whys, the guides dropped them.
2. **Multi-topic stages.** e.g. stage 7 bundled DLQ + FIFO + dedup +
   `oldest_age`; stage 9 bundled three DynamoDB ideas; stage 2 bundled
   conditions + boundaries.
3. **Factual errors.** Stage 12's guide said filter policies are "AND within a
   key, OR across values" — backwards; stage 9 claimed RCU/WCU derives from
   item size, which the implementation never does; stage 13's predict tested a
   rule the checker never asserts; stage 7 omitted the tested `oldest_age`
   requirement; stage 11's "retries twice" contradicted the asserted 3 attempts.

## What changed

- `aws-from-scratch/check.py` — 36 per-stage checks (`check_stage_1` …
  `check_stage_24`, some stages share a function surface), `CHECKS` titles
  renamed to one-behavior phrasing. All 36 pass against `solutions/`.
- `codecraft/curriculum.py` — aws entry rewritten: 36 stages, each with
  `action` + `why` + `predict` + `tags`.
- `codecraft/guide.py` — `render_stage` emits a
  `## Why the requirement is what it is` section.
- `codecraft/manifests.py` — passes `why` through.
- `aws-from-scratch/stages/` — 36 regenerated guides; `START.md` updated.
- `codecraft/profile.json` — aws stage state reset for the renumbered ladder.

## Stage map (36)

| # | file | the one thing |
|---|---|---|
| 1 | iam.py | explicit deny > allow > implicit deny |
| 2 | iam.py | conditions: AND keys, OR values, fail closed |
| 3 | iam.py | permissions boundaries subtract, never grant |
| 4 | iam.py | assume-role: caller policy AND role trust |
| 5 | s3.py | put/get, ETag = MD5, NoSuchKey |
| 6 | s3.py | multipart ETags end in `-<part count>` |
| 7 | s3.py | delimiter invents folders at list time |
| 8 | s3.py | delete marker hides versions, frees nothing |
| 9 | sqs.py | receive is a lease; expiry redelivers |
| 10 | sqs.py | stale receipt handles fail to delete |
| 11 | sqs.py | change_visibility extends the lease |
| 12 | sqs.py | poison messages dead-letter after max_receives |
| 13 | sqs.py | oldest_age counts in-flight too |
| 14 | sqs.py | FIFO: one in-flight message per group |
| 15 | sqs.py | FIFO dedup window |
| 16 | dynamodb.py | composite key = partition + sort |
| 17 | dynamodb.py | query reads one partition |
| 18 | dynamodb.py | conditional writes fail atomically |
| 19 | dynamodb.py | consistent reads cost 2x |
| 20 | dynamodb.py | capacity divides across partitions; hot key throttles |
| 21 | dynamodb.py | scan reads everything, then filters |
| 22 | lambda_svc.py | cold start once; warm state survives |
| 23 | lambda_svc.py | env TTL resets state; timeout bills full |
| 24 | lambda_svc.py | concurrency quota; reservation steals a floor |
| 25 | lambda_svc.py | async retries to 3 attempts, then DLQ |
| 26 | sns.py | one publish fans out to every subscriber |
| 27 | sns.py | filters: AND keys, OR values, missing never matches |
| 28 | sns.py | EventBridge: nested shape, fires every rule |
| 29 | kms.py | envelope: data key encrypts, CMK wraps the key |
| 30 | kms.py | one KMS call per object, not per byte |
| 31 | kms.py | encryption context must match on decrypt |
| 32 | kms.py | rotation re-encrypts keys, never data |
| 33 | vpc.py | CIDR containment, overlap, 5 reserved IPs |
| 34 | vpc.py | routes pick the longest matching prefix |
| 35 | vpc.py | SG stateful vs NACL stateless, same rules |
| 36 | capstone.py | the pipeline, and failures surfacing a layer away |
