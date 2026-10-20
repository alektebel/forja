# Load Balancer — Simple

## 1. What problem does it solve?

You have N identical backend servers. One server cannot handle the load.
A load balancer (LB) sits between clients and backends and distributes incoming
requests so that no single backend is overwhelmed and failed backends are
skipped.

Without an LB: every client must know every backend's IP and pick one.
When a backend goes down, clients must retry. When you add/remove backends,
every client must update its list. The LB centralises that knowledge and
hides the failure from the client.

**The job:** accept connections from clients → forward one at a time to a
healthy backend → return the response.

## 2. How does it work?

### Routing algorithms

Algorithm | How it works | Good for | Bad for
---|---|---|---
Round-robin | Pick backend (i % N), increment i | Uniform backends | Ignores load/speed
Weighted round-robin | Each backend has a weight; sends `weight` requests then moves on | Mixed-capacity backends | Still ignores actual load
Least connections | Send to the backend with fewest active connections | Long-lived connections (websockets) | Needs connection counting
Least response time | Send to backend with lowest avg response time | When response time varies a lot | Needs response time tracking
Consistent hash | `hash(key) % N` maps a key to a backend | Session affinity, cache locality | Skewed keys cause hotspots

### Health checks

The LB must know which backends are healthy:
- **Active (push):** LB sends a probe (HTTP HEAD, TCP connect, custom script) on a timer.
  Backend returns OK/FAIL. After N consecutive failures, remove from pool.
  After M consecutive successes, add back.
- **Passive (pull):** Backends self-report health or the LB learns from failed responses.

### Session stickiness

Some backends cache session state. Stickiness pins a client to one backend:
- **Cookie-based:** LB writes `SERVERID=backend_id` cookie; client returns it.
- **Source IP hash:** `hash(client_ip) % N` — same IP → same backend.
- **Consistent hash:** `hash(session_id) % N` — same session → same backend.

When the pinned backend dies, re-hash to a new one.

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Nginx** | HTTP/7-layer | `upstream` block, `least_conn`, `ip_hash`. Reverse proxy too. |
| **HAProxy** | Layer 4 & 7 | Mature, battle-tested, health checks, stats page, ACL routing. |
| **Envoy** | Sidecar proxy | Dynamic config via xDS, per-request filters, widely used in service mesh. |
| **AWS ALB/NLB** | Cloud | Managed, scales automatically. ALB = HTTP, NLB = TCP. |
| **Traefik** | Reverse proxy | Automatic service discovery (Docker, Kubernetes, Consul). |
| **Envoy Proxy** | L4/L7 proxy | Per-request filtering, dynamic config, observability. |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Layer 4 vs Layer 7 | TCP (fastest, no HTTP parsing) | HTTP (content-based routing) | Need cookies/headers → L7 |
| Centralised vs decentralised | Single LB (reverse proxy) | Client-side LB (Consul Template, Eureka) | No single point of failure |
| Round-robin vs sticky | Even distribution | Session stays on same backend | Stateful backends, caching |
| Health check interval | 5s (react fast) | 30s (avoid flapping) | Unstable network → use longer interval |
| Graceful drain | Accept requests, finish them, then stop | Kill all connections instantly | Can't lose in-flight requests |

## 5. Exercises

1. **Round-robin LB in Python**: A TCP server that reads from 3 backend sockets and distributes requests round-robin.
2. **Least-connections LB**: Track active connections per backend; send to the one with the fewest.
3. **Consistent hash ring**: Implement a ring of virtual nodes (160 per physical node); adding/removing a node moves only a fraction of keys.
4. **Health-check loop**: Background goroutine/probe that tests each backend every 2s; remove after 3 failures, add back after 2 successes.
5. **Graceful drain**: On signal, stop accepting new connections, finish in-flight requests, then exit.

## 6. References

- [HAProxy architecture](http://docs.haproxy.org/dev/management.html)
- [Nginx upstream documentation](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Consistent hashing: "Consistent Hashing and Random Trees" (Karger et al., 1997)](https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.31.7207)
- [Envoy proxy documentation](https://www.envoyproxy.io/docs/envoy/latest/)