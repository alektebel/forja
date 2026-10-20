"""
Session Stickiness — Complete Solution
"""

import hashlib
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class Backend:
    def __init__(self, backend_id: str, address: str):
        self.backend_id = backend_id
        self.address = address
        self.healthy: bool = True
        self.active_sessions: int = 0


class StickyRouter:
    def __init__(self):
        self._backends: Dict[str, Backend] = {}
        self._lock = threading.Lock()

    def add_backend(self, backend: Backend) -> None:
        with self._lock:
            self._backends[backend.backend_id] = backend

    def remove_backend(self, backend_id: str) -> None:
        with self._lock:
            del self._backends[backend_id]

    def route(self, session_id: str) -> Optional[Backend]:
        with self._lock:
            healthy = sorted(
                [b for b in self._backends.values() if b.healthy],
                key=lambda b: b.backend_id
            )
        if not healthy:
            return None
        index = int(hashlib.md5(session_id.encode()).hexdigest(), 16) % len(healthy)
        return healthy[index]

    def mark_unhealthy(self, backend_id: str) -> None:
        with self._lock:
            self._backends[backend_id].healthy = False

    def mark_healthy(self, backend_id: str) -> None:
        with self._lock:
            self._backends[backend_id].healthy = True

    @property
    def healthy_count(self) -> int:
        with self._lock:
            return sum(1 for b in self._backends.values() if b.healthy)


class StickyLoadBalancer:
    COOKIE_NAME = "SERVERID"

    def __init__(self, router: StickyRouter):
        self._router = router
        self._backends = router._backends

    def handle_request(self, session_cookie: Optional[str],
                       session_id: str) -> tuple:
        if session_cookie:
            parts = session_cookie.split("=", 1)
            if len(parts) == 2 and parts[0] == self.COOKIE_NAME:
                backend_id = parts[1]
                backend = self._backends.get(backend_id)
                if backend and backend.healthy:
                    return (backend, None)

        backend = self._pick_least_loaded()
        if backend is None:
            return (None, None)
        return (backend, f"{self.COOKIE_NAME}={backend.backend_id}")

    def _pick_least_loaded(self) -> Optional[Backend]:
        with self._router._lock:
            healthy = [b for b in self._backends.values() if b.healthy]
        if not healthy:
            return None
        return min(healthy, key=lambda b: b.active_sessions)


class SessionStore:
    def __init__(self, ttl_seconds: float = 1800.0):
        self.ttl = ttl_seconds
        self._store: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def create_session(self, data: Dict[str, Any]) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._store[session_id] = {
                "data": data,
                "expires_at": time.time() + self.ttl
            }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._store[session_id]
                return None
            return entry["data"]

    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        with self._lock:
            if session_id not in self._store:
                return False
            self._store[session_id]["data"] = data
            self._store[session_id]["expires_at"] = time.time() + self.ttl
            return True

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def _prune_expired(self) -> int:
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


def _test():
    print("Testing StickyRouter...")
    router = StickyRouter()
    router.add_backend(Backend("b1", "10.0.0.1:8080"))
    router.add_backend(Backend("b2", "10.0.0.2:8080"))
    router.add_backend(Backend("b3", "10.0.0.3:8080"))

    b_first = router.route("session-abc")
    assert b_first is not None
    for _ in range(5):
        assert router.route("session-abc").backend_id == b_first.backend_id

    downed_id = b_first.backend_id
    router.mark_unhealthy(downed_id)
    b_after = router.route("session-abc")
    assert b_after is not None and b_after.backend_id != downed_id
    router.mark_healthy(downed_id)
    print("  StickyRouter: OK")

    print("Testing StickyLoadBalancer...")
    lb = StickyLoadBalancer(router)
    b, cookie = lb.handle_request(None, "sess-1")
    assert b is not None
    assert cookie is not None and "SERVERID=" in cookie

    backend_id = cookie.split("=")[1]
    b2, cookie2 = lb.handle_request(cookie, "sess-1")
    assert b2 is not None and b2.backend_id == backend_id
    assert cookie2 is None
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
    assert store.get_session(sid) is None

    sid2 = store.create_session({"user_id": "u2"})
    time.sleep(1.1)
    assert store.get_session(sid2) is None
    print("  SessionStore: OK")

    print("\nAll session stickiness tests passed!")


if __name__ == "__main__":
    _test()
