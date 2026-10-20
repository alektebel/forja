"""
Connection Pooling — From Scratch
===================================
Build connection pooling to understand:
- Pool lifecycle: create, acquire, release, retire
- Max pool size, min pool size, idle timeout
- Connection validation (health check before use)
- Connection queue: callers wait when all connections are in use
- Pool metrics: active, idle, wait queue depth, acquisition latency

Why pooling? Creating a TCP connection + TLS handshake + DB auth takes
10-100ms. Pooling amortizes that cost across many requests.

Learning Path:
1. Implement a basic connection pool with acquire/release
2. Add max-pool-size with a waiting queue
3. Add idle-timeout to retire stale connections
4. Add health-check validation before each use
5. Think about: HikariCP, pgBouncer, and connection pool sizing formulae
   - Pool size ≈ number of CPU cores on DB server (Little's Law)
   - Too large → context-switching overhead; Too small → queue depth grows
"""

import time
import uuid
import threading
from typing import Any, Callable, Dict, Optional


# ---------------------------------------------------------------------------
# Simulated Connection
# ---------------------------------------------------------------------------

class Connection:
    """Simulates a database or network connection."""

    def __init__(self, conn_id: Optional[str] = None,
                 connect_fn: Optional[Callable] = None):
        self.conn_id = conn_id or str(uuid.uuid4())[:8]
        self.created_at: float = time.time()
        self.last_used_at: float = time.time()
        self._healthy: bool = True
        if connect_fn:
            connect_fn(self)  # simulate handshake

    def execute(self, query: str) -> str:
        """Simulate query execution."""
        if not self._healthy:
            raise ConnectionError(f"Connection {self.conn_id} is broken")
        self.last_used_at = time.time()
        return f"result:{query}"

    def close(self) -> None:
        self._healthy = False

    @property
    def is_healthy(self) -> bool:
        return self._healthy


class PoolExhaustedError(Exception):
    """Raised when the pool is exhausted and no connection becomes available."""
    pass


# ---------------------------------------------------------------------------
# Step 1: Basic Connection Pool
# ---------------------------------------------------------------------------

class ConnectionPool:
    """A connection pool with acquire/release, max size, and idle timeout.

    Lifecycle:
      - Connections are created lazily (on first acquire up to max_size)
      - Released connections go back to the idle pool
      - Idle connections older than idle_timeout are closed and removed
      - If pool is exhausted, callers wait up to acquire_timeout seconds

    TODO:
    1. Implement acquire(): return an idle healthy connection or create a new one;
       block if at max capacity (up to acquire_timeout)
    2. Implement release(conn): return connection to idle pool (or close if pool full)
    3. Implement _evict_idle(): close and remove connections idle > idle_timeout
    4. Implement close_all(): close every connection and reset pool
    """

    def __init__(self, factory: Callable[[], Connection],
                 min_size: int = 1,
                 max_size: int = 10,
                 acquire_timeout: float = 5.0,
                 idle_timeout: float = 60.0,
                 validate_fn: Optional[Callable[[Connection], bool]] = None):
        """
        Args:
            factory: callable that creates a new Connection
            min_size: minimum number of connections to pre-create
            max_size: maximum number of connections in the pool
            acquire_timeout: seconds to wait for a connection before raising
            idle_timeout: seconds a connection may sit idle before being closed
            validate_fn: optional callable(conn) → bool; True means connection is OK
        """
        self._factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self.idle_timeout = idle_timeout
        self._validate = validate_fn or (lambda c: c.is_healthy)

        self._idle: list = []         # idle connections available to acquire
        self._active: set = set()     # connections currently checked out
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._total = 0               # total connections created (idle + active)

        # Pre-create min_size connections
        for _ in range(min_size):
            conn = self._factory()
            self._idle.append(conn)
            self._total += 1

    def acquire(self) -> Connection:
        """Acquire a connection from the pool.

        TODO:
        1. Try to get an idle connection (validate it; discard if invalid)
        2. If no idle connections and total < max_size: create a new connection
        3. If at max_size: wait on self._not_empty condition (up to acquire_timeout)
        4. If still no connection after timeout: raise PoolExhaustedError
        5. Mark connection as active (add to self._active)
        6. Return the connection
        """
        # TODO: implement acquire
        raise NotImplementedError("Implement ConnectionPool.acquire")

    def release(self, conn: Connection) -> None:
        """Return a connection to the idle pool (or close if over min_size and idle).

        TODO:
        1. Remove from self._active
        2. If conn is healthy: append to self._idle; notify waiters
        3. If conn is unhealthy: decrement self._total (connection is lost)
        """
        # TODO: implement release
        raise NotImplementedError("Implement ConnectionPool.release")

    def _evict_idle(self) -> int:
        """Close and remove connections that have been idle longer than idle_timeout.

        Returns number of connections evicted.

        TODO:
        1. Find connections in self._idle where (now - last_used_at) > idle_timeout
           AND self._total > self.min_size (keep at least min_size connections)
        2. Close evicted connections; remove from self._idle; decrement self._total
        3. Return evict count
        """
        # TODO: implement _evict_idle
        raise NotImplementedError("Implement ConnectionPool._evict_idle")

    def close_all(self) -> None:
        """Close all connections and reset pool state.

        TODO:
        1. Close all idle connections
        2. Close all active connections (force-close)
        3. Reset self._idle, self._active, self._total
        """
        # TODO: implement close_all
        raise NotImplementedError("Implement ConnectionPool.close_all")

    @property
    def idle_count(self) -> int:
        with self._lock:
            return len(self._idle)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    @property
    def total_count(self) -> int:
        with self._lock:
            return self._total


# ---------------------------------------------------------------------------
# Step 2: Context Manager Support
# ---------------------------------------------------------------------------

class PooledConnection:
    """Context manager wrapper for acquiring and auto-releasing a connection.

    Usage:
        with PooledConnection(pool) as conn:
            result = conn.execute("SELECT 1")

    TODO:
    - __enter__: call pool.acquire(); return conn
    - __exit__: call pool.release(conn); handle exceptions cleanly
    """

    def __init__(self, pool: ConnectionPool):
        self._pool = pool
        self._conn: Optional[Connection] = None

    def __enter__(self) -> Connection:
        """Acquire a connection from the pool.

        TODO: self._conn = self._pool.acquire(); return self._conn
        """
        # TODO: implement __enter__
        raise NotImplementedError("Implement PooledConnection.__enter__")

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Release the connection back to the pool.

        TODO: if self._conn: self._pool.release(self._conn)
        """
        # TODO: implement __exit__
        raise NotImplementedError("Implement PooledConnection.__exit__")


# ---------------------------------------------------------------------------
# Step 3: Pool Sizing & Metrics (discussion)
# ---------------------------------------------------------------------------

"""
Connection Pool Sizing:

1. Little's Law: N = λ × W
   - N = average number in-flight (pool size needed)
   - λ = arrival rate (requests/second)
   - W = average service time (seconds per query)
   - Example: 500 QPS, 10ms avg query → N = 500 * 0.01 = 5 connections
   
2. DB-Side Limit:
   - Each DB connection consumes ~5-10MB of server memory
   - PostgreSQL default max_connections = 100; each uses a backend process
   - Rule of thumb: pool_size ≤ num_CPU_cores on DB server * 2
   - HikariCP default: 10 connections

3. Tiered Pools:
   - Read pool → point at read replicas (larger pool, for SELECTs)
   - Write pool → point at primary (smaller pool, for INSERT/UPDATE/DELETE)
   - Separate pools prevent write saturation from starving reads

4. pgBouncer (connection pooler for PostgreSQL):
   - Session mode: one server connection per client session
   - Transaction mode: server connection released after each transaction (recommended)
   - Statement mode: released after each statement (restrictive)
   - Allows thousands of application connections → few DB connections

5. Metrics to monitor:
   - pool.active_count: connections in use (should be < max_size)
   - pool.idle_count: spare connections
   - pool.wait_queue_depth: callers waiting (should be 0 normally)
   - pool.acquire_latency_p99: time to get a connection (should be < 1ms)
   - pool.timeout_rate: fraction of acquires that timeout (should be 0)
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing ConnectionPool...")
    created = [0]

    def make_conn():
        created[0] += 1
        return Connection(conn_id=f"conn-{created[0]}")

    pool = ConnectionPool(factory=make_conn, min_size=2, max_size=5,
                          acquire_timeout=1.0, idle_timeout=60.0)

    assert pool.idle_count == 2, f"expected 2 idle, got {pool.idle_count}"
    assert pool.active_count == 0

    # Acquire 3 connections
    c1 = pool.acquire()
    c2 = pool.acquire()
    c3 = pool.acquire()
    assert pool.active_count == 3
    assert pool.idle_count == 0

    # Execute queries
    assert c1.execute("SELECT 1") == "result:SELECT 1"

    # Release one back
    pool.release(c1)
    assert pool.idle_count == 1

    # Release rest
    pool.release(c2)
    pool.release(c3)
    assert pool.active_count == 0
    print("  ConnectionPool: OK")

    print("Testing PooledConnection context manager...")
    with PooledConnection(pool) as conn:
        result = conn.execute("SELECT 42")
        assert result == "result:SELECT 42"
    assert pool.active_count == 0, "connection should be released after context exit"
    print("  PooledConnection: OK")

    print("Testing pool exhaustion...")
    pool2 = ConnectionPool(factory=make_conn, min_size=1, max_size=2,
                           acquire_timeout=0.2)
    a = pool2.acquire()
    b = pool2.acquire()
    try:
        pool2.acquire()   # should time out
        assert False, "should raise PoolExhaustedError"
    except PoolExhaustedError:
        pass
    pool2.release(a)
    pool2.release(b)
    print("  Pool exhaustion / timeout: OK")

    print("Testing idle eviction...")
    pool3 = ConnectionPool(factory=make_conn, min_size=1, max_size=3,
                           idle_timeout=0.05)
    c = pool3.acquire()
    pool3.release(c)
    assert pool3.idle_count >= 1
    time.sleep(0.1)
    evicted = pool3._evict_idle()
    # min_size=1, so at most total-1 should be evicted
    assert pool3.idle_count <= pool3.min_size, \
        f"expected idle ≤ min_size after eviction, got {pool3.idle_count}"
    print("  Idle eviction: OK")

    print("\nAll connection pooling tests passed!")


if __name__ == "__main__":
    _test()
