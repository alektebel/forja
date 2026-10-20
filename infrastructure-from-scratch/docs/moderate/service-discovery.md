# Service Discovery — Moderate

## 1. What problem does it solve?

In a dynamic environment (containers, serverless, auto-scaling), backends
change IPs frequently. The LB can't hardcode IP lists.

Service discovery solves this:
- When a service starts, it **registers** its address (host:port) with a registry
- When a service stops, it **deregisters**
- When a service needs to find others, it **queries** the registry

**The job:** maintain a live map of "which backend is at which address"
and provide it to consumers (LB, clients, orchestrators).

## 2. How does it work?

### Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Service  │    │ Service  │    │ Service  │
│ A (start)│    │ B (stop) │    │ C (query)│
│ register │    │ deregister│   │ lookup A │
└────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │
     ▼               ▼               ▼
┌──────────────────────────────────────────┐
│           Registry (e.g. Consul)            │
│                                          │
│  A → [10.0.1.1:8080]                     │
│  B → [10.0.1.2:8080]                     │
│  C → [10.0.1.3:8080]                     │
└──────────────────────────────────────────┘
```

### Registration

A service registers on startup:
```json
{
  "service": "user-service",
  "id": "user-service-3",
  "address": "10.0.1.3",
  "port": 8080,
  "tags": ["v2", "prod"],
  "health_check": "http://10.0.1.3:8080/health"
}
```

Registration expires after a TTL; the service must send periodic heartbeats.

### Health checks

The registry performs health checks:
- **Agent-based**: A local agent on each node pings the service
- **Server-based**: The registry itself pings the service endpoint
- **Deregister on failure**: After N consecutive failures, remove from registry

Types:
| Type | How it works |
|---|---|
| HTTP | GET /health → expect 200 |
| TCP | Connect to port → expect open |
| gRPC | Call HealthCheck → expect OK |
| Script | Run a shell script → exit 0 = healthy |

### Service discovery (query)

A client queries the registry for all healthy instances of a service:
```json
{
  "service": "user-service",
  "instances": [
    {"address": "10.0.1.1", "port": 8080, "healthy": true},
    {"address": "10.0.1.2", "port": 8080, "healthy": true},
    {"address": "10.0.1.3", "port": 8080, "healthy": false}
  ]
}
```

The client then picks one (round-robin, random, least-connections).

### Consistency

The registry must be:
- **Available**: always answer queries (even if some nodes are down)
- **Consistent**: all nodes agree on the current service list

This is the CAP trade-off:
| Type | Consistency | Availability | Trade-off |
|---|---|---|---|
| **Strong** | Strong | May reject queries during partition | Consensus-based (etcd, ZooKeeper) |
| **Eventual** | Weak (replication lag) | High (read from any node) | AP system (Consul, Eureka) |

### DNS-based vs API-based

| Approach | Pros | Cons |
|---|---|---|
| **DNS** | Simple; every client can use it | DNS caching; slow to update |
| **HTTP API** | Fast, flexible queries | Client must know the API |
| **gRPC** | Strongly typed; streaming updates | Requires gRPC client |

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **HashiCorp Consul** | Service mesh + discovery | DNS + HTTP API; health checks; key-value store; distributed (Raft) |
| **etcd** | Key-value store (K8s uses it) | Strong consistency; watch for updates; used by Kubernetes |
| **Apache ZooKeeper** | Coordination service | Strong consistency; ZNodes; ACLs; used by Kafka |
| **Eureka** | Client-side discovery (Netflix) | Eventual consistency; client caches; used in Spring Cloud |
| **Consul DNS** | DNS-based | Convert service names to DNS records; TTL-based |
| **Kubernetes Service** | Built-in discovery | DNS-based; in-cluster; integrates with K8s networking |
| **Consul Template** | Template-based | Watches registry; generates config (Nginx, HAProxy) on update |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Registry type | Strong consistency (etcd) | Eventual (Consul, Eureka) | Need exact state → strong; scale → eventual |
| Client caching | Cache with TTL | Always query registry | High QPS → cache; low QPS → always query |
| Health check | HTTP endpoint | TCP connect | App-level health → HTTP; basic → TCP |
| Registration | Manual config | Auto-registration (K8s, Nomad) | Containerised → auto; VM → manual |
| Query method | DNS | HTTP/gRPC API | Simple clients → DNS; programmatic → API |

## 5. Exercises

1. **Simple registry**: A Python server that accepts register/deregister/lookup calls; stores service name → list of (address, port, healthy).
2. **Health check loop**: Background task that pings each service's health endpoint; marks unhealthy after N failures.
3. **Distributed registry**: Two registry nodes; replicate service registrations using a simple leader-follower protocol.
4. **DNS resolver**: Accept DNS queries for `service.internal`; return the healthy backend IPs.
5. **Auto-deregistration**: Services must send heartbeats; after TTL expires, remove them.

## 6. References

- [HashiCorp Consul documentation](https://developer.hashicorp.com/consul/docs)
- [etcd documentation](https://etcd.io/docs/)
- [Apache ZooKeeper documentation](https://zookeeper.apache.org/doc/current/)
- [Netflix Eureka documentation](https://netflix.github.io/eureka/)
- [Kubernetes Service documentation](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Consul DNS documentation](https://developer.hashicorp.com/consul/docs/connect/dns)