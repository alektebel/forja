# Rate Limiter — Moderate

## 1. What problem does it solve?

Without rate limiting, a single client (or a malicious one) can overwhelm a service:
- DDoS: too many requests from one source
- Slow client: a client processes responses slowly; keeps connections open
- Burst: a client sends 1000 requests instantly, crushing the database
- Fairness: one heavy user starves lighter users

A rate limiter enforces a limit: max N requests per T seconds per caller.

**The job:** reject excess requests with `429 Too Many Requests` (or `403 Forbidden`)
before they reach the backend, while being fair and accurate.

## 2. How does it work?

### Algorithms

| Algorithm | How it works | Burst allowed? | Accuracy |
|---|---|---|---|
| **Fixed window** | Count requests in fixed time window (e.g. 1000/minute); reset on window boundary | No | Low (edge case: 1000 at end of one window + 1000 at start of next = 2000 in 1 second) |
| **Sliding window log** | Store timestamp of each request; count requests in last N seconds | Yes (limited by bucket size) | High (but memory-heavy: N entries per user) |
| **Sliding window counter** | Combine fixed window (current + previous) with weighted average | Yes | Good (approximate; 2 counters per user) |
| **Token bucket** | Refill at rate R; each request consumes 1 token; burst allowed up to bucket size | Yes (up to bucket capacity) | Exact (one counter per user) |
| **Leaky bucket** | Queue requests at rate R; process at fixed rate; burst fills queue | No (smoothed output) | Exact (one counter + queue per user) |

### Token bucket (most common in practice)

```
bucket_size = 100        # max burst capacity
refill_rate = 10         # tokens added per second
tokens = 100             # starts full

def allow(request):
    now = time.now()
    tokens += (now - last_refill) * refill_rate  # refill
    tokens = min(tokens, bucket_size)            # cap at bucket
    if tokens >= 1:
        tokens -= 1
        return True
    else:
        return False                             # rate limit exceeded
```

### Distributed rate limiting

Single-node rate limiting is easy (in-memory counter).
Distributed (across multiple instances) requires a shared store:

| Store | Pros | Cons |
|---|---|---|
| **Redis (INCR + TTL)** | Atomic, fast, simple | Redis must be available |
| **DynamoDB** | Distributed, durable | Higher latency than Redis |
| **Database** | Always available | Slow; not suitable for high QPS |

### Headers

Standard rate limit headers (Twitter/X convention):
- `X-RateLimit-Limit`: the maximum allowed requests
- `X-RateLimit-Remaining`: remaining requests in the current window
- `X-RateLimit-Reset`: when the window resets (epoch seconds)
- `Retry-After`: seconds to wait (on 429 response)

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Nginx `limit_req`** | Module-based | Fixed window; `burst` parameter for token-bucket-like burst |
| **Envoy `rate_limit`** | Filter-based | Per-cluster, per-route; integrates with external Redis |
| **Redis-based** | Lua script in Redis | Atomic INCR + TTL; most common in custom gateways |
| **Kong `rate-limiting`** | Plugin | Supports 6 levels of granularity; Redis-backed |
| **Cloudflare** | Edge-level | Global; protects the origin from excessive requests |
| **Resilience4j** | Java library | Token bucket, fixed window, sliding window in-memory |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Algorithm | Token bucket | Sliding window log | Need smooth output → leaky bucket; burst → token bucket |
| Scope | Per-user (API key) | Per-IP | Public API → per-user; internal → per-IP |
| Storage | In-memory (single node) | Redis (distributed) | Single instance → memory; multi-instance → Redis |
| Action | Reject (429) | Throttle (queue/delay) | Hard limit → 429; overload protection → throttle |
| Grace period | None | `Retry-After` header | Respectful clients → header; automation → no grace |

## 5. Exercises

1. **Fixed window rate limiter**: Count requests per user per minute; reject when exceeded.
2. **Token bucket**: Per-user bucket with configurable size and refill rate; atomic check-and-decrement.
3. **Sliding window log**: Store per-user list of request timestamps; count requests in last N seconds.
4. **Distributed rate limiter**: Redis-backed using `INCR` + `EXPIRE`; Lua script for atomicity.
5. **Multi-tier rate limiting**: Global limit (all users) + per-user limit; reject when either is exceeded.

## 6. References

- [Cloudflare: Rate limiting algorithms](https://www.cloudflare.com/learning/ddos/glossary/rate-limiting/)
- [Nginx rate limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Resilience4j rate limiter](https://github.com/resilience4j/resilience4j)
- [Token bucket algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Sliding window rate limiter](https://www.baeldung.com/cs/sliding-window-rate-limiter)