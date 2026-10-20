"""
URL Shortener — From Scratch
=============================
Build a URL shortener service to understand:
- Base62 encoding for short codes
- Hash-based vs counter-based ID generation
- Redirect mechanics (301 vs 302)
- Caching hot URLs
- Handling expiry and click tracking
- Collision avoidance

Learning Path:
1. Implement base62 encoding/decoding
2. Implement counter-based ID → code (no collisions)
3. Implement random code generation with collision detection
4. Add in-memory storage with expiry (TTL)
5. Add LRU cache in front of storage for hot URLs
6. Add click tracking (hits counter)
7. Think about: how would you scale to 100M URLs?
   - Sharding strategy (by code hash)
   - Cache tier (Redis) for reads
   - Write path (single DB node or distributed counter)
"""

import time
import hashlib
import random
import string
from typing import Optional


# ---------------------------------------------------------------------------
# Step 1: Base62 encoding
# ---------------------------------------------------------------------------

BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase


def base62_encode(num: int) -> str:
    """Encode a non-negative integer to a base62 string.

    TODO:
    - Handle num == 0 as a special case → return BASE62_ALPHABET[0]
    - Repeatedly divide num by 62, prepend the remainder as a base62 digit
    - Return the accumulated string
    """
    # TODO: implement base62 encoding
    raise NotImplementedError("Implement base62_encode")


def base62_decode(code: str) -> int:
    """Decode a base62 string back to an integer.

    TODO:
    - Iterate over each character in code
    - Build up the integer: result = result * 62 + index_of_char
    - Return the result
    """
    # TODO: implement base62 decoding
    raise NotImplementedError("Implement base62_decode")


# ---------------------------------------------------------------------------
# Step 2: Storage layer
# ---------------------------------------------------------------------------

class URLStore:
    """Simple in-memory URL store.

    TODO:
    - Store mappings: code → {long_url, created_at, expires_at, hits}
    - Implement save(), get(), increment_hits()
    - On get(), check if expired and return None if so
    """

    def __init__(self):
        # TODO: initialize your storage dict
        pass

    def save(self, code: str, long_url: str, ttl_seconds: Optional[int] = None) -> None:
        """Store a mapping from code to long_url.

        TODO:
        - Record created_at = current time
        - If ttl_seconds provided, record expires_at = now + ttl_seconds
        - Initialize hits = 0
        """
        # TODO: implement save
        raise NotImplementedError("Implement URLStore.save")

    def get(self, code: str) -> Optional[str]:
        """Return the long_url for code, or None if not found / expired.

        TODO:
        - Look up code in storage
        - Check if expired (expires_at is set and now > expires_at)
        - Return long_url or None
        """
        # TODO: implement get
        raise NotImplementedError("Implement URLStore.get")

    def increment_hits(self, code: str) -> None:
        """Increment the hit counter for a code.

        TODO:
        - Safely increment hits if code exists
        """
        # TODO: implement increment_hits
        raise NotImplementedError("Implement URLStore.increment_hits")

    def get_stats(self, code: str) -> Optional[dict]:
        """Return stats dict for a code, or None if not found."""
        # TODO: return the full record for a code
        raise NotImplementedError("Implement URLStore.get_stats")


# ---------------------------------------------------------------------------
# Step 3: URL Shortener service
# ---------------------------------------------------------------------------

class URLShortener:
    """URL Shortener service combining encoding, storage, and caching.

    TODO:
    - Use an auto-incrementing counter to generate unique IDs
    - Encode IDs with base62 to produce short codes
    - Support custom aliases (user-provided short codes)
    - Integrate URLStore for persistence
    - Add a simple LRU cache (use cache.py's LRUCache) for hot redirects
    """

    def __init__(self, base_url: str = "https://short.ly"):
        self.base_url = base_url
        self._counter = 1000  # start counter away from 0 to get reasonable-length codes
        self._store = URLStore()
        # TODO: optionally add an LRU cache here

    def shorten(self, long_url: str, custom_code: Optional[str] = None,
                ttl_seconds: Optional[int] = None) -> str:
        """Shorten a URL and return the short URL.

        TODO:
        1. If custom_code provided:
           - Check it's not already taken
           - Use it directly
        2. Otherwise:
           - Increment _counter
           - Encode with base62 to get code
        3. Save to store with optional TTL
        4. Return f"{self.base_url}/{code}"
        """
        # TODO: implement shorten
        raise NotImplementedError("Implement URLShortener.shorten")

    def resolve(self, code: str) -> Optional[str]:
        """Resolve a short code to its long URL, or None if not found/expired.

        TODO:
        1. Check LRU cache first (cache-aside pattern)
        2. On miss, fetch from store
        3. On hit, populate cache and increment hits
        4. Return long_url or None
        """
        # TODO: implement resolve
        raise NotImplementedError("Implement URLShortener.resolve")

    def get_stats(self, code: str) -> Optional[dict]:
        """Return stats for a short code."""
        # TODO: delegate to store
        raise NotImplementedError("Implement URLShortener.get_stats")


# ---------------------------------------------------------------------------
# Step 4: Scale considerations (discussion, no code needed)
# ---------------------------------------------------------------------------

"""
Scale Discussion — think through these:

1. Storage:
   - 100M URLs * ~500 bytes/entry = ~50 GB → fits in a single DB
   - Use sharding by hash(code) if write QPS grows

2. Reads (redirects):
   - 1B redirects/day = ~11,600 QPS average, ~35,000 QPS peak
   - Cache top 20% of URLs (Pareto principle) → covers 80% of traffic
   - Use Redis as a fast cache layer (GET code → long_url in <1ms)

3. Writes (shorten):
   - 100M new URLs / 365 days ≈ 274K/day ≈ 3 writes/second → trivial

4. Redirect type:
   - 301 (permanent): browser caches → less server load but can't track clicks
   - 302 (temporary): browser always hits server → accurate analytics

5. ID generation at scale:
   - Single counter = bottleneck → use distributed ID gen (Snowflake-style)
   - Or: random 7-char base62 = 62^7 ≈ 3.5T possibilities, collision prob low
"""


# ---------------------------------------------------------------------------
# Simple self-test (replace TODOs above, then run: python url_shortener.py)
# ---------------------------------------------------------------------------

def _test():
    # Test base62
    assert base62_encode(0) == "0", "base62_encode(0) should return '0'"
    assert base62_encode(61) == "Z", "base62_encode(61) should return 'Z'"
    assert base62_encode(62) == "10", "base62_encode(62) should return '10'"
    assert base62_decode(base62_encode(12345)) == 12345, "round-trip should work"
    print("base62: OK")

    # Test store
    store = URLStore()
    store.save("abc", "https://example.com")
    assert store.get("abc") == "https://example.com"
    store.increment_hits("abc")
    assert store.get_stats("abc")["hits"] == 1
    print("URLStore: OK")

    # Test TTL expiry
    store.save("xyz", "https://expiring.com", ttl_seconds=1)
    assert store.get("xyz") == "https://expiring.com"
    time.sleep(1.1)
    assert store.get("xyz") is None, "expired URL should return None"
    print("TTL expiry: OK")

    # Test shortener
    svc = URLShortener()
    short = svc.shorten("https://www.example.com/very/long/path?query=param")
    print(f"Shortened: {short}")
    code = short.split("/")[-1]
    assert svc.resolve(code) == "https://www.example.com/very/long/path?query=param"
    print("URLShortener: OK")

    print("\nAll tests passed!")


if __name__ == "__main__":
    _test()
