"""
Session Stickiness — From Scratch
====================================
Build session stickiness (a.k.a. session affinity) primitives to understand:
- Sticky cookie routing: load balancer pins a client to one backend
- Consistent hash routing: hash(session_id) → always same backend
- Session state sharing: alternatives to stickiness (Redis-backed sessions)
- Graceful failover: handle backend going down while clients are stuck to it
- Weighted stickiness: route traffic proportionally while maintaining affinity

Session stickiness ensures requests from the same client always reach the
same backend server. Useful when session state is stored in-process (e.g.,
in-memory shopping cart, WebSocket connections, server-side sessions).

Learning Path:
1. Implement consistent-hash-based sticky router
2. Implement a sticky load balancer with cookie-based affinity
3. Implement session failover when a backend goes down
4. Implement a shared session store as the stateless alternative
5. Think about: why is stickiness fragile and when to prefer shared state?
   - Server crash loses in-memory session → user logged out, cart emptied
   - Deployments become harder (drain sticky connections before restart)
   - Load becomes uneven (popular sessions all on one server)
"""

import hashlib
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Step 1: Consistent-Hash Sticky Router
# ---------------------------------------------------------------------------

class Backend:
    """Represents a backend server in the pool."""
    def __init__(self, backend_id: str, address: str):
        self.backend_id = backend_id
        self.address = address
        self.healthy: bool = True
        self.active_sessions: int = 0


class StickyRouter:
    """Route requests to backends using consistent hashing on session ID.

    Same session_id always hashes to the same backend (unless that backend
    goes down, in which case it rehashes to the next healthy backend).

    TODO:
    - add_backend(backend): register a backend
    - remove_backend(backend_id): deregister (e.g., on shutdown)
    - route(session_id): return the backend for this session_id
      Use: int(hashlib.md5(session_id.encode()).hexdigest(), 16) % len(healthy_backends)
      Then pick from sorted(healthy_backends) list for determinism
    - mark_unhealthy(backend_id): exclude backend from routing
    - mark_healthy(backend_id): restore backend to routing pool
    """

    def __init__(self):
        self._backends: Dict[str, Backend] = {}
        self._lock = threading.Lock()

    def add_backend(self, backend: Backend) -> None:
        """Register a backend.

        TODO: self._backends[backend.backend_id] = backend
        """
        # TODO: implement add_backend
        raise NotImplementedError("Implement StickyRouter.add_backend")

    def remove_backend(self, backend_id: str) -> None:
        """Deregister a backend.

        TODO: del self._backends[backend_id]
        """
        # TODO: implement remove_backend
        raise NotImplementedError("Implement StickyRouter.remove_backend")

    def route(self, session_id: str) -> Optional[Backend]:
        """Return the backend for this session using consistent hashing.

        TODO:
        1. Collect healthy backends sorted by backend_id (deterministic order)
        2. If none: return None
        3. index = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % len(healthy)
        4. Return healthy[index]
        """
        # TODO: implement route
        raise NotImplementedError("Implement StickyRouter.route")

    def mark_unhealthy(self, backend_id: str) -> None:
        """Exclude a backend from routing.

        TODO: self._backends[backend_id].healthy = False
        """
        # TODO: implement mark_unhealthy
        raise NotImplementedError("Implement StickyRouter.mark_unhealthy")

    def mark_healthy(self, backend_id: str) -> None:
        """Restore a backend to the pool.

        TODO: self._backends[backend_id].healthy = True
        """
        # TODO: implement mark_healthy
        raise NotImplementedError("Implement StickyRouter.mark_healthy")

    @property
    def healthy_count(self) -> int:
        with self._lock:
            return sum(1 for b in self._backends.values() if b.healthy)


# ---------------------------------------------------------------------------
# Step 2: Sticky Load Balancer with Cookie Affinity
# ---------------------------------------------------------------------------

class StickyLoadBalancer:
    """Load balancer that issues sticky cookies to pin clients to backends.

    On first request: pick least-loaded backend; set cookie "SERVERID=backend_id"
    On subsequent requests: read cookie; route directly to that backend

    TODO:
    - handle_request(session_cookie, session_id): return (backend, new_cookie)
      - If session_cookie is set and backend is healthy: use it
      - Otherwise: pick least-loaded healthy backend; issue new cookie
    - _pick_least_loaded(): return the healthy backend with fewest active sessions
    """

    COOKIE_NAME = "SERVERID"

    def __init__(self, router: StickyRouter):
        self._router = router
        self._backends = router._backends

    def handle_request(self, session_cookie: Optional[str],
                       session_id: str) -> tuple:
        """Route a request; return (backend, cookie_to_set_or_none).

        If cookie is valid and backend is healthy: return (backend, None)  [no new cookie]
        Otherwise: pick a new backend; return (backend, "SERVERID=backend_id")

        TODO:
        1. If session_cookie is set: extract backend_id from cookie value
           Check if self._backends[backend_id] exists and is healthy
           If yes: return (backend, None)
        2. Fall through to _pick_least_loaded()
        3. Return (backend, f"{self.COOKIE_NAME}={backend.backend_id}")
        """
        # TODO: implement handle_request
        raise NotImplementedError("Implement StickyLoadBalancer.handle_request")

    def _pick_least_loaded(self) -> Optional[Backend]:
        """Return the healthy backend with the fewest active_sessions.

        TODO: filter to healthy, sort by active_sessions, return first
        """
        # TODO: implement _pick_least_loaded
        raise NotImplementedError("Implement StickyLoadBalancer._pick_least_loaded")


# ---------------------------------------------------------------------------
# Step 3: Shared Session Store (stateless alternative to stickiness)
# ---------------------------------------------------------------------------

class SessionStore:
    """Redis-like shared session store that removes the need for stickiness.

    Any backend can serve any request by reading session state from the store.
    Sessions are keyed by session_id with a TTL.

    TODO:
    - create_session(data): create a new session; return session_id
    - get_session(session_id): return session data or None if expired/missing
    - update_session(session_id, data): update session data; refresh TTL
    - delete_session(session_id): invalidate session (logout)
    - _prune_expired(): remove expired sessions (lazy or periodic)
    """

    def __init__(self, ttl_seconds: float = 1800.0):
        self.ttl = ttl_seconds
        self._store: Dict[str, Dict] = {}   # session_id → {data, expires_at}
        self._lock = threading.Lock()

    def create_session(self, data: Dict[str, Any]) -> str:
        """Create a new session; return the session_id.

        TODO:
        1. session_id = str(uuid.uuid4())
        2. self._store[session_id] = {"data": data, "expires_at": time.time() + ttl}
        3. Return session_id
        """
        # TODO: implement create_session
        raise NotImplementedError("Implement SessionStore.create_session")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session data or None if expired or not found.

        TODO:
        1. Look up session_id; if not found: return None
        2. If time.time() > expires_at: delete and return None
        3. Return data
        """
        # TODO: implement get_session
        raise NotImplementedError("Implement SessionStore.get_session")

    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data and refresh TTL. Return False if session not found.

        TODO: look up session, update data + expires_at, return True/False
        """
        # TODO: implement update_session
        raise NotImplementedError("Implement SessionStore.update_session")

    def delete_session(self, session_id: str) -> None:
        """Delete a session (logout).

        TODO: remove session_id from self._store
        """
        # TODO: implement delete_session
        raise NotImplementedError("Implement SessionStore.delete_session")

    def _prune_expired(self) -> int:
        """Remove expired sessions; return the count removed."""
        now = time.time()
        with self._lock:
            expired = [sid for sid, s in self._store.items()
                       if s["expires_at"] < now]
            for sid in expired:
                del self._store[sid]
        return len(expired)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Step 4: Failover Handling (discussion)
# ---------------------------------------------------------------------------

"""
Session Stickiness — Trade-offs and Alternatives:

1. When to use stickiness:
   - WebSocket connections (stateful long-lived TCP, must stay on same server)
   - In-memory session caches (avoid Redis round-trip for hot sessions)
   - Stateful computation workers (partial results in-process)

2. Problems with stickiness:
   - Uneven load: some backends become hot if they own popular sessions
   - Failover complexity: when a backend dies, its sessions are lost
   - Blue-green deploys: must drain sticky connections gracefully
   - Horizontal scaling: adding backends doesn't help in-flight sticky sessions

3. Stateless alternative (preferred):
   - Store session in Redis, Memcached, or a fast DB
   - Any backend can serve any request → easy to scale and deploy
   - Trade-off: ~1ms extra latency per request for session lookup
   - Most production systems prefer this approach

4. Cookie-Based Affinity (AWS ALB, nginx upstream):
   - ALB inserts AWSALB cookie with encrypted backend ID
   - nginx: upstream { ... sticky cookie SERVERID; }
   - Duration-based: cookie expires → client might be re-pinned to different server

5. IP Hash Affinity:
   - hash(client_ip) → backend (deterministic without a cookie)
   - Problem: NAT devices share one IP across many users → uneven load
   - Better: hash(X-Forwarded-For) if available
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing StickyRouter...")
    router = StickyRouter()
    router.add_backend(Backend("b1", "10.0.0.1:8080"))
    router.add_backend(Backend("b2", "10.0.0.2:8080"))
    router.add_backend(Backend("b3", "10.0.0.3:8080"))

    # Same session always routes to same backend
    b_first = router.route("session-abc")
    assert b_first is not None
    for _ in range(5):
        assert router.route("session-abc").backend_id == b_first.backend_id

    # When a backend goes down, session rehashes to a different one
    downed_id = b_first.backend_id
    router.mark_unhealthy(downed_id)
    b_after = router.route("session-abc")
    assert b_after is not None and b_after.backend_id != downed_id, \
        "session should rehash after backend goes down"
    router.mark_healthy(downed_id)
    print("  StickyRouter: OK")

    print("Testing StickyLoadBalancer...")
    lb = StickyLoadBalancer(router)
    # First request: no cookie → should receive a new cookie
    b, cookie = lb.handle_request(None, "sess-1")
    assert b is not None
    assert cookie is not None and "SERVERID=" in cookie, \
        f"expected cookie, got {cookie}"

    # Subsequent request with cookie → should stick to same backend
    backend_id = cookie.split("=")[1]
    b2, cookie2 = lb.handle_request(cookie, "sess-1")
    assert b2 is not None and b2.backend_id == backend_id, \
        "should stick to same backend with valid cookie"
    assert cookie2 is None, "no new cookie needed when stickiness is maintained"
    print("  StickyLoadBalancer: OK")

    print("Testing SessionStore...")
    store = SessionStore(ttl_seconds=1.0)
    sid = store.create_session({"user_id": "u1", "cart": []})
    data = store.get_session(sid)
    assert data is not None and data["user_id"] == "u1"

    store.update_session(sid, {"user_id": "u1", "cart": ["item1"]})
    data2 = store.get_session(sid)
    assert data2["cart"] == ["item1"]

    store.delete_session(sid)
    assert store.get_session(sid) is None, "deleted session should not be found"

    # TTL expiry
    sid2 = store.create_session({"user_id": "u2"})
    time.sleep(1.1)
    assert store.get_session(sid2) is None, "expired session should return None"
    print("  SessionStore: OK")

    print("\nAll session stickiness tests passed!")


if __name__ == "__main__":
    _test()
