# Infrastructure From Scratch — Course Contract

## Laws

1. stdlib only. No external packages.
2. No float, no `/` between ints (truncating `//` only).
3. No banned imports: `math, statistics, decimal, fractions, random, time, datetime, os, uuid, socket, subprocess, secrets, shutil, tempfile, pathlib` (check/mutate harness files may use `os/sys/shutil/tempfile`).
4. No module-level mutable state.
5. The estate (test data) is read-only.
6. A refused call raises naming the offender.
7. The grader — `course.check_N`, reached by `check_NN.py` — must report TODO on the template stub and PASS on the solution.
8. Each `mutate_NN.py` holds anchored mutations — exact, once-occurring solution lines replaced with wrong-behaviour variants — and every one must be caught by the shipped grader. `mutate_all.py` prints the measured caught/total per battery; nothing is claimed that was not run.

> **Honesty note.** Laws 2–3 are the house ideal; this course's material was
> imported from `system-design/` and does not conform to them — the topic
> modules use `time`, floats, and threads because TTLs and rate windows are
> wall-clock phenomena. The conformance debt is recorded, not hidden, and
> rewriting the material to the laws is a separate unit of work.

## Course: Infrastructure From Scratch

A graded course covering the 18 core building blocks of distributed systems.
Each component is a stage. Each stage has a template (stub with `raise NotImplementedError`) and a solution (working implementation).

## World (the estate)

```python
# estate.py — the test data and scenarios that define correctness.
# This is the ground truth. Every stage's checks hold against it.

# Load Balancer estate
LB_BACKENDS = [
    {"id": "backend-1", "address": "10.0.0.1:8080", "healthy": True, "active": 0},
    {"id": "backend-2", "address": "10.0.0.2:8080", "healthy": True, "active": 0},
    {"id": "backend-3", "address": "10.0.0.3:8080", "healthy": False, "active": 0},
]
LB_ROUNDS = 100  # number of requests to distribute

# CDN estate
CDN_OBJECTS = {
    "style.css": {"body": b"body { color: black; }", "ttl": 3600},
    "app.js":    {"body": b"console.log('hello');", "ttl": 3600},
    "data.json": {"body": b'{"key": "value"}',     "ttl": 60},
}
CDN_HEADERS = {
    "style.css": {"cache-control": "public, max-age=3600"},
    "app.js":    {"cache-control": "public, max-age=3600"},
    "data.json": {"cache-control": "public, max-age=60"},
}

# Object Storage estate
OBJECTS = {
    "bucket1/image.png": b"\x89PNG\r\n\x1a\n...",
    "bucket1/readme.txt": b"Hello, World!",
    "bucket2/backup.tar": b"binary data here...",
}
OBJ_STORE_SIZE = 1024 * 1024 * 1024  # 1GB capacity

# Reverse Proxy estate
RP_ROUTES = {
    "/api":   {"backend": "http://10.0.0.10:3000"},
    "/app":   {"backend": "http://10.0.0.11:8080"},
    "/":      {"backend": "http://10.0.0.12:4000"},
}
RP_REQUESTS = [
    {"method": "GET", "path": "/api/users", "headers": {"Host": "api.example.com"}},
    {"method": "POST", "path": "/app/login", "headers": {"Host": "app.example.com"}},
    {"method": "GET", "path": "/health", "headers": {"Host": "example.com"}},
]

# API Gateway estate
GW_ROUTES = {
    "/users":   {"backend": "http://user-service:8080", "auth": True},
    "/orders":  {"backend": "http://order-service:8080", "auth": True},
    "/public":  {"backend": "http://public-service:8080", "auth": False},
}
GW_RATE_LIMITS = {
    "api-key-1": {"limit": 100, "window": 60},
    "api-key-2": {"limit": 50,  "window": 60},
}
GW_HEADERS_TO_STRIP = ["X-Powered-By", "Server"]

# Caching Layer estate (covers cache.py + cdn_caching.py + throttling.py)
CACHE_STAMPDE = {
    "key1": {"value": "v1", "ttl": 300},
    "key2": {"value": "v2", "ttl": 600},
}
CACHE_OPERATIONS = [
    ("get", "key1"), ("get", "key1"),  # hit, hit
    ("get", "missing"),  # miss → populate
    ("put", "key3", "v3", 300),  # new with TTL
]

# Message Queue estate (covers message_queue.py + idempotency_keys.py)
MQ_MESSAGES = [
    {"id": "msg-1", "payload": {"action": "charge", "amount": 100}},
    {"id": "msg-2", "payload": {"action": "charge", "amount": 200}},
    {"id": "msg-3", "payload": {"action": "refund", "amount": 50}},
]

# Rate Limiter estate (covers rate_limiter.py + throttling.py)
RL_LIMITS = {
    "user-1": {"limit": 10,  "window": 60},
    "user-2": {"limit": 20,  "window": 60},
    "user-3": {"limit": 50,  "window": 60},
}
RL_REQUESTS = [
    ("user-1", i) for i in range(15)  # 15 requests, limit 10
]

# Read Replicas estate (covers eventual_consistency.py + session_stickiness.py)
RR_REPLICAS = [
    {"id": "primary",   "role": "primary",   "write": True,  "read": True},
    {"id": "replica-1", "role": "replica",   "write": False, "read": True},
    {"id": "replica-2", "role": "replica",   "write": False, "read": True},
]
RR_DATA = {"x": 1, "y": 2, "z": 3}

# Service Discovery estate (covers consistent_hash.py + edge_computing.py)
SD_NODES = [
    {"id": "svc-1", "address": "10.0.1.1:8080", "healthy": True, "tags": ["v1", "prod"]},
    {"id": "svc-2", "address": "10.0.1.2:8080", "healthy": True, "tags": ["v1", "prod"]},
    {"id": "svc-3", "address": "10.0.1.3:8080", "healthy": False, "tags": ["v1", "prod"]},
]

# Database Sharding estate (covers hot_partition_mitigation.py + data_locality.py)
SHARD_KEYS = [f"user-{i}" for i in range(1000)]
SHARD_COUNT = 10

# Event-Driven Architecture estate (covers request_batching.py + leaderboad.py)
EDA_EVENTS = [
    {"type": "order.created", "data": {"order_id": 1, "total": 100}},
    {"type": "order.created", "data": {"order_id": 2, "total": 200}},
    {"type": "payment.received", "data": {"order_id": 1, "amount": 100}},
    {"type": "order.created", "data": {"order_id": 3, "total": 150}},
]

# Search Index estate (covers cdn_caching.py + url_shortener.py)
SEARCH_DOCS = [
    {"id": "doc1", "title": "Introduction to Databases", "body": "A guide to database systems"},
    {"id": "doc2", "title": "Search Engine Basics", "body": "How search engines work"},
    {"id": "doc3", "title": "Database Indexing", "body": "Understanding database indexes"},
]

# Service Mesh estate (covers cache.py + throttling.py)
MESH_SERVICES = [
    {"id": "svc-a", "address": "10.0.2.1:8080", "healthy": True},
    {"id": "svc-b", "address": "10.0.2.2:8080", "healthy": True},
    {"id": "svc-c", "address": "10.0.2.3:8080", "healthy": False},
]

# Cache Invalidation estate (covers cdn_caching.py + eventuate_consistency.py)
CACHE_WITH_TAGS = {
    "article:1":  {"tags": ["article", "tech"], "value": "v1", "ttl": 300},
    "article:2":  {"tags": ["article", "tech"], "value": "v2", "ttl": 300},
    "article:3":  {"tags": ["article", "science"], "value": "v3", "ttl": 300},
}

# Sagas estate (covers message_queue.py + idempotency_keys.py)
SAGA_STEPS = [
    {"name": "create_order", "compensate": "cancel_order"},
    {"name": "reserve_inventory", "compensate": "release_inventory"},
    {"name": "process_payment", "compensate": "refund_payment"},
]

# Consensus estate (covers eventual_consistency.py + session_stickiness.py)
CONSENSUS_NODES = [
    {"id": "node-1", "term": 0, "vote_for": None, "log": []},
    {"id": "node-2", "term": 0, "vote_for": None, "log": []},
    {"id": "node-3", "term": 0, "vote_for": None, "log": []},
]

# Multi-Region estate (covers data_locality.py + hot_partition_mitigation.py)
MULTI_REGION_DATA = {
    "region-us": {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]},
    "region-eu": {"users": [{"id": 3, "name": "Charlie"}]},
    "region-ap": {"users": [{"id": 4, "name": "David"}]},
}

# Exactly-Once Delivery estate (covers message_queue.py + idempotency_keys.py)
EXACTLY_ONCE_MESSAGES = [
    {"id": "msg-1", "payload": {"action": "charge", "amount": 100}},
    {"id": "msg-1", "payload": {"action": "charge", "amount": 100}},  # duplicate
    {"id": "msg-2", "payload": {"action": "charge", "amount": 200}},
    {"id": "msg-2", "payload": {"action": "charge", "amount": 200}},  # duplicate
]

# Global Rate Limiting estate (covers rate_limiter.py + throttling.py)
GLOBAL_RATE_LIMITS = {
    "global": {"limit": 1000, "window": 60},
    "regional": {
        "us":  {"limit": 600,  "window": 60},
        "eu":  {"limit": 300,  "window": 60},
        "ap":  {"limit": 100,  "window": 60},
    }
}