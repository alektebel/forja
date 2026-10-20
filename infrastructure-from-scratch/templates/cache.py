"""
Cache — From Scratch
======================
Build caching implementations to understand:
- LRU (Least Recently Used) eviction policy
- LFU (Least Frequently Used) eviction policy
- Cache-aside pattern (lazy population)
- TTL (time-to-live) with lazy expiry
- Cache stampede (thundering herd) protection
- Write-through and write-back patterns

Learning Path:
1. Implement LRU cache with O(1) get/put using dict + doubly-linked list
2. Add TTL support to LRU cache
3. Implement cache-aside pattern against a fake "database"
4. Add stampede protection with per-key locking
5. Implement LFU cache
6. Think about: Redis data structures (strings, hashes, sorted sets)
"""

import time
import threading
from typing import Any, Dict, Optional, Callable


# ---------------------------------------------------------------------------
# Step 1: LRU Cache
# ---------------------------------------------------------------------------

class _Node:
    """Doubly-linked list node for LRU cache."""
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev: Optional["_Node"] = None
        self.next: Optional["_Node"] = None


class LRUCache:
    """LRU Cache with O(1) get and put.

    Implementation: dict (key → node) + doubly-linked list
    - Most recently used node is at HEAD (right of sentinel head)
    - Least recently used node is at TAIL (left of sentinel tail)
    - On access: move node to HEAD
    - On eviction: remove TAIL

    TODO:
    1. Initialize head and tail sentinel nodes linked to each other
    2. Implement _add_to_head(node): insert node right after head sentinel
    3. Implement _remove_node(node): unlink node from list
    4. Implement _move_to_head(node): _remove_node + _add_to_head
    5. Implement _remove_tail(): unlink the node before tail sentinel
    6. Implement get(key): return value or -1; move accessed node to head
    7. Implement put(key, value): update if exists; add new node at head;
       evict tail node if over capacity
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: Dict[Any, _Node] = {}
        # TODO: create head and tail sentinel nodes and link them
        self._head = _Node()  # sentinel head
        self._tail = _Node()  # sentinel tail
        # TODO: link head ↔ tail

    def _add_to_head(self, node: _Node) -> None:
        """Insert node right after head sentinel (= most recently used position).

        TODO: update pointers: head ↔ node ↔ (old first node)
        """
        # TODO: implement _add_to_head
        raise NotImplementedError("Implement _add_to_head")

    def _remove_node(self, node: _Node) -> None:
        """Unlink node from the doubly-linked list.

        TODO: update prev and next pointers to skip over this node
        """
        # TODO: implement _remove_node
        raise NotImplementedError("Implement _remove_node")

    def _move_to_head(self, node: _Node) -> None:
        """Move an existing node to the head (mark as most recently used)."""
        # TODO: call _remove_node then _add_to_head
        raise NotImplementedError("Implement _move_to_head")

    def _remove_tail(self) -> _Node:
        """Remove and return the node before the tail sentinel (= LRU node)."""
        # TODO: implement _remove_tail
        raise NotImplementedError("Implement _remove_tail")

    def get(self, key: Any) -> Any:
        """Return value for key, or -1 if not present. Moves key to MRU position.

        TODO:
        1. Look up key in _cache
        2. If not found, return -1
        3. Move found node to head
        4. Return node.value
        """
        # TODO: implement get
        raise NotImplementedError("Implement LRUCache.get")

    def put(self, key: Any, value: Any) -> None:
        """Insert or update key-value pair. Evicts LRU entry if over capacity.

        TODO:
        1. If key exists: update value, move to head
        2. Else: create new node, add to head, add to _cache
        3. If len(_cache) > capacity: remove tail node and delete from _cache
        """
        # TODO: implement put
        raise NotImplementedError("Implement LRUCache.put")

    def __len__(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# Step 2: LRU Cache with TTL
# ---------------------------------------------------------------------------

class TTLCache:
    """LRU Cache with TTL-based expiry.

    TTL entries are expired lazily (on access) and eagerly on put when over capacity.

    TODO:
    1. Store (value, expires_at) per key instead of just value
    2. On get: check if expired → delete and return -1
    3. On put: store expires_at = now + ttl if ttl provided
    """

    def __init__(self, capacity: int, default_ttl: Optional[float] = None):
        self.capacity = capacity
        self.default_ttl = default_ttl
        # TODO: you can reuse LRUCache internally or re-implement with expiry
        # Hint: store (value, expires_at) as the value in LRUCache

    def get(self, key: Any) -> Any:
        """Return value or -1 if not found or expired.

        TODO: check expiry on access (lazy expiry)
        """
        # TODO: implement get with TTL check
        raise NotImplementedError("Implement TTLCache.get")

    def put(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """Insert or update with optional TTL (seconds).

        TODO: compute expires_at = now + (ttl or default_ttl); store pair
        """
        # TODO: implement put with TTL
        raise NotImplementedError("Implement TTLCache.put")


# ---------------------------------------------------------------------------
# Step 3: Cache-Aside Pattern
# ---------------------------------------------------------------------------

class CacheAsideStore:
    """Demonstrates the cache-aside (lazy loading) pattern.

    The application manages the cache explicitly:
      1. Check cache for key
      2. On HIT: return cached value
      3. On MISS: fetch from DB, write to cache, return value

    TODO:
    - Implement get() using the cache-aside pattern
    - Implement update() that invalidates the cache on write (delete on write)
    - Track cache_hits and cache_misses for observability
    """

    def __init__(self, cache: LRUCache, db_fetch_fn: Callable[[Any], Any]):
        """
        Args:
            cache: an LRUCache instance
            db_fetch_fn: function that fetches a value from the "database" by key
        """
        self._cache = cache
        self._db_fetch = db_fetch_fn
        self.cache_hits = 0
        self.cache_misses = 0

    def get(self, key: Any) -> Any:
        """Fetch with cache-aside: cache first, then DB on miss.

        TODO:
        1. Try cache.get(key)
        2. If hit (not -1): increment cache_hits, return value
        3. If miss: increment cache_misses, call _db_fetch(key)
        4. Store in cache, return value
        """
        # TODO: implement cache-aside get
        raise NotImplementedError("Implement CacheAsideStore.get")

    def update(self, key: Any, value: Any) -> None:
        """Update DB and invalidate cache (delete-on-write strategy).

        TODO:
        - Simulate DB write (you can just note it in a comment)
        - Invalidate cache entry so next read is a miss and re-fetches fresh data
        - Alternative: write-through would update cache here instead of deleting
        """
        # TODO: implement update with cache invalidation
        raise NotImplementedError("Implement CacheAsideStore.update")

    @property
    def hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Step 4: Cache Stampede Protection
# ---------------------------------------------------------------------------

class StampedeProtectedCache:
    """Cache with per-key locking to prevent stampede (thundering herd).

    Problem: Many concurrent requests miss on the same key simultaneously,
    all go to DB at once → DB overload.

    Solution: Only one request fetches from DB per key; others wait for result.

    TODO:
    - Use a dict of per-key locks (threading.Lock or threading.Event)
    - On miss: acquire lock; re-check cache (another thread may have populated);
      if still miss, fetch from DB, populate cache, release lock
    - Other threads wait on the lock/event and read from cache once unlocked
    """

    def __init__(self, cache: LRUCache, db_fetch_fn: Callable[[Any], Any]):
        self._cache = cache
        self._db_fetch = db_fetch_fn
        self._key_locks: Dict[Any, threading.Lock] = {}
        self._meta_lock = threading.Lock()  # protects _key_locks dict

    def _get_key_lock(self, key: Any) -> threading.Lock:
        """Get or create a per-key lock."""
        # TODO: safely get-or-create a lock for this key
        raise NotImplementedError("Implement _get_key_lock")

    def get(self, key: Any) -> Any:
        """Fetch with stampede protection.

        TODO:
        1. Check cache (no lock needed for read)
        2. If hit, return immediately
        3. Get per-key lock; acquire it
        4. Re-check cache (double-checked locking) — another thread may have filled it
        5. If still miss: fetch from DB, put in cache
        6. Release lock; return value
        """
        # TODO: implement stampede-protected get
        raise NotImplementedError("Implement StampedeProtectedCache.get")


# ---------------------------------------------------------------------------
# Step 5: Scale & Redis Concepts (discussion)
# ---------------------------------------------------------------------------

"""
Redis Key Concepts (implement in your mind, or run a real Redis):

Data Structures:
  - STRING:      SET key value EX 60  (with TTL)
  - HASH:        HSET user:1 name "Alice" age 30
  - LIST:        LPUSH queue item; BRPOP queue 0  (blocking pop — message queue)
  - SET:         SADD seen_ids msg123  (dedup set)
  - SORTED SET:  ZADD leaderboard 1500 user:42  (score → rank)

Eviction Policies (maxmemory-policy):
  - allkeys-lru:    evict any key LRU (recommended for cache)
  - volatile-lru:   evict only keys with TTL set, LRU order
  - allkeys-lfu:    evict any key by least frequency (Redis 4+)
  - noeviction:     return error when full (for durable stores)

Cache Patterns:
  - Cache-aside (lazy): app manages cache; stale on write unless invalidated
  - Write-through: write to cache AND DB synchronously; consistent but slower writes
  - Write-back: write to cache only; async flush to DB; fast writes, risk of data loss

CDN Basics:
  - Edge PoPs cache static/dynamic responses close to users
  - Cache-Control: public, max-age=3600  → CDN caches for 1 hour
  - Cache-Control: private               → CDN does NOT cache (per-user content)
  - Surrogate-Key / Cache-Tag: tag objects for bulk purge (e.g. purge all /product/* pages)
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing LRUCache...")
    cache = LRUCache(capacity=3)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.put(3, "c")
    assert cache.get(1) == "a"   # access 1 → now 1 is MRU
    cache.put(4, "d")            # evict LRU = 2
    assert cache.get(2) == -1, "2 should be evicted"
    assert cache.get(3) == "c"
    assert cache.get(4) == "d"
    assert len(cache) == 3
    print("  LRUCache: OK")

    print("Testing TTLCache...")
    ttl_cache = TTLCache(capacity=10, default_ttl=1.0)
    ttl_cache.put("x", "hello")
    assert ttl_cache.get("x") == "hello"
    time.sleep(1.1)
    assert ttl_cache.get("x") == -1, "entry should have expired"
    print("  TTLCache: OK")

    print("Testing CacheAsideStore...")
    db = {"user:1": "Alice", "user:2": "Bob"}
    lru = LRUCache(capacity=10)
    store = CacheAsideStore(lru, db_fetch_fn=lambda k: db.get(k))
    assert store.get("user:1") == "Alice"
    assert store.cache_misses == 1
    assert store.get("user:1") == "Alice"
    assert store.cache_hits == 1
    assert store.hit_ratio == 0.5
    store.update("user:1", "Alicia")
    assert lru.get("user:1") == -1, "cache should be invalidated after update"
    print("  CacheAsideStore: OK")

    print("\nAll cache tests passed!")


if __name__ == "__main__":
    _test()
