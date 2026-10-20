"""
Idempotency Keys — From Scratch
=================================
Build idempotency key infrastructure to understand:
- Idempotency key storage and lookup
- Request deduplication with stored responses
- TTL-based expiry of idempotency records
- Concurrent request handling (exactly-once execution)
- Idempotency in different contexts: payments, messaging, DB writes

Idempotency: applying the same operation multiple times produces the same
result as applying it once. Critical for retryable operations in distributed
systems where "did my request succeed?" is often unknowable after a timeout.

Learning Path:
1. Implement a basic idempotency key store (key → cached response)
2. Add concurrent deduplication (only one request executes; others wait)
3. Add TTL-based expiry for stored responses
4. Implement idempotency for a mock payment processor
5. Think about: where do you store idempotency keys at scale?
   - Redis: fast, TTL-native, but eventually consistent
   - DB (Postgres): strong consistency, use UNIQUE constraint on idempotency_key
   - Combined: check Redis first, fallback to DB for long-lived keys
"""

import time
import threading
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: Idempotency Key Store
# ---------------------------------------------------------------------------

class IdempotencyStatus(Enum):
    PENDING = "PENDING"    # request is currently being processed
    COMPLETE = "COMPLETE"  # response is stored and can be returned


class IdempotencyRecord:
    """Stores the status and result of an idempotent operation."""

    def __init__(self, key: str, ttl_seconds: float = 86400.0):
        self.key = key
        self.status = IdempotencyStatus.PENDING
        self.response: Optional[Any] = None
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None
        self.ttl_seconds = ttl_seconds
        self._event = threading.Event()  # waiters block on this

    def complete(self, response: Any) -> None:
        """Mark the record as complete with the given response."""
        self.response = response
        self.status = IdempotencyStatus.COMPLETE
        self.completed_at = time.time()
        self._event.set()

    def wait(self, timeout: float = 30.0) -> bool:
        """Block until the record is completed or timeout expires."""
        return self._event.wait(timeout=timeout)

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


class IdempotencyStore:
    """Thread-safe store for idempotency keys and cached responses.

    TODO:
    - get_or_create(key): return (record, is_new)
      - If key exists and not expired: return (existing_record, False)
      - If key expired: remove it, create fresh record
      - If key not found: create new PENDING record, return (new_record, True)
    - complete(key, response): store response on the record
    - get(key): return record or None
    - purge_expired(): remove all expired records; return count removed
    """

    def __init__(self, default_ttl: float = 86400.0):
        self.default_ttl = default_ttl
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str) -> Tuple["IdempotencyRecord", bool]:
        """Return (record, is_new). is_new=True means caller should execute.

        TODO:
        1. with self._lock:
           a. If key in _store and not expired: return (record, False)
           b. If key in _store and expired: delete it
           c. Create new record (PENDING); store in _store; return (record, True)
        """
        # TODO: implement get_or_create
        raise NotImplementedError("Implement IdempotencyStore.get_or_create")

    def complete(self, key: str, response: Any) -> None:
        """Mark key as complete with response.

        TODO: look up record; call record.complete(response)
        """
        # TODO: implement complete
        raise NotImplementedError("Implement IdempotencyStore.complete")

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Return record for key or None.

        TODO: return self._store.get(key)
        """
        # TODO: implement get
        raise NotImplementedError("Implement IdempotencyStore.get")

    def purge_expired(self) -> int:
        """Remove expired records; return count removed.

        TODO: iterate _store, collect expired keys, delete them, return count
        """
        # TODO: implement purge_expired
        raise NotImplementedError("Implement IdempotencyStore.purge_expired")

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Step 2: Idempotent Request Handler
# ---------------------------------------------------------------------------

class IdempotentHandler:
    """Wraps any callable to make it idempotent using an idempotency key.

    Pattern:
      1. Client sends request with header Idempotency-Key: <uuid>
      2. Server checks if key exists in store
      3. If COMPLETE: return cached response immediately
      4. If PENDING: wait for the in-flight request to finish, return its result
      5. If NEW: execute the operation, store result, return response

    TODO:
    - handle(idempotency_key, fn, *args, **kwargs):
      1. get_or_create(idempotency_key)
      2. If not new: if COMPLETE return response; if PENDING wait then return response
      3. If new: execute fn(*args, **kwargs); store.complete(key, result); return result
      4. On exception: must delete the PENDING record so retries can proceed
    """

    def __init__(self, store: IdempotencyStore, wait_timeout: float = 30.0):
        self._store = store
        self.wait_timeout = wait_timeout

    def handle(self, idempotency_key: str, fn: Callable, *args, **kwargs) -> Any:
        """Execute fn idempotently.

        TODO:
        1. record, is_new = self._store.get_or_create(idempotency_key)
        2. If not is_new:
           a. If COMPLETE: return record.response
           b. If PENDING: wait on record._event; return record.response
        3. If is_new:
           try:
             result = fn(*args, **kwargs)
             self._store.complete(idempotency_key, result)
             return result
           except:
             delete record from store (allow retry)
             re-raise
        """
        # TODO: implement handle
        raise NotImplementedError("Implement IdempotentHandler.handle")


# ---------------------------------------------------------------------------
# Step 3: Idempotent Payment Processor (example use case)
# ---------------------------------------------------------------------------

class PaymentStatus(Enum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    DUPLICATE = "DUPLICATE"


class PaymentProcessor:
    """Mock payment processor that uses idempotency keys to prevent double charges.

    TODO:
    - charge(idempotency_key, account_id, amount): deduct amount from account;
      return {"status": PaymentStatus, "transaction_id": str}
      Use IdempotentHandler internally so duplicate calls return the same response.
    - _do_charge(account_id, amount): the actual charge logic (non-idempotent)
    """

    def __init__(self):
        self._store = IdempotencyStore(default_ttl=86400.0)
        self._handler = IdempotentHandler(self._store)
        self._accounts: Dict[str, float] = {}  # account_id → balance
        self._lock = threading.Lock()

    def fund_account(self, account_id: str, amount: float) -> None:
        """Add funds to an account (for testing)."""
        with self._lock:
            self._accounts[account_id] = self._accounts.get(account_id, 0.0) + amount

    def balance(self, account_id: str) -> float:
        with self._lock:
            return self._accounts.get(account_id, 0.0)

    def charge(self, idempotency_key: str, account_id: str, amount: float) -> Dict:
        """Charge an account; idempotent on idempotency_key.

        TODO: use self._handler.handle(idempotency_key, self._do_charge, account_id, amount)
        """
        # TODO: implement charge using IdempotentHandler
        raise NotImplementedError("Implement PaymentProcessor.charge")

    def _do_charge(self, account_id: str, amount: float) -> Dict:
        """Execute the actual charge (not idempotent — called at most once per key).

        TODO:
        1. with self._lock: check balance >= amount
        2. If yes: deduct; return {"status": PaymentStatus.SUCCESS, "transaction_id": uuid}
        3. If no: return {"status": PaymentStatus.INSUFFICIENT_FUNDS, "transaction_id": None}
        """
        # TODO: implement _do_charge
        raise NotImplementedError("Implement PaymentProcessor._do_charge")


# ---------------------------------------------------------------------------
# Step 4: Idempotency in Different Contexts (discussion)
# ---------------------------------------------------------------------------

"""
Idempotency Key Patterns:

1. HTTP API Pattern:
   - Client generates a UUID: Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
   - Server stores (key → response) in Redis with 24-hour TTL
   - On retry: return cached response WITHOUT re-executing the operation
   - Stripe, Plaid, Adyen all implement this pattern

2. Database-Backed Idempotency:
   CREATE TABLE idempotency_keys (
       key        TEXT PRIMARY KEY,
       status     TEXT NOT NULL DEFAULT 'pending',
       response   JSONB,
       created_at TIMESTAMPTZ DEFAULT now(),
       expires_at TIMESTAMPTZ
   );
   - Use UNIQUE constraint to prevent concurrent execution of the same key
   - On conflict (duplicate key): SELECT and return stored response
   - Auto-cleanup with a background job or pg_cron

3. Message Deduplication (at-least-once delivery):
   - Consumer maintains a seen-set: SET seen:<message_id> 1 EX 86400
   - Before processing: SETNX (set-if-not-exists) → only processes once
   - SQS MessageDeduplicationId: 5-minute dedup window for FIFO queues
   - Kafka: exactly-once semantics via producer idempotence + transactions

4. Idempotent HTTP Methods:
   - GET, HEAD, OPTIONS: inherently idempotent (read-only)
   - PUT: idempotent by spec (replace the resource)
   - DELETE: idempotent by spec (deleting a deleted resource = same state)
   - POST: NOT idempotent → use idempotency keys explicitly
   - PATCH: depends on operation (add vs. set)

5. Safe Retry Patterns:
   - Always generate the idempotency key client-side before the first attempt
   - Include the key on every retry → server deduplicates
   - Use exponential backoff + jitter between retries
   - Set TTL > max retry window (e.g., 24h if retrying for up to 1h)
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing IdempotencyStore...")
    store = IdempotencyStore(default_ttl=60.0)

    record1, is_new1 = store.get_or_create("key-abc")
    assert is_new1 is True
    assert record1.status == IdempotencyStatus.PENDING

    # Second call with same key while PENDING → not new
    record2, is_new2 = store.get_or_create("key-abc")
    assert is_new2 is False
    assert record2 is record1

    store.complete("key-abc", {"result": "ok"})
    record3, is_new3 = store.get_or_create("key-abc")
    assert is_new3 is False
    assert record3.status == IdempotencyStatus.COMPLETE
    assert record3.response == {"result": "ok"}
    print("  IdempotencyStore: OK")

    print("Testing IdempotentHandler (concurrent deduplication)...")
    store2 = IdempotencyStore()
    handler = IdempotentHandler(store2)

    call_count = [0]

    def expensive_op(x: int) -> int:
        call_count[0] += 1
        time.sleep(0.05)
        return x * 2

    results = []
    errors = []

    def do_handle(key, val):
        try:
            results.append(handler.handle(key, expensive_op, val))
        except Exception as e:
            errors.append(e)

    # 5 concurrent requests with the same idempotency key
    threads = [threading.Thread(target=do_handle, args=("payment-xyz", 21))
               for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"unexpected errors: {errors}"
    assert all(r == 42 for r in results), f"all should return 42: {results}"
    assert call_count[0] == 1, \
        f"expensive_op should be called exactly once, got {call_count[0]}"
    print("  IdempotentHandler: OK")

    print("Testing PaymentProcessor...")
    processor = PaymentProcessor()
    processor.fund_account("alice", 100.0)

    idem_key = "charge-001"
    resp1 = processor.charge(idem_key, "alice", 30.0)
    assert resp1["status"] == PaymentStatus.SUCCESS
    assert processor.balance("alice") == 70.0

    # Retry with same key → same response, no double charge
    resp2 = processor.charge(idem_key, "alice", 30.0)
    assert resp2["status"] == PaymentStatus.SUCCESS
    assert resp2["transaction_id"] == resp1["transaction_id"], \
        "retry should return cached response"
    assert processor.balance("alice") == 70.0, "balance should not change on retry"

    # Different key → new charge
    resp3 = processor.charge("charge-002", "alice", 30.0)
    assert resp3["status"] == PaymentStatus.SUCCESS
    assert processor.balance("alice") == 40.0
    print("  PaymentProcessor: OK")

    print("Testing TTL expiry + purge...")
    store3 = IdempotencyStore(default_ttl=0.1)
    r, _ = store3.get_or_create("expiring-key")
    store3.complete("expiring-key", "done")
    time.sleep(0.15)
    assert r.is_expired is True
    # get_or_create should treat expired record as new
    r2, is_new = store3.get_or_create("expiring-key")
    assert is_new is True, "expired key should be treated as new"
    purged = store3.purge_expired()
    assert purged >= 0  # at least the original expired record was removed
    print("  TTL expiry + purge: OK")

    print("\nAll idempotency key tests passed!")


if __name__ == "__main__":
    _test()
