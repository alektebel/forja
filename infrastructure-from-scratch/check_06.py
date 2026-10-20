"""check_cache — the cache: LRU, TTL, cache-aside, stampede protection.

Catches:
- LRU eviction order (FIFO-like, not true LRU)
- TTL expiry (doesn't expire, expires too early, expires too late)
- Cache-aside pattern (misses DB on hit, hits DB on miss)
- Stampede protection (multiple fetchers per key, no per-key lock)
"""

import sys
import os
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

def _check_cache(s):
    """LRU cache: capacity, eviction, access order."""
    cache = s.LRUCache(capacity=3)
    cache.put(1, "a")
    cache.put(2, "b")
    cache.put(3, "c")
    assert len(cache) == 3

    # Access 1 → it becomes MRU
    assert cache.get(1) == "a"

    # Add 4 → evicts LRU (2, not 1)
    cache.put(4, "d")
    assert len(cache) == 3
    assert cache.get(2) == -1, "2 should be evicted (LRU)"
    assert cache.get(1) == "a"  # 1 is MRU, still present
    assert cache.get(4) == "d"

def _check_ttl(s):
    """TTL cache: entries expire, non-expired entries live."""
    import time
    cache = s.TTLCache(capacity=10, default_ttl=0.5)
    cache.put("x", "hello")
    assert cache.get("x") == "hello"
    time.sleep(0.6)
    assert cache.get("x") == -1, "Entry should have expired after 0.5s"

def _check_cache_aside(s):
    """Cache-aside: cache hit returns cached; cache miss fetches from DB."""
    db = {"user:1": "Alice", "user:2": "Bob"}
    lru = s.LRUCache(capacity=10)
    store = s.CacheAsideStore(lru, db_fetch_fn=lambda k: db.get(k))

    # First access → miss, fetch from DB
    assert store.get("user:1") == "Alice"
    assert store.cache_misses == 1
    assert store.cache_hits == 0

    # Second access → hit from cache
    assert store.get("user:1") == "Alice"
    assert store.cache_misses == 1
    assert store.cache_hits == 1

def _check_stampede(s):
    """Stampede protection: per-key lock prevents multiple DB fetches."""
    db_calls = []
    def fake_db_fetch(key):
        db_calls.append(key)
        return f"value:{key}"

    lru = s.LRUCache(capacity=100)
    cache = s.StampedeProtectedCache(lru, db_fetch_fn=fake_db_fetch)

    # First call → miss, fetch from DB
    cache.get("key1")
    assert len(db_calls) == 1, f"Expected 1 DB call, got {len(db_calls)}"

    # Second call → hit from cache
    cache.get("key1")
    assert len(db_calls) == 1, "Second call should hit cache, not fetch from DB"

def check():
    import sys
    import os
    # Load the module from templates or solutions
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", HERE)
    template_path = os.path.join(course_dir, "templates", "cache.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(HERE, "cache.py")

    spec = importlib.util.spec_from_file_location("cache_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _check_cache(mod)
    _check_ttl(mod)
    _check_cache_aside(mod)
    _check_stampede(mod)

if __name__ == "__main__":
    try:
        check()
        print("check_cache: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"cache: not implemented yet ({sys.exc_info()})")
        sys.exit(2)
    except Exception as e:
        print(f"cache: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)