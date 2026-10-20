"""
URL Shortener — Complete Solution
"""

import time
import string
from typing import Optional

BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase


def base62_encode(num: int) -> str:
    if num == 0:
        return BASE62_ALPHABET[0]
    result = []
    while num:
        result.append(BASE62_ALPHABET[num % 62])
        num //= 62
    return "".join(reversed(result))


def base62_decode(code: str) -> int:
    idx = {c: i for i, c in enumerate(BASE62_ALPHABET)}
    result = 0
    for c in code:
        result = result * 62 + idx[c]
    return result


class URLStore:
    def __init__(self):
        self._data: dict = {}

    def save(self, code: str, long_url: str, ttl_seconds: Optional[int] = None) -> None:
        now = time.time()
        self._data[code] = {
            "long_url": long_url,
            "created_at": now,
            "expires_at": now + ttl_seconds if ttl_seconds else None,
            "hits": 0,
        }

    def get(self, code: str) -> Optional[str]:
        entry = self._data.get(code)
        if entry is None:
            return None
        if entry["expires_at"] and time.time() > entry["expires_at"]:
            del self._data[code]
            return None
        return entry["long_url"]

    def increment_hits(self, code: str) -> None:
        if code in self._data:
            self._data[code]["hits"] += 1

    def get_stats(self, code: str) -> Optional[dict]:
        return self._data.get(code)


class URLShortener:
    def __init__(self, base_url: str = "https://short.ly"):
        self.base_url = base_url
        self._counter = 1000
        self._store = URLStore()
        # Simple dict-based LRU substitute (full LRU in cache.py solution)
        self._cache: dict = {}
        self._cache_max = 1000

    def shorten(self, long_url: str, custom_code: Optional[str] = None,
                ttl_seconds: Optional[int] = None) -> str:
        if custom_code:
            if self._store.get(custom_code) is not None:
                raise ValueError(f"Code '{custom_code}' is already taken")
            code = custom_code
        else:
            self._counter += 1
            code = base62_encode(self._counter)
        self._store.save(code, long_url, ttl_seconds)
        return f"{self.base_url}/{code}"

    def resolve(self, code: str) -> Optional[str]:
        if code in self._cache:
            self._store.increment_hits(code)
            return self._cache[code]
        long_url = self._store.get(code)
        if long_url:
            if len(self._cache) >= self._cache_max:
                # Evict one entry (simple strategy: pop arbitrary)
                self._cache.pop(next(iter(self._cache)))
            self._cache[code] = long_url
            self._store.increment_hits(code)
        return long_url

    def get_stats(self, code: str) -> Optional[dict]:
        return self._store.get_stats(code)


def _test():
    assert base62_encode(0) == "0"
    assert base62_encode(61) == "Z"
    assert base62_encode(62) == "10"
    assert base62_decode(base62_encode(12345)) == 12345
    print("base62: OK")

    store = URLStore()
    store.save("abc", "https://example.com")
    assert store.get("abc") == "https://example.com"
    store.increment_hits("abc")
    assert store.get_stats("abc")["hits"] == 1
    print("URLStore: OK")

    store.save("xyz", "https://expiring.com", ttl_seconds=1)
    assert store.get("xyz") == "https://expiring.com"
    time.sleep(1.1)
    assert store.get("xyz") is None
    print("TTL expiry: OK")

    svc = URLShortener()
    short = svc.shorten("https://www.example.com/very/long/path?query=param")
    print(f"Shortened: {short}")
    code = short.split("/")[-1]
    assert svc.resolve(code) == "https://www.example.com/very/long/path?query=param"
    print("URLShortener: OK")

    print("\nAll tests passed!")


if __name__ == "__main__":
    _test()
