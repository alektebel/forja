# Global Rate Limiting at Scale — Extremely Complex

## 1. What problem does it solve?

A simple rate limiter (local, in-memory) works for a single instance:
```python
requests = 0
def allow():
    global requests
    requests += 1
    return requests <= limit
```

But when you have 100 instances across 5 regions, each instance has its own counter:
- Instance 1: allows 1000 requests → total: 1000
- Instance 2: allows 1000 requests → total: 2000
- Total: 2000 (but limit is 1000!)

The limit is per-instance, not global. And it gets worse across regions:
- Users in different regions have different counters
- No single view of "how many requests has this user made globally?"

Global rate limiting enforces a limit across ALL instances and ALL regions.

**The job:** enforce one limit across all traffic, in real-time, with
sub-millisecond latency, no single point of failure, and perfect accuracy.

## 2. How does it work?

### The problem: distributed counters

You need a single counter that all instances can atomically increment:
```
Instance A: INCR user:limit:12345 → 101 (user made 101 requests globally)
Instance B: INCR user:limit:12345 → 102 (user made 102 requests globally)
```

### Redis-based global rate limiting (most common)

Use Redis `INCR` + `EXPIRE`:

```python
def check_rate_limit(user_id, limit, window_seconds):
    key = f"rate:{user_id}"
    with redis.pipeline() as pipe:
        pipe.multi()
        pipe.incr(key)
        pipe.ttl(key)
        result = pipe.execute()
        
        current_count = result[0]
        ttl = result[1]
        
        if ttl == -1:  # key doesn't exist yet → set TTL
            expire(key, window_seconds)
            ttl = window_seconds
        
        return current_count <= limit
```

Atomicity: Redis `INCR` is atomic. No race conditions.

### Sliding window log (accurate, memory-heavy)

Store every request timestamp:
```python
def check_rate_limit(user_id, limit, window_seconds):
    key = f"rate:{user_id}"
    now = time.now()
    window_start = now - window_seconds
    
    # Remove old entries
    redis.zremrangebyscore(key, 0, window_start)
    
    # Count recent requests
    count = redis.zcard(key)
    
    if count < limit:
        redis.zadd(key, {str(now): now})
        redis.expire(key, window_seconds)
        return True
    else:
        return False
```

Problem: each request adds an entry. 1000 requests per user × 1M users = 1B entries.

### Sliding window counter (approximate, efficient)

Combine fixed window counters:
```
window A: 0-59 seconds (current)
window B: 60-119 seconds (previous)

effective_count = window_B × ((window - 1 - elapsed) / window) + window_A
```

This gives an approximate count that's better than fixed window (no edge case).

### Global quota with regional buckets

One global limit with regional sub-limits:
```
Global: 10,000 requests/minute
Region US: 6,000/minute
Region EU: 3,000/minute
Region AP: 1,000/minute
```

```python
def check_rate_limit(user_id):
    if region_count[region] >= region_limit[region]:
        return False  # regional limit exceeded
    
    if global_count[user_id] >= global_limit[user_id]:
        return False  # global limit exceeded
    
    region_count[region] += 1
    global_count[user_id] += 1
    return True
```

### Consistent hashing for rate limit stores

When the rate limit store is distributed (multiple Redis nodes),
use consistent hashing to ensure the same user always hits the same node:

```
user_id → hash(user_id) → Redis node → check that node's counter
```

If a Redis node goes down: only a fraction of users are affected.
Rebalance by changing the number of virtual nodes (consistent hashing).

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Redis + Lua** | Distributed rate limiting | Most common; atomic INCR + EXPIRE; Lua for complex logic |
| **Envoy rate limit service** | External rate limit | Envoy calls an external gRPC service; supports Redis, Golang, custom |
| **Kong rate-limiting** | Plugin-based | Redis-backed; 6 levels of granularity |
| **Cloudflare** | Edge rate limiting | Global; enforces at the edge before reaching origin |
| **Datadog** | Application-level | In-process; distributed via Redis |
| **Resilience4j** | Java library | In-process; token bucket, sliding window |
| **HashiCorp Vault** | Rate-limiting auth | Vault-based; per-path rate limits |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Algorithm | Fixed window (Redis INCR) | Sliding window log | Simple → INCR; accurate → sliding window |
| Storage | Redis | In-memory (single node) | Multi-instance → Redis; single → memory |
| Scope | Per-user | Global (all users) | User quotas → per-user; system limit → global |
| Regional | Global (one counter) | Regional (per-region counters) | Global limit → one counter; regional → per-region |
| Consistency | Strong (Redis) | Eventual (async sync) | Accuracy matters → Redis; cheap → async |

## 5. Exercises

1. **Global rate limiter (Redis)**: INCR + EXPIRE; per-user; 1000 requests per minute.
2. **Sliding window log**: ZSET of timestamps; count requests in last N seconds.
3. **Sliding window counter**: Combine current and previous fixed window with weighted average.
4. **Regional rate limiting**: Global limit + regional sub-limits; reject when either exceeded.
5. **Consistent hashing**: Hash user to Redis node; ensure same user always hits same node.

## 6. References

- [Redis rate limiting with Lua](https://redis.io/commands/incr/)
- [Envoy external rate limit service](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/rate_limit_filter#config-http-filters-rate-limit)
- [Sliding window counter](https://www.baeldung.com/cs/sliding-window-rate-limiter)
- [Cloudflare rate limiting](https://developers.cloudflare.com/waf/rules/rate-limiting-rules/)
- [Datadog rate limiting](https://docs.datadoghq.com/monitors/types/#rate-limiting)
- [Resilience4j rate limiter](https://github.com/resilience4j/resilience4j)