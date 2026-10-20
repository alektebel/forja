# Cache Invalidation Strategy — Complex

## 1. What problem does it solve?

Caches speed up reads, but data changes:
```
Time 0ms:  DB: name="Alice"
Time 1ms:  Cache: name="Alice"
Time 2ms:  DB: name="Bob"      ← data changed
Time 3ms:  Cache: name="Alice" ← still stale!
Time 4ms:  Read from cache → returns "Alice" (WRONG!)
```

Cache invalidation solves this: when the source of truth changes,
the cache must be updated or the stale entry must be evicted.

The problem is hard because:
- Which copies are stale? (the cache may be distributed)
- When to evict? (immediately? on read? on a schedule?)
- What about cascading dependencies? (cache A depends on cache B)

**The job:** keep cache entries consistent with the source of truth,
while balancing freshness, performance, and complexity.

## 2. How does it work?

### Strategies

| Strategy | How it works | Pros | Cons |
|---|---|---|---|
| **TTL** | Expire after N seconds | Simple; automatic | Stale data up to TTL; no instant consistency |
| **Write-through** | Update cache on every write | Always current | Write amplification (cache + DB) |
| **Write-behind** | Write to cache; async flush to DB | Fast writes | Risk of data loss if cache crashes |
| **Cache stampede protection** | Only one fetch per key | Prevents thundering herd | Extra latency for waiting callers |
| **Invalidation by key** | Delete specific key when source changes | Precise; no stale data | Must know which keys to invalidate |
| **Cache tags (Surrogate-Key)** | Associate keys with tags; purge by tag | Bulk purge; clean | Requires tag tracking in cache |
| **Versioned keys** | `user:123:v2` → increment version on update | Never stale; explicit | Client must handle version changes |

### The two hard problems

```
1. When to invalidate?
   - On write: update cache (write-through) or evict cache
   - On read: check if stale; refresh if so (lazy)
   - On schedule: background job evicts all stale entries

2. What to invalidate?
   - Single key: simple, but cache may depend on many sources
   - All keys: safe but wasteful (thundering herd on next read)
   - Keys with same tag: precise but requires tag tracking
```

### Cache stampede (revisited)

When a key expires, N simultaneous reads all hit the DB.

Solutions:
1. **Mutex per key**: only one fetcher; others wait
2. **Probabilistic expiry**: stagger expiration times (expire at TTL × random(0.5, 1.0))
3. **Background refresh**: before TTL expires, refresh the key

```python
def get(key):
    value = cache.get(key)
    if value is None:
        with mutex(f"lock:{key}"):  # only one refresher
            value = db.query(key)
            cache.set(key, value, ttl=300)
    return value
```

### Cache stampede on batch invalidation

When invalidating N keys, N fetches happen simultaneously.

Solutions:
- **Stagger**: don't invalidate all keys at once; spread over time
- **Lazy refresh**: on read, check if cache is about to expire; refresh in background
- **Version bump**: change version number; next read detects mismatch and refreshes

## 3. Real implementations

| System | Invalidation | Notes |
|---|---|---|
| **Redis** | TTL + explicit DEL + cache tags (Surrogate-Key via Varnish) | TTL-based; manual invalidation via API |
| **Cloudflare** | Cache tags + instant purge | Purge by URL or by cache tag; near-instant propagation |
| **Fastly** | Surrogate-Key purge | Bulk purge by tag; immediate propagation to all PoPs |
| **CDN** | TTL + cache purge + cache warming | TTL-based; purge on demand; warm on deploy |
| **DynamoDB Streams** | Event-driven cache invalidation | When DB changes, emit event to evict cache |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Invalidation | TTL (stale allowed) | Write-through (instant consistency) | Strong consistency → write-through; speed → TTL |
| Granularity | Per-key | Per-tag (bulk) | Few keys → per-key; many keys sharing source → per-tag |
| Refresh | Lazy (on read) | Background (before expiry) | Read-heavy → lazy; stale-then-correct → background |
| Scope | Single cache | Multi-layer (CDN + app + DB cache) | Multiple layers → coordinate invalidation across all |
| Staleness tolerance | Zero (write-through) | Bounded (TTL = N seconds) | User-facing data → zero; analytics → bounded |

## 5. Exercises

1. **TTL cache**: Implement a cache with per-key TTL; expired entries are lazily evicted.
2. **Cache stampede protection**: Mutex-per-key; only one refresher; others wait.
3. **Write-through cache**: On `set(key, value)`, write both cache and DB; never return stale data.
4. **Cache tag purge**: Associate cached keys with tags; purge by tag evicts all matching keys.
5. **Versioned keys**: Store `key:v<N>`; on update, bump version; next read detects version mismatch and refreshes.

## 6. References

- [Cache stampede problem](https://www.alibabacloud.com/blog/cache-stampede-problem-and-solutions_595970)
- [Cloudflare cache tags](https://developers.cloudflare.com/cache/how-to/cache-tags/)
- [Fastly Surrogate-Key purge](https://docs.fastly.com/en/guides/purge-with-surrogate-keys)
- [Redis: volatile-lru eviction policy](https://redis.io/docs/latest/operate/oss_and_stack/management/config/eviction/)
- [Write-through vs write-behind caching](https://www.ibm.com/think/topics/write-through-caching)
- [Cache invalidation strategies (Martin Kleppmann)](https://martin.kleppmann.com/2016/02/19/how-to-do-distributed-locking.html)