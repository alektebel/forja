"""
CDN Caching — From Scratch
============================
Build a CDN caching layer to understand:
- Edge cache with Cache-Control headers (max-age, s-maxage, no-cache, private)
- Origin shield: a single mid-tier cache between edge nodes and origin
- Cache key normalization (strip irrelevant query params, Vary header)
- Surrogate keys / cache tags: tag responses for bulk purge
- Stale-while-revalidate: serve stale content while fetching fresh in background

Learning Path:
1. Implement an edge cache that respects Cache-Control: max-age
2. Add support for Cache-Control: no-cache, private, no-store
3. Implement surrogate key tagging and bulk purge
4. Implement stale-while-revalidate behaviour
5. Think about: how does a CDN differ from an in-process cache?
   - Shared across all users / requests (public cache)
   - Geographically distributed PoPs
   - Origin shield collapses cache misses from many PoPs into one origin request
"""

import time
import threading
from typing import Any, Dict, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Step 1: Edge Cache with Cache-Control
# ---------------------------------------------------------------------------

class CacheEntry:
    """A cached HTTP response."""
    def __init__(self, body: Any, max_age: float, surrogate_keys: Set[str],
                 stale_while_revalidate: float = 0.0):
        self.body = body
        self.stored_at: float = time.time()
        self.max_age = max_age                          # seconds until stale
        self.stale_while_revalidate = stale_while_revalidate  # extra seconds to serve stale
        self.surrogate_keys = surrogate_keys            # tags for bulk purge
        self.revalidating = False                       # True while background refresh runs


class EdgeCache:
    """Simulates a CDN edge node cache.

    Respects Cache-Control directives:
      - max-age=N:              cache for N seconds
      - s-maxage=N:             shared (CDN) max age, overrides max-age for CDNs
      - no-store:               do not cache at all
      - private:                do not cache on shared/CDN cache
      - no-cache:               must revalidate with origin before serving
      - stale-while-revalidate=N: serve stale for N extra seconds while refreshing

    TODO:
    1. Implement get(key): return cached body if fresh, None if expired/not found
    2. Implement put(key, body, cache_control, surrogate_keys): parse Cache-Control,
       store entry only if cacheable
    3. Implement purge_by_key(surrogate_key): remove all entries with that tag
    4. Implement is_fresh(entry): return True if within max_age
    """

    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return cached body if the entry is fresh, else None.

        TODO:
        1. Look up key in _store
        2. If not found: return None (MISS)
        3. If is_fresh(entry): return entry.body (HIT)
        4. If within stale-while-revalidate window: trigger background revalidation,
           return stale body
        5. Otherwise: return None (STALE — treat as MISS)
        """
        # TODO: implement get
        raise NotImplementedError("Implement EdgeCache.get")

    def put(self, key: str, body: Any, cache_control: str = "max-age=60",
            surrogate_keys: Optional[Set[str]] = None) -> bool:
        """Store a response. Returns False if not cacheable.

        Cache-Control parsing rules:
          - "no-store" → do not cache; return False
          - "private"  → do not cache on shared cache; return False
          - "s-maxage=N" → use N as max_age (overrides max-age for CDNs)
          - "max-age=N" → use N as max_age if s-maxage not present
          - "stale-while-revalidate=N" → set stale_while_revalidate=N
          - "no-cache" → cache but revalidate on every request (max_age=0)

        TODO:
        1. Parse cache_control string into directives
        2. Check for no-store / private → return False
        3. Extract max_age (prefer s-maxage)
        4. Extract stale_while_revalidate
        5. Create CacheEntry and store
        """
        # TODO: implement put with Cache-Control parsing
        raise NotImplementedError("Implement EdgeCache.put")

    def purge_by_key(self, surrogate_key: str) -> int:
        """Remove all cached entries tagged with surrogate_key.

        Returns the number of entries purged.

        TODO: iterate _store, delete entries whose surrogate_keys contains surrogate_key
        """
        # TODO: implement purge by surrogate key
        raise NotImplementedError("Implement EdgeCache.purge_by_key")

    def purge(self, key: str) -> bool:
        """Remove a single cache entry by its cache key.

        TODO: delete key from _store if present
        """
        # TODO: implement purge
        raise NotImplementedError("Implement EdgeCache.purge")

    def _is_fresh(self, entry: CacheEntry) -> bool:
        """Return True if the entry is within its max_age.

        TODO: return (time.time() - entry.stored_at) < entry.max_age
        """
        # TODO: implement _is_fresh
        raise NotImplementedError("Implement EdgeCache._is_fresh")

    def _is_stale_while_revalidate(self, entry: CacheEntry) -> bool:
        """Return True if within the stale-while-revalidate window."""
        age = time.time() - entry.stored_at
        return age < (entry.max_age + entry.stale_while_revalidate)

    @property
    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Step 2: Origin Shield
# ---------------------------------------------------------------------------

class OriginShield:
    """Mid-tier cache between edge nodes and origin.

    Collapses multiple simultaneous cache misses from edge PoPs into a single
    request to the origin (request coalescing).

    Without shield: 50 edge nodes each miss → 50 requests to origin
    With shield: 50 edge misses → 1 request to origin shield → 1 to origin

    TODO:
    - Maintain its own EdgeCache
    - On fetch(key): if in own cache → return (shield HIT)
      If not: coalesce concurrent misses (use per-key lock) → call origin_fn once
      → store in own cache → return to all waiters
    """

    def __init__(self, origin_fn, cache_ttl: float = 60.0):
        """
        Args:
            origin_fn: callable(key) → body  (simulates origin server)
            cache_ttl: how long to cache responses
        """
        self._cache = EdgeCache()
        self._origin = origin_fn
        self._ttl = cache_ttl
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_result: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self.origin_requests = 0   # count of actual origin fetches

    def fetch(self, key: str) -> Any:
        """Fetch key, using shield cache and request coalescing.

        TODO:
        1. Check own cache → return if fresh (shield HIT)
        2. Acquire self._lock; check if another thread is already fetching key
           a. If yes: release lock, wait on the event, return result (coalesced)
           b. If no: create event, store in _inflight, release lock
        3. Fetch from origin: self._origin(key); increment self.origin_requests
        4. Store in own cache
        5. Set event, remove from _inflight, return result
        """
        # TODO: implement fetch with request coalescing
        raise NotImplementedError("Implement OriginShield.fetch")


# ---------------------------------------------------------------------------
# Step 3: Cache Key Normalization (discussion + stub)
# ---------------------------------------------------------------------------

def normalize_cache_key(url: str, vary_headers: Optional[Dict[str, str]] = None,
                        strip_params: Optional[Set[str]] = None) -> str:
    """Compute a normalized cache key from a URL and relevant request headers.

    Key normalization prevents duplicate cache entries for equivalent requests.

    Rules:
      1. Sort query parameters alphabetically
      2. Remove params in strip_params (e.g. utm_source, fbclid — tracking params)
      3. If Vary header specified: append relevant header values to key
         (e.g. Vary: Accept-Encoding → append gzip/br/identity)

    TODO:
    1. Parse query string, remove strip_params, sort remaining params
    2. Reconstruct URL without fragment (fragments are client-side, never sent)
    3. Append vary_headers values (sorted by header name)
    4. Return normalized key string
    """
    # TODO: implement cache key normalization
    raise NotImplementedError("Implement normalize_cache_key")


# ---------------------------------------------------------------------------
# Step 4: CDN Concepts (discussion)
# ---------------------------------------------------------------------------

"""
CDN Architecture Concepts:

1. Points of Presence (PoPs):
   - Geographically distributed edge servers
   - Request routed to nearest PoP via anycast DNS or GeoDNS
   - Reduces RTT: user in Tokyo → Tokyo PoP (5ms) vs US origin (150ms)

2. Cache Hierarchy:
   - L1: Edge PoP (closest to user, smallest, many locations)
   - L2: Regional / Origin Shield (fewer, larger caches)
   - Origin: your actual servers

3. Cache-Control Headers:
   - Cache-Control: public, max-age=3600         → CDN caches 1hr
   - Cache-Control: private                       → CDN does NOT cache (per-user)
   - Cache-Control: no-store                      → never cache anywhere
   - Cache-Control: s-maxage=600, max-age=60      → CDN: 10min, browser: 1min
   - Cache-Control: stale-while-revalidate=60     → serve stale 60s while refreshing
   - Surrogate-Control: max-age=86400             → CDN-only TTL (Fastly/Varnish)

4. Surrogate Keys (Cache Tags):
   - Tag responses: Surrogate-Key: product:123 category:electronics
   - Purge all product:123 pages in one API call → instant invalidation
   - Used by Fastly, Cloudflare Cache Tags, Varnish xkey

5. Purge Strategies:
   - Purge-on-write: invalidate on every content change (complex, correct)
   - TTL-based: let entries expire naturally (simple, eventually stale)
   - Surrogate-key purge: purge by content relationship (scalable + correct)

6. Cache Miss Thundering Herd:
   - Many PoPs miss simultaneously → origin flood
   - Solutions: origin shield (coalescing), request queuing per key, SWR
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing EdgeCache...")
    cache = EdgeCache()

    # Cacheable response
    assert cache.put("/api/products", {"items": []}, "max-age=60") is True
    assert cache.get("/api/products") == {"items": []}, "should be a cache HIT"

    # private response should not be cached
    assert cache.put("/api/user/me", {"id": 1}, "private, max-age=60") is False
    assert cache.get("/api/user/me") is None, "private response should not be cached"

    # no-store response
    assert cache.put("/api/checkout", {}, "no-store") is False

    # Surrogate key purge
    cache.put("/api/products/1", {"id": 1}, "max-age=3600",
              surrogate_keys={"product:1", "category:electronics"})
    cache.put("/api/products/2", {"id": 2}, "max-age=3600",
              surrogate_keys={"product:2", "category:electronics"})
    purged = cache.purge_by_key("category:electronics")
    assert purged == 2, f"expected 2 purged, got {purged}"
    assert cache.get("/api/products/1") is None
    assert cache.get("/api/products/2") is None
    print("  EdgeCache: OK")

    print("Testing OriginShield (request coalescing)...")
    call_count = [0]

    def origin(key):
        call_count[0] += 1
        time.sleep(0.05)   # simulate origin latency
        return f"data:{key}"

    shield = OriginShield(origin_fn=origin, cache_ttl=60.0)

    results = []
    errors = []

    def fetch(key):
        try:
            results.append(shield.fetch(key))
        except Exception as e:
            errors.append(e)

    # 5 concurrent fetches for the same key
    threads = [threading.Thread(target=fetch, args=("/page/1",)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"unexpected errors: {errors}"
    assert all(r == "data:/page/1" for r in results), f"unexpected results: {results}"
    assert shield.origin_requests == 1, \
        f"coalescing should produce 1 origin request, got {shield.origin_requests}"
    print("  OriginShield: OK")

    print("Testing normalize_cache_key...")
    key1 = normalize_cache_key("/search?z=1&a=2&utm_source=email",
                                strip_params={"utm_source"})
    key2 = normalize_cache_key("/search?a=2&z=1",
                                strip_params={"utm_source"})
    assert key1 == key2, f"normalized keys should match: {key1!r} vs {key2!r}"

    key_vary = normalize_cache_key("/api/data",
                                   vary_headers={"Accept-Encoding": "gzip"})
    key_no_vary = normalize_cache_key("/api/data",
                                      vary_headers={"Accept-Encoding": "identity"})
    assert key_vary != key_no_vary, "different Accept-Encoding should produce different keys"
    print("  normalize_cache_key: OK")

    print("\nAll CDN caching tests passed!")


if __name__ == "__main__":
    _test()
