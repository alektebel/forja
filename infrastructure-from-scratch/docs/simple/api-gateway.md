# API Gateway — Simple

## 1. What problem does it solve?

You have multiple backend services (user-service, order-service, payment-service).
Every client needs auth, rate limiting, CORS, request transformation, and logging.
Repeating this in every backend is duplication, drift, and security risk.

An API gateway is a single entry point that:
- Routes requests to the right service
- Authenticates and authorises callers
- Rate limits
- Transforms requests/responses (header mapping, body rewriting)
- Aggregates responses from multiple services
- Provides observability (metrics, logs, traces)

**The job:** the single door through which all API traffic flows, with
policy enforcement and transformation happening before the request reaches
the backend.

## 2. How does it work?

### Request lifecycle

```
Client → Gateway → [Auth] → [Rate Limit] → [Transform] → Backend → [Transform] → [Log] → Client
```

1. **Authentication**: Verify the caller's identity (API key, JWT, OAuth token)
2. **Authorisation**: Check if the caller has permission (scopes, roles)
3. **Rate limiting**: Reject if the caller exceeded their quota
4. **Transformation**: Rewrite paths, headers, or bodies; add missing fields
5. **Routing**: Forward to the correct backend service
6. **Aggregation**: Fetch from multiple backends, merge, return a single response
7. **Response transformation**: Strip sensitive headers, format JSON
8. **Observability**: Log, metrics, tracing

### Authentication patterns

| Pattern | How it works | Pros | Cons |
|---|---|---|---|
| API key | Client sends `X-API-Key: xyz` in header | Simple, no crypto | Key can be leaked, no identity |
| JWT (signed) | Client sends `Authorization: Bearer <token>`; gateway validates signature | No DB lookup, self-contained | Can't revoke without rotation |
| JWT (introspection) | Gateway calls an endpoint to validate the token | Can revoke, check scopes | Extra latency, single point of failure |
| OAuth 2.0 / OIDC | Full flow; gateway is a client, not a resource server | Standard, delegated auth | Complex, multiple hops |

### Request/response transformation

The gateway can rewrite:

| Transformation | Example |
|---|---|
| Path rewrite | `/users/123` → `GET /user?id=123` |
| Header mapping | `X-User-ID` → `X-Internal-User-ID` |
| Body enrichment | Add `tenant_id` to request body |
| Response filter | Remove `X-Secret-Header` from backend response |
| Aggregation | `GET /dashboard` → fetch `/profile` + `/orders` → merge |

### Rate limiting

The gateway enforces quotas per-caller (from the auth result):

| Algorithm | Description |
|---|---|
| Token bucket | Fixed refill rate; burst allowed up to bucket size |
| Sliding window log | Count requests in last N seconds; precise but memory-heavy |
| Sliding window counter | Coarse buckets; efficient, approximate |

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Kong** | Plugin-based gateway | Lua plugins; NGINX-based; supports OAuth2, JWT, rate-limiting |
| **APISIX** | Dynamic gateway | Apache project; hot-reload config; dynamic routing; plugin ecosystem |
| **AWS API Gateway** | Cloud-managed | Managed, auto-scaling; supports HTTP/API/WS/Lambda integrations |
| **Tyk** | Open-source gateway | Go-based; dashboard for analytics; plugin support |
| **Spring Cloud Gateway** | Java framework | Reactive; integrates with Spring ecosystem |
| **Kratos (ORY)** | Security suite | Authn/authz + gateway; modern, cloud-native |
| **Envoy + Gloo** | Sidecar gateway | Built on Envoy proxy; dynamic config; Kubernetes native |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Auth method | JWT (stateless) | JWT introspection (stateful) | Need revocation → introspection |
| Gateway location | Edge (public) | Internal (service mesh) | Public API → edge; internal → mesh |
| Routing | Static config | Dynamic (service discovery) | Static services → config; dynamic (K8s) → discovery |
| Performance | C-based (NGINX/Kong) | Go or Java (Tyk/Spring) | Max throughput → C; developer velocity → Go/Java |
| Plugin model | Lua (Kong) | Go (APISIX) or Java (Spring) | Lua ecosystem → Kong; Go → APISIX |

## 5. Exercises

1. **Simple gateway**: Routes `/users` → user-service, `/orders` → order-service; adds `X-Gateway-ID` header.
2. **JWT validation**: Parse `Authorization: Bearer <token>`, validate RSA signature, extract `sub` claim, pass it downstream.
3. **Rate limiter**: Per-API-key sliding window counter; reject with `429 Too Many Requests` when exceeded.
4. **Response transform**: Strip `X-Secret-Header` from all backend responses.
5. **Aggregator**: `GET /dashboard` fetches `/profile` and `/orders`, merges JSON, returns single response.

## 6. References

- [Kong documentation](https://docs.konghq.com/)
- [APISIX documentation](https://apisix.apache.org/docs/)
- [AWS API Gateway documentation](https://docs.aws.amazon.com/apigateway/)
- [OAuth 2.0 (RFC 6749)](https://datatracker.ietf.org/doc/html/rfc6749)
- [JWT (RFC 7519)](https://datatracker.ietf.org/doc/html/rfc7519)
- [Gloo Edge documentation](https://docs.solo.io/gloo-edge/)