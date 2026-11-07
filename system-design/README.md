# System Design From Scratch

A collection of from-scratch implementations covering the core building blocks of distributed systems and system design interviews.

## Goal

Build hands-on intuition for system design by implementing the patterns yourself:
- Networking primitives (HTTP, DNS, TLS basics)
- Database patterns (indexing, replication, transactions)
- Caching (LRU, cache-aside, stampede protection, TTL/eviction)
- Async systems (message queues, retries, backoff, DLQ, idempotency)
- Reliability patterns (circuit breaker, timeout, bulkhead, backpressure)
- Classic small designs (URL shortener, rate limiter, leaderboard, notifications)
- Capacity math (QPS, storage/day, bandwidth, cache hit ratio)
- Observability (structured logging, metrics, tracing)

---

## Learning Path

### 1. Foundations — Networking & OS Basics
> *Already covered in this repo:* `http-server/`, `dns-server/`, `firewall-from-scratch/`

Key concepts to understand before system design:
- **HTTP/HTTPS**: request/response cycle, headers, status codes, keep-alive, TLS handshake
- **DNS**: resolution chain, TTL, caching at resolver, A/CNAME/MX records
- **TCP**: 3-way handshake, flow control, retransmission, TIME_WAIT
- **TLS**: certificate chain, cipher suites, session resumption
- **Latency numbers**: memory (~100ns), SSD (~100µs), network RTT (~1ms LAN, ~100ms cross-region)
- **OS basics**: threads vs processes, context switching cost, virtual memory, file descriptors

---

### 2. Databases
Key concepts:
- **Indexing**: B-tree vs hash index, composite indexes, covering index, index selectivity
- **Transactions & ACID**: atomicity, consistency, isolation, durability
- **Isolation levels**: read uncommitted → read committed → repeatable read → serializable
- **Replication**: leader-follower, synchronous vs async replication, replication lag
- **SQL vs NoSQL**: when to use each, trade-offs (schema flexibility, joins, consistency)
- **Sharding & partitioning**: horizontal vs vertical, hot partitions, consistent hashing

---

### 3. Caching
**Template**: [`cache.py`](cache.py)

Key concepts:
- **LRU/LFU eviction policies**
- **Cache-aside pattern**: app reads from cache, on miss fetches DB and writes to cache
- **Write-through / write-back patterns**
- **TTL**: time-to-live, staleness trade-offs
- **Cache stampede (thundering herd)**: many simultaneous misses hit DB; mitigated with locking/jitter
- **Cache invalidation**: hardest problem — on write, either delete or update cache entry
- **Redis basics**: single-threaded event loop, data structures (string, hash, list, set, sorted set)
- **CDN basics**: edge caches, cache-control headers, origin shield, purging

---

### 4. Async Systems
**Template**: [`message_queue.py`](message_queue.py)

Key concepts:
- **Queues vs streams**: queues consume and delete (SQS); streams retain and replay (Kafka)
- **At-least-once delivery**: messages may be redelivered — consumers must be idempotent
- **Retries & exponential backoff**: `delay = base * 2^attempt + jitter`
- **Dead-letter queue (DLQ)**: messages that fail N times go to DLQ for inspection
- **Idempotency**: same operation applied multiple times = same result (use idempotency keys)
- **Deduplication**: deduplicate by message ID in a seen-set with TTL
- **Scheduled jobs**: cron-like triggers, at-least-once semantics, leader election for single-runner

---

### 5. Small Designs (Practice Problems)
**Templates**:
- [`url_shortener.py`](url_shortener.py) — URL shortener
- [`rate_limiter.py`](rate_limiter.py) — Token bucket / sliding window rate limiter
- [`consistent_hash.py`](consistent_hash.py) — Consistent hashing ring

#### URL Shortener
- **API**: `POST /shorten` → `{short_url}`, `GET /{code}` → redirect
- **Data model**: `urls(code PK, long_url, created_at, expires_at, hits)`
- **Encoding**: base62 over auto-increment ID or random 6-char code
- **Scale**: 100M URLs, 10:1 read/write, ~1KB/entry → ~100GB storage, cache top URLs

#### Rate Limiter
- **Algorithms**: token bucket (allows bursts), sliding window log (precise), sliding window counter (efficient)
- **Storage**: Redis `INCR` + `EXPIRE` per key
- **Distributed**: same Redis key across instances; careful with clock skew

#### Notifications System
- **Components**: event producers → message queue → fanout workers → push/email/SMS gateways
- **Idempotency**: deduplicate by `(user_id, event_id)`
- **Rate limiting**: don't spam users — per-user daily limits

#### Comments System
- **Data model**: `comments(id, post_id, parent_id, user_id, body, created_at)` — adjacency list for tree
- **Pagination**: keyset pagination on `(post_id, created_at, id)`
- **Denormalization**: cache comment count on posts table

#### File Upload + Processing
- **Flow**: client → presigned S3 URL → upload direct to object store → S3 event → queue → worker processes file
- **Chunked upload**: split large files, upload parts, multipart complete
- **Processing pipeline**: transcode/resize as async job; store output in S3; update DB

#### Leaderboard
**Template**: [`leaderboard.py`](leaderboard.py)
- **Data model**: Redis sorted set `ZADD leaderboard score user_id`, `ZREVRANK` for rank
- **Persistence**: periodic snapshot to DB; Redis as fast read layer
- **Scale**: top-K with `ZREVRANGE`; windowed leaderboards with time-bucketed keys

---

### 6. APIs + Data Model
For every design, write out:
```
Endpoints:
  POST   /resource         → create
  GET    /resource/{id}    → read
  PUT    /resource/{id}    → update (full)
  PATCH  /resource/{id}    → update (partial)
  DELETE /resource/{id}    → delete
  GET    /resource?cursor=&limit=  → paginated list

Request/Response: JSON with camelCase, ISO-8601 dates, pagination envelope
  { "data": [...], "nextCursor": "...", "total": 1000 }

Tables/Keys: choose partition key to avoid hot partitions
  - spread writes by hashing user_id, not by timestamp
  - composite keys: (tenant_id, entity_id) for multi-tenant

Schema evolution:
  - add nullable columns only (backward compatible)
  - use migrations with rollback scripts
  - avoid renaming columns without dual-write period
```

---

### 7. Capacity Math
**Template**: [`capacity_planner.py`](capacity_planner.py)

Always work through:
```
Given: 10M DAU, 10 reads/user/day, 1 write/user/day

QPS (reads):  10M * 10 / 86400 ≈ 1,160 QPS
QPS (writes): 10M * 1  / 86400 ≈ 116 QPS
Peak:         ~3x average      ≈ 3,500 QPS reads

Payload: 1 KB per read response
Bandwidth: 1,160 QPS * 1 KB = ~1.1 MB/s

Storage/day (writes): 116 writes/s * 1 KB * 86400s ≈ 10 GB/day
Storage/year: 10 GB * 365 ≈ 3.65 TB

Cache: assume 80% hit ratio → only 20% hit DB = 232 QPS to DB
DB sizing: 232 QPS, 5ms avg query → need ~2 replicas
```

---

### 8. Reliability Patterns
**Template**: [`circuit_breaker.py`](circuit_breaker.py)

Key patterns:
- **Timeout**: every outbound call must have a timeout; use deadline propagation
- **Retry with backoff**: `delay = min(cap, base * 2^n) + random_jitter`; only retry idempotent ops
- **Circuit breaker**: CLOSED → OPEN (on failures) → HALF-OPEN (probe) → CLOSED
- **Load shedding**: drop low-priority requests when overloaded; return 503 with `Retry-After`
- **Backpressure**: signal upstream to slow down; bounded queues reject when full
- **Bulkhead**: isolate resource pools per caller/tenant so one bad actor can't exhaust all connections
- **Graceful degradation**: return stale data / partial results rather than full failure
- **Multi-AZ**: deploy across availability zones; use health checks + automatic failover

---

### 9. Observability
Key concepts:
- **Logs**: structured (JSON), include `trace_id`, `request_id`, `user_id`, severity levels
- **Metrics**: counters (requests total), gauges (queue depth), histograms (latency p50/p99)
- **Traces**: distributed tracing (OpenTelemetry), span per service hop, visualize with Jaeger/Zipkin
- **SLO/SLA**: define SLOs (e.g. p99 < 200ms, 99.9% availability); alert when error budget burns fast
- **Alerting**: alert on symptoms (high error rate, latency spike) not causes (high CPU)
- **Dashboards**: golden signals — latency, traffic (RPS), errors, saturation (USE method)
- **Debugging slowdowns**: check p99 latency, trace slow requests, look for lock contention, GC pauses

---

### 10. Advanced Distributed Systems Patterns

#### Rate Limiting
**Template**: [`rate_limiter.py`](rate_limiter.py)
- Fixed window, token bucket, sliding window log, sliding window counter
- Redis-backed distributed rate limiting; `X-RateLimit-*` headers

#### Throttling
**Template**: [`throttling.py`](throttling.py)
- Leaky bucket: smooth output rate regardless of input bursts
- Delay-based throttling: slow down callers instead of rejecting
- Queue-based worker: process at a controlled rate
- Adaptive throttling: shed load based on downstream success ratio

#### Eventual Consistency
**Template**: [`eventual_consistency.py`](eventual_consistency.py)
- G-Counter CRDT: grow-only counter, merge by component-wise max
- LWW-Register: last-writer-wins conflict resolution by timestamp
- Vector clocks: track causality; detect concurrent vs. happened-before
- Read-repair: fix stale replicas lazily on reads

#### CDN Caching
**Template**: [`cdn_caching.py`](cdn_caching.py)
- Cache-Control parsing: `max-age`, `s-maxage`, `private`, `no-store`, `stale-while-revalidate`
- Surrogate keys / cache tags: bulk purge by content relationship
- Origin shield: coalesce misses from many PoPs into one origin request
- Cache key normalization: strip tracking params, handle `Vary` headers

#### Edge Computing
**Template**: [`edge_computing.py`](edge_computing.py)
- Latency-based routing: pick nearest healthy PoP
- Edge middleware pipeline: chain auth, geo-block, A/B logic
- Deterministic A/B testing: hash(user_id) → stable variant assignment
- Edge function runtime: enforce CPU time limits (Cloudflare Workers model)

#### Hot Partition Mitigation
**Template**: [`hot_partition_mitigation.py`](hot_partition_mitigation.py)
- Write scattering: add random salt suffix to spread a hot key across N shards
- Scatter-gather reads: query all shards in parallel, merge results
- Hot key detection: sliding-window access frequency tracker
- Time-bucketed keys: distribute bursty time-series writes across hourly/daily buckets

#### Data Locality
**Template**: [`data_locality.py`](data_locality.py)
- Shard router: hash(partition_key) % N for deterministic routing
- Co-location store: keep related entities on the same shard (no cross-shard joins)
- Denormalized read model: pre-join at write time; fan-out on update
- Locality-aware cache: per-shard in-process cache, no cross-shard cache lookup

#### Request Batching
**Template**: [`request_batching.py`](request_batching.py)
- Size-window batcher: flush when batch reaches N items
- Time-window batcher: background thread flushes every N ms
- DataLoader pattern: deduplicate keys + fan out results (solves N+1 query problem)
- Pipeline batcher: flush on whichever threshold (size or time) is reached first

#### Connection Pooling
**Template**: [`connection_pooling.py`](connection_pooling.py)
- Pool lifecycle: pre-create min connections; grow to max on demand
- Acquire with timeout: callers wait when pool is exhausted; raise on deadline
- Idle eviction: close connections idle longer than `idle_timeout`; keep `min_size`
- Context manager (`with` statement): auto-release connections after use
- Pool sizing: Little's Law — `N = λ × W` (connections = QPS × query_time)

#### Session Stickiness
**Template**: [`session_stickiness.py`](session_stickiness.py)
- Consistent-hash sticky router: `hash(session_id) % len(healthy_backends)`
- Cookie-based affinity: `SERVERID=backend_id` sticky cookie
- Graceful failover: re-hash to a different backend when the pinned one goes down
- Shared session store: Redis-backed sessions eliminate the need for stickiness

#### Idempotency Keys
**Template**: [`idempotency_keys.py`](idempotency_keys.py)
- Key store: PENDING → COMPLETE lifecycle with TTL-based expiry
- Concurrent deduplication: only one execution per key; others wait for the result
- Payment processor example: prevent double charges on retry
- Patterns: HTTP `Idempotency-Key` header, DB UNIQUE constraint, SQS MessageDeduplicationId

---

### 11. Interview Flow (Repeatable Template)
```
1. Requirements (5 min)
   - Functional: what features exactly?
   - Non-functional: scale, latency SLO, availability, consistency

2. APIs (5 min)
   - List endpoints with request/response shapes
   - Confirm scope with interviewer

3. Data Model (5 min)
   - Core tables/collections + key columns
   - Primary key, partition key, indexes
   - Retention policy

4. High-Level Diagram (10 min)
   - Client → LB → API servers → [cache, DB, queue, object store]
   - Name each component (not just "database")

5. Bottlenecks & Scaling (10 min)
   - Do capacity math
   - Identify hot paths (reads? writes? specific endpoints?)
   - Scale each layer: stateless services horizontal, DB read replicas, caching

6. Failure Modes (5 min)
   - What happens if cache is down? DB goes down? Queue backs up?
   - Timeouts, circuit breakers, retries, DLQ

7. Observability (3 min)
   - What metrics/logs/traces would you add?
   - What alerts would fire?

8. Trade-offs (2 min)
   - What did you sacrifice? (consistency vs availability, cost vs latency)
   - What would you do differently at 10x scale?
```

---

## Building and Running Templates

```bash
cd system-design/

# Run any template directly (Python 3.8+)
python url_shortener.py
python rate_limiter.py
python cache.py
python message_queue.py
python circuit_breaker.py
python capacity_planner.py
python consistent_hash.py
python leaderboard.py

# New advanced patterns
python throttling.py
python eventual_consistency.py
python cdn_caching.py
python edge_computing.py
python hot_partition_mitigation.py
python data_locality.py
python request_batching.py
python connection_pooling.py
python session_stickiness.py
python idempotency_keys.py

# Run with tests
python -m unittest discover  # standard library
```

---

## Directory Structure

```
system-design/
├── README.md                       # This file — full learning guide
├── url_shortener.py                # URL shortener template
├── rate_limiter.py                 # Token bucket + sliding window templates
├── cache.py                        # LRU cache + cache-aside pattern template
├── message_queue.py                # Async queue, retries, backoff, DLQ template
├── circuit_breaker.py              # Circuit breaker + bulkhead template
├── capacity_planner.py             # Capacity math calculator template
├── consistent_hash.py              # Consistent hashing ring template
├── leaderboard.py                  # Leaderboard with sorted set template
├── throttling.py                   # Leaky bucket + delay throttling template
├── eventual_consistency.py         # CRDT, LWW, vector clocks, read-repair template
├── cdn_caching.py                  # CDN edge cache + origin shield template
├── edge_computing.py               # Edge routing, middleware, A/B test template
├── hot_partition_mitigation.py     # Write scatter, scatter-gather, time buckets template
├── data_locality.py                # Shard routing, co-location, denormalization template
├── request_batching.py             # Size/time batching, DataLoader template
├── connection_pooling.py           # Pool lifecycle, eviction, context manager template
├── session_stickiness.py           # Sticky router, cookie affinity, session store template
├── idempotency_keys.py             # Idempotency key store, dedup, payments template
└── solutions/
    ├── README.md                   # Solution notes
    ├── url_shortener.py            # Complete URL shortener implementation
    ├── rate_limiter.py             # Complete rate limiter implementations
    ├── cache.py                    # Complete cache implementations
    ├── message_queue.py            # Complete async queue implementation
    ├── circuit_breaker.py          # Complete reliability patterns
    ├── capacity_planner.py         # Complete capacity planner
    ├── consistent_hash.py          # Complete consistent hash ring
    ├── leaderboard.py              # Complete leaderboard implementation
    ├── throttling.py               # Complete throttling implementations
    ├── eventual_consistency.py     # Complete eventual consistency implementations
    ├── cdn_caching.py              # Complete CDN caching implementation
    ├── edge_computing.py           # Complete edge computing implementation
    ├── hot_partition_mitigation.py # Complete hot partition mitigation
    ├── data_locality.py            # Complete data locality implementation
    ├── request_batching.py         # Complete request batching implementation
    ├── connection_pooling.py       # Complete connection pool implementation
    ├── session_stickiness.py       # Complete session stickiness implementation
    └── idempotency_keys.py         # Complete idempotency keys implementation
```

---

## Video Courses & Resources

### System Design
- [System Design Interview – An Insider's Guide (Alex Xu)](https://www.amazon.com/System-Design-Interview-insiders-Second/dp/B08CMF2CQF)
- [Grokking the System Design Interview](https://www.educative.io/courses/grokking-the-system-design-interview)
- [CS 75 - Building Dynamic Websites - Harvard](https://cs75.tv/2012/summer/)
- [6.824 - Distributed Systems - MIT](https://pdos.csail.mit.edu/6.824/schedule.html)

### Databases
- [CMU 15-445 Database Systems](https://15445.courses.cs.cmu.edu/fall2022/)
- [Database Systems Courses](https://github.com/Developer-Y/cs-video-courses#database-systems)

### Distributed Systems
- [Designing Data-Intensive Applications (Kleppmann)](https://dataintensive.net/)
- [Distributed Systems Courses](https://github.com/Developer-Y/cs-video-courses#distributed-systems)

### Computer Networks
- [Computer Networks Courses](https://github.com/Developer-Y/cs-video-courses#computer-networks)

### Maps & Communities
- [roadmap.sh/backend](https://roadmap.sh/backend) — the community map of this territory; walk it *after* building to find the nodes your implementation skipped
- [r/databasedevelopment](https://www.reddit.com/r/databasedevelopment/) — practitioners who *implement* databases, the altitude this course teaches at
- more external sources catalogued in [`EXTERNAL-RESOURCES.md`](../EXTERNAL-RESOURCES.md)
