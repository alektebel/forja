# Reverse Proxy — Simple

## 1. What problem does it solve?

Clients connect directly to your application servers → security risk, no central
point for TLS, no compression, no caching, no rate limiting.

A reverse proxy sits between clients and application servers:
- Clients think they're talking to the proxy; the proxy forwards to backends
- Centralises TLS termination (one cert instead of N certs)
- Can add compression, caching, access control

**The job:** accept client requests → decide where to send them → forward →
return the response — with optional transformations.

## 2. How does it work?

### Request flow

```
Client → Proxy → Backend → Proxy → Client
```

1. Client sends HTTP request to proxy
2. Proxy parses the request, applies rules (routing, auth, rate limit)
3. Proxy forwards the request to the selected backend
4. Backend responds to the proxy
5. Proxy may transform the response (compress, strip headers)
6. Proxy returns response to client

### Routing

The proxy decides where to forward based on:

| Rule | Example |
|---|---|
| Host header | `api.example.com` → backend A, `app.example.com` → backend B |
| Path prefix | `/api/*` → backend A, `/*` → backend B (catch-all) |
| Header match | `X-Role=admin` → admin backend |
| Weight | 80% of traffic → version v1, 20% → version v2 |

### TLS termination

The proxy handles TLS, not the backends:
- Client ↔ Proxy (HTTPS, TLS 1.3)
- Proxy ↔ Backend (HTTP, no TLS — internal network)

Benefits:
- One certificate to manage instead of N
- Proxy can decrypt, inspect, re-encrypt
- Backends don't pay TLS cost

### Compression

The proxy can compress responses:
- `gzip` or `brotli` encoding
- Only compress if `Accept-Encoding` includes it
- Decompress if the backend sent it compressed and the proxy is forwarding

### Request buffering

The proxy can buffer:
- The full request body before forwarding (useful for auth checks)
- The full response before returning (useful for caching)
- Or stream directly (low latency, no buffering)

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Nginx** | Reverse proxy | `proxy_pass` directive; the world's most popular; high performance |
| **HAProxy** | L4/L7 proxy | More focused on LB; can also reverse proxy |
| **Caddy** | Reverse proxy | Auto-TLS (Let's Encrypt); `reverse_proxy` directive |
| **Traefik** | Reverse proxy + service discovery | Automatic config from Docker/K8s |
| **Envoy** | Sidecar proxy | xDS dynamic config; per-request filtering |
| **Squid** | Forward proxy (also reverse) | Primarily a cache; can act as reverse proxy |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| TLS termination | At proxy | End-to-end TLS (proxy decrypts, re-encrypts to backend) | Sensitive data → end-to-end; internal network → proxy terminates |
| Routing granularity | Path-based | Host-based | Multi-tenant apps → host-based; single app → path-based |
| Caching | Proxy caches responses | No proxy cache | Static content → cache; dynamic/API → no cache |
| Streaming | Buffer full response | Stream directly | Need caching/compression → buffer; low latency → stream |
| HTTP version | HTTP/1.1 to backend | HTTP/2 or HTTP/3 to backend | Modern backends → HTTP/2 for multiplexing |

## 5. Exercises

1. **HTTP reverse proxy**: A Python server that reads a request, forwards it to a backend URL (configured per path), returns the response.
2. **TLS termination**: Add HTTPS support to the proxy; accept a cert/key pair; forward plaintext to backends.
3. **Path-based routing**: Route `/api/*` to one backend, `/*` to another.
4. **Response compression**: Compress responses if the client accepts `gzip` or `brotli`.
5. **Request buffering**: Read the full request body before forwarding (useful for auth checks).

## 6. References

- [Nginx reverse proxy documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Caddy reverse_proxy documentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [TLS termination: "Reverse Proxy vs Forward Proxy" (Cloudflare blog)](https://www.cloudflare.com/learning/cdn/glossary/reverse-proxy/)
- [HTTP/2 multiplexing](https://httpwg.org/specs/rfc7540.html)
- [Caddy TLS automation](https://caddyserver.com/docs/automatic-https)