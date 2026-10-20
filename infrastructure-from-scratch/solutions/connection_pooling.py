"""
Connection Pooling — Complete Solution
"""

import time
import uuid
import threading
from typing import Any, Callable, Dict, Optional


class Connection:
    def __init__(self, conn_id: Optional[str] = None,
                 connect_fn: Optional[Callable] = None):
        self.conn_id = conn_id or str(uuid.uuid4())[:8]
        self.created_at: float = time.time()
        self.last_used_at: float = time.time()
        self._healthy: bool = True
        if connect_fn:
            connect_fn(self)

    def execute(self, query: str) -> str:
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
    pass


class ConnectionPool:
    def __init__(self, factory: Callable[[], Connection],
                 min_size: int = 1,
                 max_size: int = 10,
                 acquire_timeout: float = 5.0,
                 idle_timeout: float = 60.0,
                 validate_fn: Optional[Callable[[Connection], bool]] = None):
        self._factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self.idle_timeout = idle_timeout
        self._validate = validate_fn or (lambda c: c.is_healthy)

        self._idle: list = []
        self._active: set = set()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._total = 0

        for _ in range(min_size):
            conn = self._factory()
            self._idle.append(conn)
            self._total += 1

    def acquire(self) -> Connection:
        deadline = time.time() + self.acquire_timeout
        with self._not_empty:
            while True:
                # Try to get a valid idle connection
                while self._idle:
                    conn = self._idle.pop()
                    if self._validate(conn):
                        self._active.add(conn)
                        return conn
                    else:
                        self._total -= 1  # discard invalid connection

                # Create a new connection if under max
                if self._total < self.max_size:
                    conn = self._factory()
                    self._total += 1
                    self._active.add(conn)
                    return conn

                # Wait for a connection to be released
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise PoolExhaustedError(
                        f"Pool exhausted: {self._total}/{self.max_size} connections in use")
                self._not_empty.wait(timeout=remaining)

    def release(self, conn: Connection) -> None:
        with self._not_empty:
            self._active.discard(conn)
            if conn.is_healthy:
                self._idle.append(conn)
                self._not_empty.notify()
            else:
                self._total -= 1

    def _evict_idle(self) -> int:
        now = time.time()
        evicted = 0
        with self._lock:
            to_keep = []
            for conn in self._idle:
                age = now - conn.last_used_at
                if age > self.idle_timeout and self._total - evicted > self.min_size:
                    conn.close()
                    evicted += 1
                    self._total -= 1
                else:
                    to_keep.append(conn)
            self._idle = to_keep
        return evicted

    def close_all(self) -> None:
        with self._lock:
            for conn in self._idle:
                conn.close()
            for conn in list(self._active):
                conn.close()
            self._idle = []
            self._active = set()
            self._total = 0

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


class PooledConnection:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool
        self._conn: Optional[Connection] = None

    def __enter__(self) -> Connection:
        self._conn = self._pool.acquire()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._conn:
            self._pool.release(self._conn)
        return False


def _test():
    print("Testing ConnectionPool...")
    created = [0]

    def make_conn():
        created[0] += 1
        return Connection(conn_id=f"conn-{created[0]}")

    pool = ConnectionPool(factory=make_conn, min_size=2, max_size=5,
                          acquire_timeout=1.0, idle_timeout=60.0)
    assert pool.idle_count == 2
    assert pool.active_count == 0

    c1 = pool.acquire()
    c2 = pool.acquire()
    c3 = pool.acquire()
    assert pool.active_count == 3
    assert pool.idle_count == 0
    assert c1.execute("SELECT 1") == "result:SELECT 1"

    pool.release(c1)
    assert pool.idle_count == 1

    pool.release(c2)
    pool.release(c3)
    assert pool.active_count == 0
    print("  ConnectionPool: OK")

    print("Testing PooledConnection context manager...")
    with PooledConnection(pool) as conn:
        result = conn.execute("SELECT 42")
        assert result == "result:SELECT 42"
    assert pool.active_count == 0
    print("  PooledConnection: OK")

    print("Testing pool exhaustion...")
    pool2 = ConnectionPool(factory=make_conn, min_size=1, max_size=2,
                           acquire_timeout=0.2)
    a = pool2.acquire()
    b = pool2.acquire()
    try:
        pool2.acquire()
        assert False
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
    pool3._evict_idle()
    assert pool3.idle_count <= pool3.min_size
    print("  Idle eviction: OK")

    print("\nAll connection pooling tests passed!")


if __name__ == "__main__":
    _test()
