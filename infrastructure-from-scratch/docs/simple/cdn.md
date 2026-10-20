# CDN — Simple

## 1. What problem does it solve?

A user in Tokyo downloading a 5MB image from a server in Virginia takes ~200ms.
Same request through a Tokyo PoP (Point of Presence) takes ~5ms if the image is
cached there.

A CDN (Content Delivery Network) distributes copies of static content across
many PoPs worldwide. When a user requests content:
1. DNS resolves to the nearest PoP
2. PoP serves from cache if available (hit)
3. If not, PoP fetches from origin, caches it, then serves

**The job:** reduce latency, reduce origin load, absorb traffic spikes.

## 2. How does it work?

### Caching fundamentals

Every cached object has a **cache key** and **cache policy**:

- **Cache key:** typically `scheme://host/path?query`.
  Must be normalised (lowercase host, sorted query params) or different URLs
  that refer to the same object become separate cache entries.

- **Cache policy** is dictated by HTTP headers the origin sets:

| Header | Meaning |
|---|---|
| `Cache-Control: max-age=3600` | Valid for 1 hour from last fetch |
| `Cache-Control: no-store` | Never cache |
| `Cache-Control: private` | Cache only for a single user (per-browser) |
| `S-Cache-Control: max-age=3600` | Origin shield / surrogate cache valid for 1 hour |
| `Cache-Control: stale-while-revalidate=60` | Serve stale for 60s while fetching new version |

### Cache lifecycle

```
1. MISS: PoP fetches from origin → stores → serves to client
2. HIT: PoP serves from cache (no origin fetch)
3. EXPIRED: Object past max-age; serve stale while revalidating
4. INVALIDATE: PoP purges specific URLs or cache-tags (Surrogate-Key)
5. EVICTION: Least-recently-used / least-frequently-used when cache is full
```

### Origin shield (cache coalescing)

Without an origin shield, every PoP fetches independently on a cache miss,
hammering the origin. An origin shield is a single PoP that all other PoPs
use as a shared upstream:
- PoP A misses → asks shield → shield fetches from origin → caches → serves A
- PoP B misses → asks shield → shield already has it → serves B instantly

This turns many misses into one origin fetch.

### Cache key normalisation

Two URLs that should map to the same cached object:
- `https://example.com/image.PNG` → `https://example.com/image.png`
- `https://example.com/path?a=1&b=2` → `https://example.com/path?a=1&b=2`

Without normalisation these become separate cache entries.

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Cloudflare** | CDN / edge platform | PoPs in 300+ cities; edge computing; WAF built in |
| **Fastly** | CDN / edge platform | VCL (Varnish Language) for custom logic; instant purge |
| **Amazon CloudFront** | AWS CDN | Integrated with S3, Lambda@Edge, Origin Shield |
| **Akamai** | Enterprise CDN | Oldest, largest, most customised; used by Fortune 500 |
| **Varnish Cache** | Open-source HTTP cache | In-process; VCL for custom logic; origin shield equivalent |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Cache duration | Short (5min) | Long (24h) | Frequently changing content → short TTL |
| Cache key strategy | Full URL | Hashed/digested URL | Avoid cache key collisions at scale |
| Purge granularity | Single URL | Cache tags (bulk purge) | When many URLs share a source (e.g. same product image) |
| PoP placement | Cloud-managed | Self-hosted at ISPs | Ultra-low latency for enterprise clients |
| Edge computing | No (pure cache) | Yes (Cloudflare Workers, Fastly VCL) | Need logic at edge (auth, rewrite, A/B) |

## 5. Exercises

1. **HTTP cache server**: A Python HTTP server that caches GET responses. Check `Cache-Control` headers and implement `max-age`, `stale-while-revalidate`, and `no-store`.
2. **Cache key normaliser**: Parse and normalise URLs: lowercase host, sort query params, strip default ports.
3. **Origin shield**: Simulate N PoPs with one shield PoP; measure origin fetches with and without shield.
4. **Cache tag purge**: Associate cached objects with tags; a purge-by-tag removes all objects with that tag.
5. **Cache stampede protection**: On cache miss for a key, only one origin fetch; others wait for the result (mutex per key).

## 6. References

- [MDN: HTTP caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
- [Fastly: HTTP caching concepts](https://docs.fastly.com/en/guides/http-caching)
- [Varnish Cache documentation](https://varnish-cache.org/docs/)
- [Cache stampede: "The Cache Stampede Problem" (Adya et al., 2002)](https://www.cs.cmu.edu/~jgrauw/papers/cache_stampede.pdf)
- [Origin Shield (Cloudflare)](https://developers.cloudflare.com/cache/origin-pull/)