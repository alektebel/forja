# Caching Layer (Redis) — Moderate

## 1. What problem does it solve?

A database query takes 5–50ms. A cache lookup takes <1ms.
If the same query runs 10,000 times per second, that's 50 seconds of DB time
vs 0.01 seconds of cache time.

A caching layer sits between the application and the database:
- **Cache-aside (lazy loading):** app reads cache → miss → reads DB → writes cache → returns
- **Write-through:** app writes cache AND DB (synchronous); cache is always current
- **Write-back:** app writes cache only; cache asynchronously flushes to DB

**The job:** serve repeated reads at sub-millisecond latency, reducing DB load,
while keeping data fresh through TTL, eviction, and stampede protection.

## 2. How does it work?

### Cache-aside pattern (most common)

```python
def get(key):
    value = cache.get(key)          # step 1: check cache
    if value is None:               # step 2: miss
        value = db.query(key)       # step 3: read DB
        cache.set(key, value)       # step 4: write cache
    return value                    # step 5: return
```

On cache hit: one cache read (<1ms).
On cache miss: one cache read + one DB query (5–50ms) + one cache write.

### Eviction policies

| Policy | Description | When to use |
|---|---|---|
| **LRU** (Least Recently Used) | Evict the item not accessed for longest | General purpose; most common |
| **LFU** (Least Frequently Used) | Evict the item with fewest accesses | Items with very different access patterns |
| **TTL** (Time-to-Live) | Every key expires after N seconds | Expired data (e.g. auth tokens, session data) |
| **Memory limit** | Evict when memory is full (maxmemory-policy) | When you must not exceed a memory budget |

### Cache stampede (thundering herd)

N requests for the same key all miss → N concurrent DB queries.

**Solutions:**
1. **Mutex per key:** only one caller fetches; others wait
2. **Probabilistic early expiry:** expire at `TTL * random(0.5, 1.0)` to stagger
3. **Background refresh:** keep an item alive by refreshing before expiry

```python
def get_with_mutex(key):
    value = cache.get(key)
    if value is None:
        if acquire_mutex(f"lock:{key}"):  # only one fetcher
            value = db.query(key)
            cache.set(key, value, ttl=300)
            release_mutex(f"lock:{key}")
        else:
            sleep(random(0.01, 0.05))
            return get_with_mutex(key)   # retry
    return value
```

### Redis internals (why it's fast)

- **Single-threaded event loop:** no lock contention, no context switching
- **In-memory:** no disk I/O for reads/writes (persistence is async)
- **O(1) for most operations:** hash, string, set
- **O(log N) for sorted set:** skip-list-based

### Redis data structures

| Type | Use case |
|---|---|
| **String** | Counter, cache value, session data |
| **Hash** | User profile (field-value pairs) |
| **List** | Queue, timeline |
| **Set** | Unique items, tags |
| **Sorted Set** | Leaderboard, priority queue |
| **Bitmap** | Active users, feature flags |
| **HyperLogLog** | Unique visitor counting (approximate) |
| **Stream** | Event log, message queue replacement |

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Redis** | In-memory store | Single-threaded; persistence via RDB/AOF; clusters for scaling |
| **Memcached** | Simple key-value cache | Multi-threaded; no persistence; simpler than Redis; only strings |
| **Valkey** | Redis fork (Linux Foundation) | Community-driven, open-source continuation of Redis after Oracle restrictions |
| **KeyDB** | Multi-threaded Redis fork | Multi-threaded I/O; NUMA-aware; drop-in Redis replacement |
| **Dragonfly** | Modern in-memory store | Multi-threaded, columnar storage; claims 10x Redis |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Cache mode | Cache-aside (lazy) | Write-through | Strong consistency → write-through; read-heavy → cache-aside |
| Eviction | LRU | LFU | Access frequency varies wildly → LFU |
| Consistency | Eventually consistent | Write-back + flush | Need durability → write-back; need speed → cache-aside |
| Cluster | Single-node | Cluster (sharding) | Data fits in one machine → single-node; multi-TB → cluster |
| Persistence | RDB (snapshot) | AOF (append-only) | Need full recovery → AOF; disk space matters → RDB |

## 5. Exercises

1. **Cache-aside layer**: Wrap a DB query method; check cache first, miss → query DB → write cache → return.
2. **LRU eviction**: Implement a fixed-size cache that evicts the least-recently-used item.
3. **Stampede protection**: Mutex-per-key; only one caller fetches from DB, others wait.
4. **TTL-aware cache**: Every key has an expiry; expired keys are evicted on access (lazy) and by a background cycle (active).
5. **Write-through cache**: On `set(key, value)`, write both cache and DB.

## 6. References

- [Redis documentation](https://redis.io/docs/)
- [Redis cache-aside pattern](https://redis.io/learn/develop/java/spring/rate-limiting/cache-aside)
- [Cache stampede problem](https://www.alibabacloud.com/blog/cache-stampede-problem-and-solutions_595970)
- [Memcached vs Redis comparison](https://www.geeksforgeeks.org/memcached-vs-redis/)
- [DragonflyDB: a modern Redis replacement](https://docs.dragonflydb.io/)
- [KeyDB: multi-threaded Redis fork](https://docs.keydb.dev/)