"""Infrastructure From Scratch — course manifest.

Eighteen graded stages, one per topic module: each stage is a stub in
`templates/<module>.py` (methods raise `NotImplementedError`) with a working
`_test()` and a complete implementation in `solutions/<module>.py`. The check
below loads the template, runs the module's own `_test()` against it, and
asserts the surface the stage's title names — so a stub reports TODO, a wrong
implementation reports FAIL, and the solution reports PASS.

    python3 codecraft/cli.py run infrastructure-from-scratch

`run_all.py` / `check_NN.py` exercise the same contract from the shell, and
`mutate_NN.py` replants anchored mistakes in the solution and proves the check
catches every one.
"""

import importlib.util
import os

from codecraft.api import stage

HERE = os.path.dirname(os.path.abspath(__file__))

TITLE = "Infrastructure From Scratch"
DESCRIPTION = (
    "The building blocks of distributed systems, one module each: consistent "
    "hashing, caching, CDN and rate limiting, batching, pooling, stickiness, "
    "circuit breaking, queues, leaderboards, hot partitions, locality, "
    "eventual consistency, idempotency, edge computing, capacity math."
)
LEVEL = "intermediate"
ORDER = 40


def _module(filename):
    """Import `templates/<filename>` under a name that cannot collide."""
    path = os.path.join(HERE, "templates", filename)
    spec = importlib.util.spec_from_file_location(
        "infra_" + filename[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tested(filename, surface, probe=None):
    """Run the module's own `_test()`, then name the classes the title promises.

    `_test()` is the module's full behaviour suite (5–21 assertions per file);
    the surface tuple is what `check_NN.py` re-verifies so a check can never
    pass a module that renamed the mechanism away. `probe` is a behaviour
    assert that does not depend on wall time — it fails on the stub even before
    `_test()` reaches its first sleep.
    """
    mod = _module(filename)
    for name in surface:
        assert hasattr(mod, name), f"{filename} must define {name}"
    if probe is not None:
        probe(mod)
    mod._test()

def check_1():
    def probe(m):
        assert m.base62_encode(0) == "0"
        assert m.base62_encode(62) == "10"
        assert m.base62_decode(m.base62_encode(12345)) == 12345
    _tested("url_shortener.py",
            ("URLStore", "URLShortener", "base62_encode", "base62_decode"),
            probe)


# --- stage 2 -----------------------------------------------------------------------
def check_2():
    def probe(m):
        ring = m.HashRing(virtual_nodes=50)
        ring.add_node("A")
        ring.add_node("B")
        assert ring.get_node("key:1") == ring.get_node("key:1")
        rh = m.RendezvousHash()
        rh.add_node("X")
        rh.add_node("Y")
        assert rh.get_node("k") in ("X", "Y")
    _tested("consistent_hash.py", ("HashRing", "RendezvousHash"), probe)


# --- stage 3 -----------------------------------------------------------------------
def check_3():
    def probe(m):
        c = m.LRUCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        assert c.get("b") == -1, "b was LRU and must have been evicted"
        assert c.get("a") == 1, "a was touched and must have survived"
    _tested("cache.py",
            ("LRUCache", "TTLCache", "CacheAsideStore", "StampedeProtectedCache"),
            probe)


# --- stage 4 -----------------------------------------------------------------------
def check_4():
    def probe(m):
        cache = m.EdgeCache()
        assert cache.put("/p", {"v": 1}, "max-age=60") is True
        assert cache.put("/p", {"v": 1}, "no-store") is False
    _tested("cdn_caching.py",
            ("EdgeCache", "OriginShield", "normalize_cache_key"), probe)


# --- stage 5 -----------------------------------------------------------------------
def check_5():
    def probe(m):
        lim = m.FixedWindowRateLimiter(limit=2, window_seconds=60)
        assert [lim.is_allowed("u") for _ in range(3)] == [True, True, False]
        tb = m.TokenBucketRateLimiter(capacity=2, refill_rate=1.0)
        assert tb.is_allowed("v") and tb.is_allowed("v")
        assert tb.is_allowed("v") is False
    _tested("rate_limiter.py",
            ("FixedWindowRateLimiter", "TokenBucketRateLimiter",
             "SlidingWindowLogRateLimiter", "SlidingWindowCounterRateLimiter"),
            probe)


# --- stage 6 -----------------------------------------------------------------------
def check_6():
    def probe(m):
        b = m.LeakyBucket(capacity=2.0, drain_rate=1.0)
        assert b.add(1.0) is True
        assert b.add(1.0) is True
        assert b.add(1.0) is False, "bucket is full and cannot drain instantly"
    _tested("throttling.py",
            ("LeakyBucket", "DelayThrottler", "ThrottledWorker"), probe)


# --- stage 7 -----------------------------------------------------------------------
def check_7():
    def probe(m):
        seen = []
        sb = m.SizeBatcher(batch_size=2, flush_fn=lambda b: seen.append(b[:]))
        assert sb.add(1) is None
        assert sb.add(2) == [1, 2]
        assert sb.add(3) is None
        assert sb.flush() == [3]
    _tested("request_batching.py",
            ("SizeBatcher", "TimeBatcher", "DataLoader", "PipelineBatcher"),
            probe)


# --- stage 8 -----------------------------------------------------------------------
def check_8():
    def probe(m):
        made = [0]

        def factory():
            made[0] += 1
            return m.Connection(conn_id=f"c{made[0]}")
        pool = m.ConnectionPool(factory=factory, min_size=1, max_size=2,
                                acquire_timeout=0.2)
        assert pool.idle_count == 1
        c = pool.acquire()
        assert c.execute("SELECT 1") == "result:SELECT 1"
        pool.release(c)
        assert pool.active_count == 0
    _tested("connection_pooling.py",
            ("Connection", "ConnectionPool", "PooledConnection",
             "PoolExhaustedError"), probe)


# --- stage 9 -----------------------------------------------------------------------
def check_9():
    def probe(m):
        router = m.StickyRouter()
        router.add_backend(m.Backend("b1", "10.0.0.1:8080"))
        router.add_backend(m.Backend("b2", "10.0.0.2:8080"))
        b = router.route("session-1")
        assert b is not None
        assert router.route("session-1").backend_id == b.backend_id
    _tested("session_stickiness.py",
            ("Backend", "StickyRouter", "StickyLoadBalancer", "SessionStore"),
            probe)


# --- stage 10 ----------------------------------------------------------------------
def check_10():
    def probe(m):
        cb = m.CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        assert cb.state == m.CircuitState.CLOSED
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
            except ConnectionError:
                pass
        assert cb.state == m.CircuitState.OPEN
        try:
            cb.call(lambda: "ok")
            assert False, "open breaker must refuse"
        except m.CircuitBreakerOpenError:
            pass
        q = m.BoundedQueue(capacity=1)
        assert q.put("a") is True
        assert q.put("b") is False
    _tested("circuit_breaker.py",
            ("CircuitBreaker", "CircuitState", "CircuitBreakerOpenError",
             "Bulkhead", "BoundedQueue", "with_timeout", "retry"), probe)


# --- stage 11 ----------------------------------------------------------------------
def check_11():
    def probe(m):
        assert m.exponential_backoff(3, base=1.0, cap=60.0, jitter=False) == 8.0
        assert m.exponential_backoff(10, base=1.0, cap=60.0, jitter=False) == 60.0
        q = m.MessageQueue()
        mid = q.enqueue({"task": "x"})
        assert q.queue_depth == 1
        msg = q.dequeue()
        assert msg.body["task"] == "x"
        q.ack(msg.id)
    _tested("message_queue.py",
            ("Message", "MessageQueue", "QueueWorker", "exponential_backoff"),
            probe)


# --- stage 12 ----------------------------------------------------------------------
def check_12():
    def probe(m):
        ss = m.SortedSet()
        ss.zadd("a", 10)
        ss.zadd("b", 20)
        assert ss.zrevrank("b") == 0
        assert ss.zscore("a") == 10
        assert ss.zincrby("a", 15) == 25
        assert ss.zrevrank("a") == 0
    _tested("leaderboard.py", ("SortedSet", "Leaderboard",
                               "WindowedLeaderboard", "LeaderboardEntry"),
            probe)


# --- stage 13 ----------------------------------------------------------------------
def check_13():
    def probe(m):
        w = m.ScatteredWriter(num_shards=3)
        r = m.ScatterGatherReader(w)
        store = {}
        for i in range(6):
            w.write("hot:x", f"v{i}", store)
        assert len(r.read("hot:x", store)) == 6
        d = m.HotKeyDetector(window_seconds=60.0)
        for _ in range(15):
            d.record("viral")
        assert "viral" in [k for k, _ in d.get_hot_keys(threshold=10)]
    _tested("hot_partition_mitigation.py",
            ("ScatteredWriter", "ScatterGatherReader", "HotKeyDetector",
             "TimeBucketedStore"), probe)


# --- stage 14 ----------------------------------------------------------------------
def check_14():
    def probe(m):
        router = m.ShardRouter(num_shards=4)
        store = m.CoLocationStore(router)
        store.put("user", "u1", "user:1", {"name": "Alice"})
        store.put("order", "o1", "user:1", {"product": "book"})
        assert store.get("user", "u1", "user:1") == {"name": "Alice"}
        assert len(store.get_all("order", "user:1")) == 1
    _tested("data_locality.py",
            ("ShardRouter", "CoLocationStore", "DenormalizedOrderView",
             "LocalityAwareCache"), probe)


# --- stage 15 ----------------------------------------------------------------------
def check_15():
    def probe(m):
        c1, c2 = m.GCounter("n1"), m.GCounter("n2")
        c1.increment()
        c2.increment()
        c2.increment()
        c1.merge(c2)
        assert c1.value() == 3
        reg = m.LWWRegister()
        reg.write("x", "new", timestamp=2.0)
        reg.write("x", "stale", timestamp=1.0)
        assert reg.read("x") == "new"
        va, vb = m.VectorClock("A"), m.VectorClock("B")
        va.tick()
        vb.update(va.copy())
        assert va.happened_before(vb) is True
        assert vb.happened_before(va) is False
    _tested("eventual_consistency.py",
            ("GCounter", "LWWRegister", "VectorClock", "Replica",
             "EventuallyConsistentStore"), probe)


# --- stage 16 ----------------------------------------------------------------------
def check_16():
    def probe(m):
        store = m.IdempotencyStore(default_ttl=60.0)
        r1, new1 = store.get_or_create("k")
        assert new1 is True
        r2, new2 = store.get_or_create("k")
        assert new2 is False
        assert r2 is r1
        assert r1.status == m.IdempotencyStatus.PENDING
        pp = m.PaymentProcessor()
        pp.fund_account("a", 50.0)
        resp = pp.charge("c1", "a", 20.0)
        assert resp["status"] == m.PaymentStatus.SUCCESS
        assert pp.balance("a") == 30.0
        assert pp.charge("c1", "a", 20.0)["transaction_id"] == resp["transaction_id"]
        assert pp.balance("a") == 30.0
    _tested("idempotency_keys.py",
            ("IdempotencyStore", "IdempotencyStatus", "IdempotentHandler",
             "PaymentProcessor", "PaymentStatus"), probe)


# --- stage 17 ----------------------------------------------------------------------
def check_17():
    def probe(m):
        router = m.LatencyRouter()
        router.add_node(m.EdgeNode("us", "us", 5.0))
        router.add_node(m.EdgeNode("eu", "eu", 50.0))
        assert router.route({"us": 5.0, "eu": 50.0}).node_id == "us"
        ab = m.ABTestRouter()
        ab.add_experiment("cta", ["control", "variant"], [0.5, 0.5])
        assert ab.get_variant("cta", "u1") == ab.get_variant("cta", "u1")
    _tested("edge_computing.py",
            ("EdgeNode", "LatencyRouter", "Request", "Response",
             "EdgeMiddlewarePipeline", "ABTestRouter", "EdgeRuntime"), probe)


# --- stage 18 ----------------------------------------------------------------------
def check_18():
    def probe(m):
        r = m.compute_qps(dau=1_000_000, actions_per_user_per_day=10)
        assert r.average_qps > 0
        assert abs(r.peak_qps - r.average_qps * m.PEAK_MULTIPLIER) < 1
        assert m.human_bytes(1024 * 1024 * 1024) .endswith("GB") or \
               m.human_bytes(1024 * 1024 * 1024).endswith("GiB")
    _tested("capacity_planner.py",
            ("compute_qps", "compute_storage", "compute_bandwidth",
             "cache_impact", "estimate_servers", "human_bytes", "human_num"),
            probe)


STAGES = [
    stage(1, file="url_shortener.py",
          title="URL shortener — base62 codes, TTL store, click stats",
          tags=["simple", "encoding", "storage"],
          action="Implement base62 encode/decode, a URLStore with TTL expiry "
                 "and hit stats, and a URLShortener that mints codes and resolves them.",
          predict="why must the code counter advance before encoding, never after?",
          hints=["digits = 0-9, A-Z, a-z; 62 becomes '10', not a new digit",
                 "expiry: compare the saved timestamp on read, drop lazily",
                 "shorten() must be collision-free: counter ids never repeat"],
          check=check_1, solution="solutions/url_shortener.py"),
    stage(2, file="consistent_hash.py",
          title="Consistent hashing — virtual-node ring, rendezvous",
          tags=["simple", "hashing", "routing"],
          action="Implement HashRing with virtual nodes (add/remove/get_node/"
                 "distribution/migration_count) and RendezvousHash.",
          predict="adding one node to an N-node ring — how many keys move?",
          hints=["bisect over sorted (position, node) pairs, wrap at the end",
                 "virtual nodes: hash f'{node}#vnode{i}' 150 times per server",
                 "rendezvous: score every node per key, take the max"],
          check=check_2, solution="solutions/consistent_hash.py"),
    stage(3, file="cache.py",
          title="Cache — LRU, TTL, cache-aside, stampede protection",
          tags=["moderate", "caching", "locking"],
          action="Implement LRUCache (dict + doubly-linked list, O(1) get/put), "
                 "TTLCache, CacheAsideStore, and StampedeProtectedCache.",
          predict="can a get() be O(1) while keeping true recency order?",
          hints=["move-to-head on read, evict from tail",
                 "TTL is checked lazily on get, never by a sweeper",
                 "stampede: one in-flight fetch per key, others wait on its event"],
          check=check_3, solution="solutions/cache.py"),
    stage(4, file="cdn_caching.py",
          title="CDN — edge cache, origin shield, cache-key normalization",
          tags=["moderate", "caching", "http"],
          action="Implement EdgeCache honouring Cache-Control (private/no-store/"
                 "max-age, surrogate keys, purge_by_key), OriginShield collapsing "
                 "concurrent origin fetches, and normalize_cache_key.",
          predict="two objects sharing a surrogate key — how many does one purge remove?",
          hints=["parse directives into a dict, then branch on no-store/private",
                 "shield: per-key lock, first thread fetches, rest read its result",
                 "normalize: strip tracking params, sort what remains"],
          check=check_4, solution="solutions/cdn_caching.py"),
    stage(5, file="rate_limiter.py",
          title="Rate limiting — fixed window, token bucket, sliding window",
          tags=["moderate", "backpressure", "http"],
          action="Implement FixedWindow, TokenBucket (capacity + refill_rate), "
                 "SlidingWindowLog and SlidingWindowCounter limiters.",
          predict="why does fixed window allow a 2× burst at the boundary?",
          hints=["window key: int(now // window_seconds)",
                 "token bucket: refill = (now - last) * rate, cap at capacity",
                 "sliding counter = weighted current + previous window"],
          check=check_5, solution="solutions/rate_limiter.py"),
    stage(6, file="throttling.py",
          title="Throttling — leaky bucket, delay throttle, worker drain",
          tags=["moderate", "backpressure", "scheduling"],
          action="Implement LeakyBucket (capacity + drain_rate), DelayThrottler "
                 "(minimum interval per key) and ThrottledWorker (rate-limited task pool).",
          predict="token bucket lets bursts through — which of these never does?",
          hints=["drain lazily: level -= (now - last_drain) * rate, floor 0",
                 "delay throttle records last slot per key, next slot = last + 1/rate",
                 "worker: one dispatch thread, results keyed by task id"],
          check=check_6, solution="solutions/throttling.py"),
    stage(7, file="request_batching.py",
          title="Request batching — size/time windows, DataLoader, pipeline",
          tags=["moderate", "throughput", "threads"],
          action="Implement SizeBatcher, TimeBatcher (window flush thread), "
                 "DataLoader (dedupe same-window keys into one fetch) and PipelineBatcher.",
          predict="three threads ask for key 'user:1' in one window — how many fetches?",
          hints=["add() returns the flushed batch when len hits batch_size",
                 "DataLoader: one Event per waiter, one dispatch timer per window",
                 "stop() must flush what is still pending in the buffer"],
          check=check_7, solution="solutions/request_batching.py"),
    stage(8, file="connection_pooling.py",
          title="Connection pooling — acquire/release, exhaustion, idle eviction",
          tags=["moderate", "resources", "locking"],
          action="Implement ConnectionPool (min/max size, acquire_timeout, "
                 "idle_timeout eviction), PooledConnection as context manager, "
                 "PoolExhaustedError naming the pool.",
          predict="why does acquire() wait on a condition instead of spinning?",
          hints=["pre-fill min_size in __init__",
                 "exhaustion: wait until deadline, then raise naming max_size",
                 "release() notifies one waiter; eviction drops idle > timeout"],
          check=check_8, solution="solutions/connection_pooling.py"),
    stage(9, file="session_stickiness.py",
          title="Session stickiness — sticky routing, cookies, session store",
          tags=["moderate", "sessions", "routing"],
          action="Implement StickyRouter (hash → backend, health-aware), "
                 "StickyLoadBalancer (SERVERID cookie affinity) and SessionStore "
                 "(create/get/update/delete with TTL).",
          predict="a backend dies mid-session — what does the user lose, and when?",
          hints=["route() skips unhealthy backends and remaps that session",
                 "cookie present → honour it; absent → pick and mint one",
                 "session TTL checked on read, lazily"],
          check=check_9, solution="solutions/session_stickiness.py"),
    stage(10, file="circuit_breaker.py",
          title="Circuit breaking — timeout, retry, breaker, bulkhead",
          tags=["complex", "resilience", "threads"],
          action="Implement with_timeout and retry decorators, the CLOSED→OPEN→"
                 "HALF-OPEN CircuitBreaker, per-tenant Bulkhead semaphores, and "
                 "BoundedQueue backpressure counting rejections.",
          predict="what must a half-open breaker do on its first success?",
          hints=["failure_threshold trips; recovery_timeout admits one probe",
                 "CircuitBreakerOpenError names the breaker state",
                 "bulkhead: one Semaphore per tenant, acquire(timeout=...)"],
          check=check_10, solution="solutions/circuit_breaker.py"),
    stage(11, file="message_queue.py",
          title="Message queue — retries, backoff, DLQ, idempotent delivery",
          tags=["complex", "queues", "delivery"],
          action="Implement Message, MessageQueue (enqueue/dequeue/ack/nack with "
                 "visibility, retry+backoff, dead-letter queue, idempotency-key "
                 "dedup) and exponential_backoff(base, cap, jitter).",
          predict="nack with retries left — is the old message id ever seen again?",
          hints=["backoff: min(cap, base * 2**attempt), jitter optional",
                 "deliver_at gates dequeue; attempts increment on requeue",
                 "max_attempts exhausted → dlq_depth grows, queue_depth shrinks"],
          check=check_11, solution="solutions/message_queue.py"),
    stage(12, file="leaderboard.py",
          title="Leaderboards — sorted set, ranks, windows, rank delta",
          tags=["complex", "data-structure", "ranking"],
          action="Implement SortedSet (zadd/zscore/zincrby/zrevrank/zrevrange/"
                 "zrangebyscore/zcard), Leaderboard with snapshots and rank "
                 "delta, and WindowedLeaderboard.",
          predict="why does a rank delta need a snapshot at all?",
          hints=["keep (score, member) pairs sorted; bisect to rank in O(log n)",
                 "ties: same score → earlier member ranks first",
                 "delta = snapshot_rank - current_rank"],
          check=check_12, solution="solutions/leaderboard.py"),
    stage(13, file="hot_partition_mitigation.py",
          title="Hot partitions — scattered writes, hot-key detection, buckets",
          tags=["complex", "sharding", "time-series"],
          action="Implement ScatteredWriter (salted copies across N shards) with "
                 "ScatterGatherReader, HotKeyDetector (sliding window counts), "
                 "and TimeBucketedStore (bucketed range reads + aggregation).",
          predict="why scatter writes but not reads — what does a reader pay?",
          hints=["scatter key = f'{key}#{i}' for i in range(num_shards)",
                 "detector keeps per-key timestamp lists; window trims on read",
                 "bucket id = int(timestamp // bucket_size_seconds)"],
          check=check_13, solution="solutions/hot_partition_mitigation.py"),
    stage(14, file="data_locality.py",
          title="Data locality — shard routing, co-location, denormalized views",
          tags=["complex", "sharding", "modelling"],
          action="Implement ShardRouter (partition key → shard), CoLocationStore "
                 "(related entities on one shard), DenormalizedOrderView (pre-"
                 "joined writes fan out) and LocalityAwareCache.",
          predict="which read does denormalization make free — and which write it makes expensive?",
          hints=["route by hash(partition_key) % num_shards",
                 "get_all(entity, pk) reads the single shard pk maps to",
                 "update_user_name touches every order row holding the copy"],
          check=check_14, solution="solutions/data_locality.py"),
    stage(15, file="eventual_consistency.py",
          title="Eventual consistency — CRDTs, vector clocks, read repair",
          tags=["complex", "consistency", "replication"],
          action="Implement GCounter (merge by per-node max), LWWRegister "
                 "(timestamp wins), VectorClock with happened_before, Replica, "
                 "and EventuallyConsistentStore with quorum writes and read repair.",
          predict="two replicas tick their own clock — is either's write before the other's?",
          hints=["merge: {k: max(a.get(k,0), b.get(k,0)) for k in a|b}",
                 "happened_before: every component ≤ and at least one <",
                 "read repair: quorum winner written back to lagging replicas"],
          check=check_15, solution="solutions/eventual_consistency.py"),
    stage(16, file="idempotency_keys.py",
          title="Idempotency keys — dedup store, single execution, payments",
          tags=["complex", "delivery", "transactions"],
          action="Implement IdempotencyStore (get_or_create/complete, TTL, "
                 "purge_expired), IdempotentHandler (concurrent callers → exactly "
                 "one execution), and PaymentProcessor (idempotent charges).",
          predict="five threads POST the same charge key — how many debits happen?",
          hints=["PENDING holder executes; late arrivals wait on its result event",
                 "is_new must be False while a record is COMPLETE or IN_PROGRESS",
                 "charge() replays the stored transaction_id for the same key"],
          check=check_16, solution="solutions/idempotency_keys.py"),
    stage(17, file="edge_computing.py",
          title="Edge computing — latency routing, middleware, A/B, runtime",
          tags=["complex", "edge", "routing"],
          action="Implement LatencyRouter (nearest healthy PoP), "
                 "EdgeMiddlewarePipeline (auth/geo chain), ABTestRouter "
                 "(deterministic hashed buckets) and EdgeRuntime (per-function "
                 "CPU limit, EdgeFunctionError naming the offender).",
          predict="why must the A/B bucket hash the user id, not the request?",
          hints=["route by client latency, skipping mark_unhealthy nodes",
                 "pipeline: middleware calls next_handler or short-circuits a Response",
                 "runtime: run function in a worker, enforce cpu_limit_ms"],
          check=check_17, solution="solutions/edge_computing.py"),
    stage(18, file="capacity_planner.py",
          title="Capacity planning — QPS, storage, bandwidth, server estimates",
          tags=["moderate", "estimation", "arithmetic"],
          action="Implement compute_qps (DAU × actions → average + peak), "
                 "compute_storage (write QPS × payload × replication per day), "
                 "compute_bandwidth, cache_impact, estimate_servers (Little's "
                 "Law) and the human_bytes/human_num formatters.",
          predict="cache hit ratio goes up 10% — what happens to DB QPS?",
          hints=["SECONDS_PER_DAY = 86400; peak = average × PEAK_MULTIPLIER",
                 "servers = ceil(peak_qps × avg_latency_ms / 1000 / threads_per_server)",
                 "reduction_percent is (1 - db_qps_after/db_qps_before) × 100"],
          check=check_18, solution="solutions/capacity_planner.py"),
]

ALL = [st.id for st in STAGES]
