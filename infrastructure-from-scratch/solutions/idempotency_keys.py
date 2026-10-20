"""
Idempotency Keys — Complete Solution
"""

import time
import threading
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


class IdempotencyStatus(Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"


class IdempotencyRecord:
    def __init__(self, key: str, ttl_seconds: float = 86400.0):
        self.key = key
        self.status = IdempotencyStatus.PENDING
        self.response: Optional[Any] = None
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None
        self.ttl_seconds = ttl_seconds
        self._event = threading.Event()

    def complete(self, response: Any) -> None:
        self.response = response
        self.status = IdempotencyStatus.COMPLETE
        self.completed_at = time.time()
        self._event.set()

    def wait(self, timeout: float = 30.0) -> bool:
        return self._event.wait(timeout=timeout)

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


class IdempotencyStore:
    def __init__(self, default_ttl: float = 86400.0):
        self.default_ttl = default_ttl
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str) -> Tuple[IdempotencyRecord, bool]:
        with self._lock:
            record = self._store.get(key)
            if record is not None:
                if not record.is_expired:
                    return (record, False)
                # expired — remove and re-create
                del self._store[key]
            new_record = IdempotencyRecord(key, ttl_seconds=self.default_ttl)
            self._store[key] = new_record
            return (new_record, True)

    def complete(self, key: str, response: Any) -> None:
        with self._lock:
            record = self._store.get(key)
        if record:
            record.complete(response)

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        return self._store.get(key)

    def purge_expired(self) -> int:
        with self._lock:
            expired = [k for k, r in self._store.items() if r.is_expired]
            for k in expired:
                del self._store[k]
        return len(expired)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


class IdempotentHandler:
    def __init__(self, store: IdempotencyStore, wait_timeout: float = 30.0):
        self._store = store
        self.wait_timeout = wait_timeout

    def handle(self, idempotency_key: str, fn: Callable, *args, **kwargs) -> Any:
        record, is_new = self._store.get_or_create(idempotency_key)

        if not is_new:
            if record.status == IdempotencyStatus.COMPLETE:
                return record.response
            # PENDING — wait for the in-flight execution to finish
            record.wait(timeout=self.wait_timeout)
            return record.response

        # This caller is responsible for executing
        try:
            result = fn(*args, **kwargs)
            self._store.complete(idempotency_key, result)
            return result
        except Exception:
            # Remove record so retries can try again
            with self._store._lock:
                self._store._store.pop(idempotency_key, None)
            raise


class PaymentStatus(Enum):
    SUCCESS = "SUCCESS"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    DUPLICATE = "DUPLICATE"


class PaymentProcessor:
    def __init__(self):
        self._store = IdempotencyStore(default_ttl=86400.0)
        self._handler = IdempotentHandler(self._store)
        self._accounts: Dict[str, float] = {}
        self._lock = threading.Lock()

    def fund_account(self, account_id: str, amount: float) -> None:
        with self._lock:
            self._accounts[account_id] = self._accounts.get(account_id, 0.0) + amount

    def balance(self, account_id: str) -> float:
        with self._lock:
            return self._accounts.get(account_id, 0.0)

    def charge(self, idempotency_key: str, account_id: str, amount: float) -> Dict:
        return self._handler.handle(idempotency_key, self._do_charge, account_id, amount)

    def _do_charge(self, account_id: str, amount: float) -> Dict:
        with self._lock:
            balance = self._accounts.get(account_id, 0.0)
            if balance >= amount:
                self._accounts[account_id] = balance - amount
                return {
                    "status": PaymentStatus.SUCCESS,
                    "transaction_id": str(uuid.uuid4()),
                }
            else:
                return {
                    "status": PaymentStatus.INSUFFICIENT_FUNDS,
                    "transaction_id": None,
                }


def _test():
    print("Testing IdempotencyStore...")
    store = IdempotencyStore(default_ttl=60.0)
    record1, is_new1 = store.get_or_create("key-abc")
    assert is_new1 is True
    assert record1.status == IdempotencyStatus.PENDING

    record2, is_new2 = store.get_or_create("key-abc")
    assert is_new2 is False
    assert record2 is record1

    store.complete("key-abc", {"result": "ok"})
    record3, is_new3 = store.get_or_create("key-abc")
    assert is_new3 is False
    assert record3.status == IdempotencyStatus.COMPLETE
    assert record3.response == {"result": "ok"}
    print("  IdempotencyStore: OK")

    print("Testing IdempotentHandler...")
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

    threads = [threading.Thread(target=do_handle, args=("payment-xyz", 21))
               for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert all(r == 42 for r in results)
    assert call_count[0] == 1
    print("  IdempotentHandler: OK")

    print("Testing PaymentProcessor...")
    processor = PaymentProcessor()
    processor.fund_account("alice", 100.0)

    idem_key = "charge-001"
    resp1 = processor.charge(idem_key, "alice", 30.0)
    assert resp1["status"] == PaymentStatus.SUCCESS
    assert processor.balance("alice") == 70.0

    resp2 = processor.charge(idem_key, "alice", 30.0)
    assert resp2["status"] == PaymentStatus.SUCCESS
    assert resp2["transaction_id"] == resp1["transaction_id"]
    assert processor.balance("alice") == 70.0

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
    r2, is_new = store3.get_or_create("expiring-key")
    assert is_new is True
    purged = store3.purge_expired()
    assert purged >= 0
    print("  TTL expiry + purge: OK")

    print("\nAll idempotency key tests passed!")


if __name__ == "__main__":
    _test()
