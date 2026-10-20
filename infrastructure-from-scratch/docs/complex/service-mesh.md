# Service Mesh — Complex

## 1. What problem does it solve?

Each service needs:
- TLS encryption (mTLS between services)
- Retries with backoff
- Circuit breaker
- Observability (metrics, tracing, logging)
- Traffic splitting (canary, A/B testing)
- Rate limiting
- Fault injection (for testing)

Implementing this in every service:
- Code duplication across services
- Inconsistent policy enforcement
- Security risk (one missed config = vulnerability)
- Business logic mixed with infrastructure concerns

A service mesh moves these concerns into a sidecar proxy:
- Every service pod runs an Envoy proxy alongside it
- Traffic goes through the proxy; policy is enforced transparently
- Business logic stays clean; infrastructure moves to the mesh

**The job:** manage service-to-service communication transparently,
with policy enforcement and observability built into the network layer.

## 2. How does it work?

### Sidecar pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                     Service Pod                                   │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │  Service      │    │  Envoy       │                           │
│  │  (your app)   │◄──►│  (proxy)     │                           │
│  │              │    │              │                           │
│  │  Business    │    │  mTLS,        │                           │
│  │  Logic       │    │  Retries,     │                           │
│  │              │    │  Metrics,     │                           │
│  │              │    │  Tracing      │                           │
│  └──────────────┘    └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

Traffic flow:
```
Service A → Envoy A → mTLS → Envoy B → Service B
```

Envoy A encrypts → network → Envoy B decrypts.

### mTLS (mutual TLS)

Both sides verify each other's certificates:
1. Service A connects to Service B with its client certificate
2. Service B verifies Service A's certificate against the CA
3. Service B connects back to Service A with its certificate
4. Service A verifies Service B's certificate

Benefits:
- All intra-cluster traffic is encrypted
- Authentication via certificate (not IP or header)
- No code changes in the service

### Traffic management

| Feature | How it works |
|---|---|
| **Load balancing** | Round-robin, least-connections, weighted across instances |
| **Traffic splitting** | 90% → stable, 10% → canary |
| **Retries** | Retry N times with exponential backoff; only on specific status codes |
| **Timeouts** | Timeout per request; propagate to downstream |
| **Circuit breaker** | After N failures, stop sending requests to a backend for M seconds |
| **Fault injection** | Delay N% of requests; abort N% of requests (for testing resilience) |

### Observability

The mesh automatically captures:
- **Metrics**: request count, latency, error rate per service
- **Tracing**: span per service hop (OpenTelemetry/Jaeger)
- **Logging**: structured logs with trace IDs
- **Dashboards**: Grafana dashboards generated from mesh metrics

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Istio** | Service mesh | Kubernetes native; Istio sidecar; traffic management + security + observability |
| **Linkerd** | Service mesh | Lightweight; Rust proxy; auto-injection; 50KB binary |
| **Envoy** | Sidecar proxy | Not a mesh itself; but the proxy used by Istio, Gloo, etc. |
| **Consul Connect** | Service mesh + discovery | Built on Consul; mTLS; service discovery; health checks |
| **AppMesh** | AWS service mesh | AWS managed; integrates with CloudWatch, X-Ray |
| **Kuma** | Universal mesh | Cloud-agnostic; works outside K8s; multi-mesh |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Mesh type | Sidecar (Envoy) | Host network (Nginx) | Containerised → sidecar; simple → host network |
| Complexity | Istio (full mesh) | Linkerd (lightweight) | Need full features → Istio; need simplicity → Linkerd |
| mTLS | Auto-provisioned (Istio) | Manual (certificates) | Automated → Istio; simple dev → manual |
| Observability | Built-in (mesh) | External (instrument code) | No code changes → mesh; custom → instrument |
| Performance | Sidecar (extra hop) | No mesh (direct) | Need policy → sidecar; max performance → no mesh |

## 5. Exercises

1. **mTLS proxy**: Two services communicate over TLS; both present certificates; verify each other.
2. **Traffic splitter**: Forward N% of traffic to version A, (100-N)% to version B.
3. **Retries with backoff**: Retry failed requests up to N times with exponential backoff.
4. **Circuit breaker**: Track failures per destination; after N failures, reject requests for M seconds.
5. **Distributed tracing**: Add a `trace_id` header to every request; propagate across service hops; log it.

## 6. References

- [Istio documentation](https://istio.io/latest/docs/)
- [Linkerd documentation](https://linkerd.io/2/tasks/)
- [Envoy documentation](https://www.envoyproxy.io/docs/envoy/)
- [mTLS: mutual TLS](https://www.ory.sh/docs/ecosystem/tls/mutual-tls)
- [Service mesh: what it is and why it matters (Martin Fowler)](https://www.martinfowler.com/articles/microservices.html)
- [Kuma documentation](https://kuma.io/docs/)