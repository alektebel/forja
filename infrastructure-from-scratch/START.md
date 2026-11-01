# Infrastructure From Scratch

The building blocks of distributed systems, one module each: consistent hashing, caching, CDN and rate limiting, batching, pooling, stickiness, circuit breaking, queues, leaderboards, hot partitions, locality, eventual consistency, idempotency, edge computing, capacity math.

**18 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke infrastructure-from-scratch
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `url_shortener.py` — URL shortener — base62 codes, TTL store, click stats

Implement base62 encode/decode, a URLStore with TTL expiry and hit stats, and a URLShortener that mints codes and resolves them.

```bash
forja guide infrastructure-from-scratch 1     # the full stage page
forja test infrastructure-from-scratch --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint infrastructure-from-scratch` · `forja explain infrastructure-from-scratch`
