"""
Cache — Complete Solution
"""

import time
import threading
from typing import Any, Dict, Optional, Callable


class _Node:
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev: Optional["_Node"] = None
        self.next: Optional["_Node"] = None


class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: Dict[Any, _Node] = {}
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    def _add_to_head(self, node: _Node) -> None:
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _remove_node(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_head(self, node: _Node) -> None:
        self._remove_node(node)
        self._add_to_head(node)

    def _remove_tail(self) -> _Node:
        node = self._tail.prev
        self._remove_node(node)
        return node

    def get(self, key: Any) -> Any:
        if key not in self._cache:
            return -1
        node = self._cache[key]
        self._move_to_head(node)
        return node.value

    def put(self, key: Any, value: Any) -> None:
        if key in self._cache:
            node = self._cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            node = _Node(key, value)
            self._cache[key] = node
            self._add_to_head(node)
            if len(self._cache) > self.capacity:
                tail = self._remove_tail()
                del self._cache[tail.key]

    def __len__(self) -> int:
        return len(self._cache)


class TTLCache:
    def __init__(self, capacity: int, default_ttl: Optional[float] = None):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self._inner = LRUCache(capacity)

    def get(self, key: Any) -> Any:
        result = self._inner.get(key)
        if result == -1:
            return -1
        value, expires_at = result
        if expires_at is not None and time.time() > expires_at:
            # Lazy expiry: treat as miss (node stays in cache until evicted)
            return -1
        return value

    def put(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl else None
        self._inner.put(key, (value, expires_at))


class CacheAsideStore:
    def __init__(self, cache: LRUCache, db_fetch_fn: Callable[[Any], Any]):
        self._cache = cache
        self._db_fetch = db_fetch_fn
        self.cache_hits = 0
        self.cache_misses = 0

    def get(self, key: Any) -> Any:
        cached = self._cache.get(key)
        if cached != -1:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        value = self._db_fetch(key)
        if value is not None:
            self._cache.put(key, value)
        return value

    def update(self, key: Any, value: Any) -> None:
        # Simulate DB write, then invalidate cache (delete-on-write)
        # In a real system: update DB here, then delete from cache
        # We use a sentinel to mark as invalid; real impl would store None or remove
        # For the LRUCache we don't have a delete method, so we store a tombstone
        # Simpler: just overwrite with None so next get returns None (miss)
        # Better: add delete() to LRUCache — shown here inline
        cache = self._cache
        if key in cache._cache:
            node = cache._cache.pop(key)
            cache._remove_node(node)

    @property
    def hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class StampedeProtectedCache:
    def __init__(self, cache: LRUCache, db_fetch_fn: Callable[[Any], Any]):
        self._cache = cache
        self._db_fetch = db_fetch_fn
        self._key_locks: Dict[Any, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _get_key_lock(self, key: Any) -> threading.Lock:
        with self._meta_lock:
            if key not in self._key_locks:
                self._key_locks[key] = threading.Lock()
            return self._key_locks[key]

    def get(self, key: Any) -> Any:
        # Fast path: check cache without lock
        cached = self._cache.get(key)
        if cached != -1:
            return cached

        # Slow path: acquire per-key lock
        key_lock = self._get_key_lock(key)
        with key_lock:
            # Double-check: another thread may have populated cache while we waited
            cached = self._cache.get(key)
            if cached != -1:
                return cached
            # We are the one thread that fetches from DB
            value = self._db_fetch(key)
            if value is not None:
                self._cache.put(key, value)
            return value


def _test():
    print("Testing LRUCache...")
    cache = LRUCache(capacity=3)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.put(3, "c")
    assert cache.get(1) == "a"
    cache.put(4, "d")
    assert cache.get(2) == -1
    assert cache.get(3) == "c"
    assert cache.get(4) == "d"
    assert len(cache) == 3
    print("  LRUCache: OK")

    print("Testing TTLCache...")
    ttl_cache = TTLCache(capacity=10, default_ttl=1.0)
    ttl_cache.put("x", "hello")
    assert ttl_cache.get("x") == "hello"
    time.sleep(1.1)
    assert ttl_cache.get("x") == -1
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
    assert lru.get("user:1") == -1
    print("  CacheAsideStore: OK")

    print("\nAll cache tests passed!")


if __name__ == "__main__":
    _test()
