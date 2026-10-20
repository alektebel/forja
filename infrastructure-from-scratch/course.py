"""Infrastructure From Scratch — course manifest.

20 stages covering the core building blocks of distributed systems.
Each stage is a template (stub with raise NotImplementedError) and a solution
(working implementation). check_NN.py verifies correctness; mutate_NN.py plants
≥34 mutations per stage.
"""

import sys
import os

COURSE_DIR = os.path.dirname(os.path.abspath(__file__))

STAGES = [
    {"id": 1, "title": "Load Balancer", "file": "load_balancer.py",
     "difficulty": "simple",
     "desc": "Distribute requests across identical backends; hide failures; round-robin, weighted, consistent-hash"},
    {"id": 2, "title": "CDN — Simple", "file": "cdn_caching.py",
     "difficulty": "simple",
     "desc": "Serve static/semistatic content close to the user; reduce origin load; cache policies"},
    {"id": 3, "title": "Object Storage — Simple", "file": "cache.py",  # placeholder
     "difficulty": "simple",
     "desc": "Store arbitrary blobs, durable, scalable; replace the filesystem"},
    {"id": 4, "title": "Reverse Proxy — Simple", "file": "url_shortener.py",  # placeholder
     "difficulty": "simple",
     "desc": "TLS termination, routing, compression, request buffering"},
    {"id": 5, "title": "API Gateway — Simple", "file": "request_batching.py",  # placeholder
     "difficulty": "simple",
     "desc": "Aggregate routes, auth, rate limiting, transform requests/responses"},
    {"id": 6, "title": "Caching Layer (Redis) — Moderate", "file": "cache.py",
     "difficulty": "moderate",
     "desc": "LRU/LFU eviction, cache-aside, TTL, stampede protection, write-through"},
    {"id": 7, "title": "Message Queue — Moderate", "file": "message_queue.py",
     "difficulty": "moderate",
     "desc": "At-least-once delivery, retries, backoff, DLQ, idempotency"},
    {"id": 8, "title": "Rate Limiter — Moderate", "file": "rate_limiter.py",
     "difficulty": "moderate",
     "desc": "Token bucket, sliding window, distributed rate limiting"},
    {"id": 9, "title": "Read Replicas — Moderate", "file": "leaderboard.py",  # placeholder
     "difficulty": "moderate",
     "desc": "Scale reads, accept bounded lag, handle failover"},
    {"id": 10, "title": "Service Discovery — Moderate", "file": "consistent_hash.py",
     "difficulty": "moderate",
     "desc": "Find backends when IPs move; health-check, register, deregister"},
    {"id": 11, "title": "Database Sharding — Complex", "file": "hot_partition_mitigation.py",
     "difficulty": "complex",
     "desc": "Spread writes across machines; consistent hash to avoid rebalance storms"},
    {"id": 12, "title": "Event-Driven Architecture — Complex", "file": "eventual_consistency.py",
     "difficulty": "complex",
     "desc": "Decouple producers from consumers; order preservation; at-least-once vs exactly-once"},
    {"id": 13, "title": "Search Index — Complex", "file": "data_locality.py",  # placeholder
     "difficulty": "complex",
     "desc": "Full-text search, relevance scoring, faceted navigation, autocomplete"},
    {"id": 14, "title": "Service Mesh — Complex", "file": "edge_computing.py",  # placeholder
     "difficulty": "complex",
     "desc": "mTLS between pods, traffic splitting, retries, observability — transparently"},
    {"id": 15, "title": "Cache Invalidation — Complex", "file": "capacity_planner.py",  # placeholder
     "difficulty": "complex",
     "desc": "When data changes, which copies to evict? TTL, write-through, stampede"},
    {"id": 16, "title": "Sagas — Extremely Complex", "file": "connection_pooling.py",  # placeholder
     "difficulty": "extremely-complex",
     "desc": "Multi-service business transactions without 2PC; compensating actions"},
    {"id": 17, "title": "Consensus (Raft/Paxos) — Extremely Complex", "file": "session_stickiness.py",  # placeholder
     "difficulty": "extremely-complex",
     "desc": "Agree on a log despite network partitions and crashes"},
    {"id": 18, "title": "Multi-Region Active-Active — Extremely Complex", "file": "idempotency_keys.py",  # placeholder
     "difficulty": "extremely-complex",
     "desc": "Write anywhere, replicate everywhere, resolve conflicts"},
    {"id": 19, "title": "Exactly-Once Delivery — Extremely Complex", "file": "throttling.py",  # placeholder
     "difficulty": "extremely-complex",
     "desc": "No duplicates, no losses, at any scale"},
    {"id": 20, "title": "Global Rate Limiting at Scale — Extremely Complex", "file": "cdn_caching.py",  # placeholder
     "difficulty": "extremely-complex",
     "desc": "One quota across regions; sub-second, consistent, no SPOF"},
]

ALL = list(range(1, 21))