# Stage 3: Cache — LRU, TTL, cache-aside, stampede protection

**Course:** Infrastructure From Scratch (`infrastructure-from-scratch`)
**File:** `cache.py`
**Tags:** moderate, caching, locking

## The mechanism

Implement LRUCache (dict + doubly-linked list, O(1) get/put), TTLCache, CacheAsideStore, and StampedeProtectedCache.

## Tests

The tester runs your code like this:

```bash
forja test infrastructure-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run infrastructure-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> can a get() be O(1) while keeping true recency order?

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Notes

- move-to-head on read, evict from tail
- TTL is checked lazily on get, never by a sweeper
- stampede: one in-flight fetch per key, others wait on its event

## Next

When this stage is green:

```bash
forja stage infrastructure-from-scratch 4
```
