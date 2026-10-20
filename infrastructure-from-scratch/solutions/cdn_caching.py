"""
CDN Caching — Complete Solution
"""

import time
import threading
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs, urlencode


class CacheEntry:
    def __init__(self, body: Any, max_age: float, surrogate_keys: Set[str],
                 stale_while_revalidate: float = 0.0):
        self.body = body
        self.stored_at: float = time.time()
        self.max_age = max_age
        self.stale_while_revalidate = stale_while_revalidate
        self.surrogate_keys = surrogate_keys
        self.revalidating = False


class EdgeCache:
    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if self._is_fresh(entry):
                return entry.body
            if self._is_stale_while_revalidate(entry):
                return entry.body   # serve stale; background revalidation omitted here
            return None

    def put(self, key: str, body: Any, cache_control: str = "max-age=60",
            surrogate_keys: Optional[Set[str]] = None) -> bool:
        directives = self._parse_cache_control(cache_control)

        if "no-store" in directives or "private" in directives:
            return False

        if "s-maxage" in directives:
            max_age = float(directives["s-maxage"])
        elif "max-age" in directives:
            max_age = float(directives["max-age"])
        elif "no-cache" in directives:
            max_age = 0.0
        else:
            max_age = 60.0

        swr = float(directives.get("stale-while-revalidate", 0))
        entry = CacheEntry(body, max_age, surrogate_keys or set(), swr)
        with self._lock:
            self._store[key] = entry
        return True

    def purge_by_key(self, surrogate_key: str) -> int:
        with self._lock:
            to_delete = [k for k, e in self._store.items()
                         if surrogate_key in e.surrogate_keys]
            for k in to_delete:
                del self._store[k]
        return len(to_delete)

    def purge(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
        return False

    def _is_fresh(self, entry: CacheEntry) -> bool:
        return (time.time() - entry.stored_at) < entry.max_age

    def _is_stale_while_revalidate(self, entry: CacheEntry) -> bool:
        age = time.time() - entry.stored_at
        return age < (entry.max_age + entry.stale_while_revalidate)

    def _parse_cache_control(self, header: str) -> Dict[str, str]:
        directives = {}
        for part in header.split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                directives[k.strip()] = v.strip()
            else:
                directives[part] = True
        return directives

    @property
    def size(self) -> int:
        return len(self._store)


class OriginShield:
    def __init__(self, origin_fn, cache_ttl: float = 60.0):
        self._cache = EdgeCache()
        self._origin = origin_fn
        self._ttl = cache_ttl
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_result: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self.origin_requests = 0

    def fetch(self, key: str) -> Any:
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        with self._lock:
            # Re-check after acquiring lock
            cached = self._cache.get(key)
            if cached is not None:
                return cached

            if key in self._inflight:
                event = self._inflight[key]
                # Wait outside lock
            else:
                event = threading.Event()
                self._inflight[key] = event
                event = None  # this thread is the fetcher

        if event is not None:
            event.wait()
            return self._inflight_result.get(key)

        # This thread fetches from origin
        try:
            result = self._origin(key)
            self.origin_requests += 1
            self._cache.put(key, result, f"max-age={int(self._ttl)}")
        finally:
            with self._lock:
                self._inflight_result[key] = result
                ev = self._inflight.pop(key, None)
            if ev:
                ev.set()
        return result


def normalize_cache_key(url: str, vary_headers: Optional[Dict[str, str]] = None,
                        strip_params: Optional[Set[str]] = None) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if strip_params:
        for p in strip_params:
            params.pop(p, None)
    sorted_query = urlencode(sorted(params.items()), doseq=True)
    normalized = parsed._replace(query=sorted_query, fragment="").geturl()
    if vary_headers:
        vary_part = "&".join(f"{k}={v}" for k, v in sorted(vary_headers.items()))
        normalized = f"{normalized}#{vary_part}"
    return normalized


def _test():
    print("Testing EdgeCache...")
    cache = EdgeCache()
    assert cache.put("/api/products", {"items": []}, "max-age=60") is True
    assert cache.get("/api/products") == {"items": []}
    assert cache.put("/api/user/me", {"id": 1}, "private, max-age=60") is False
    assert cache.get("/api/user/me") is None
    assert cache.put("/api/checkout", {}, "no-store") is False

    cache.put("/api/products/1", {"id": 1}, "max-age=3600",
              surrogate_keys={"product:1", "category:electronics"})
    cache.put("/api/products/2", {"id": 2}, "max-age=3600",
              surrogate_keys={"product:2", "category:electronics"})
    purged = cache.purge_by_key("category:electronics")
    assert purged == 2
    assert cache.get("/api/products/1") is None
    print("  EdgeCache: OK")

    print("Testing OriginShield...")
    call_count = [0]

    def origin(key):
        call_count[0] += 1
        time.sleep(0.05)
        return f"data:{key}"

    shield = OriginShield(origin_fn=origin, cache_ttl=60.0)
    results = []

    def fetch(key):
        results.append(shield.fetch(key))

    threads = [threading.Thread(target=fetch, args=("/page/1",)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r == "data:/page/1" for r in results)
    assert shield.origin_requests == 1
    print("  OriginShield: OK")

    print("Testing normalize_cache_key...")
    key1 = normalize_cache_key("/search?z=1&a=2&utm_source=email",
                                strip_params={"utm_source"})
    key2 = normalize_cache_key("/search?a=2&z=1", strip_params={"utm_source"})
    assert key1 == key2

    key_vary = normalize_cache_key("/api/data",
                                   vary_headers={"Accept-Encoding": "gzip"})
    key_no_vary = normalize_cache_key("/api/data",
                                      vary_headers={"Accept-Encoding": "identity"})
    assert key_vary != key_no_vary
    print("  normalize_cache_key: OK")

    print("\nAll CDN caching tests passed!")


if __name__ == "__main__":
    _test()
