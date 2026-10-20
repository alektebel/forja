"""
Message Queue — Complete Solution
"""

import time
import uuid
import threading
import random
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Message:
    id: str
    body: Any
    attempts: int = 0
    max_attempts: int = 5
    enqueued_at: float = field(default_factory=time.time)
    deliver_at: float = field(default_factory=time.time)
    idempotency_key: Optional[str] = None


def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0,
                         jitter: bool = True) -> float:
    raw_delay = min(cap, base * (2 ** attempt))
    return random.uniform(0, raw_delay) if jitter else raw_delay


class MessageQueue:
    def __init__(self, visibility_timeout: float = 30.0, dedup_ttl: float = 300.0):
        self.visibility_timeout = visibility_timeout
        self.dedup_ttl = dedup_ttl
        self._queue: List[Message] = []
        self._dlq: List[Message] = []
        self._in_flight: Dict[str, tuple] = {}
        self._seen_ids: Dict[str, float] = {}
        self._idempotency_keys: Dict[str, str] = {}  # idem_key → msg_id
        self._lock = threading.Lock()

    def enqueue(self, body: Any, idempotency_key: Optional[str] = None,
                delay_seconds: float = 0.0) -> str:
        with self._lock:
            self._clean_seen_ids()
            if idempotency_key and idempotency_key in self._idempotency_keys:
                return self._idempotency_keys[idempotency_key]
            msg_id = str(uuid.uuid4())
            msg = Message(
                id=msg_id,
                body=body,
                deliver_at=time.time() + delay_seconds,
                idempotency_key=idempotency_key,
            )
            self._queue.append(msg)
            if idempotency_key:
                self._idempotency_keys[idempotency_key] = msg_id
            return msg_id

    def dequeue(self) -> Optional[Message]:
        with self._lock:
            now = time.time()
            for i, msg in enumerate(self._queue):
                if msg.deliver_at <= now:
                    self._queue.pop(i)
                    msg.attempts += 1
                    self._in_flight[msg.id] = (msg, now + self.visibility_timeout)
                    return msg
            return None

    def ack(self, message_id: str) -> None:
        with self._lock:
            entry = self._in_flight.pop(message_id, None)
            if entry:
                msg, _ = entry
                self._seen_ids[message_id] = time.time()

    def nack(self, message_id: str, retry: bool = True) -> None:
        with self._lock:
            entry = self._in_flight.pop(message_id, None)
            if not entry:
                return
            msg, _ = entry
            if retry and msg.attempts < msg.max_attempts:
                delay = exponential_backoff(msg.attempts - 1, jitter=True)
                msg.deliver_at = time.time() + delay
                self._queue.append(msg)
            else:
                self._dlq.append(msg)

    def requeue_timed_out(self) -> int:
        with self._lock:
            now = time.time()
            timed_out = [
                msg_id for msg_id, (msg, deadline) in self._in_flight.items()
                if deadline < now
            ]
        count = 0
        for msg_id in timed_out:
            self.nack(msg_id, retry=True)
            count += 1
        return count

    def _clean_seen_ids(self) -> None:
        now = time.time()
        cutoff = now - self.dedup_ttl
        self._seen_ids = {k: v for k, v in self._seen_ids.items() if v > cutoff}

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def dlq_depth(self) -> int:
        return len(self._dlq)

    def drain_dlq(self) -> List[Message]:
        with self._lock:
            messages = list(self._dlq)
            self._dlq.clear()
            return messages


class QueueWorker:
    def __init__(self, queue: MessageQueue, handler_fn: Callable[[Message], None],
                 poll_interval: float = 0.1):
        self._queue = queue
        self._handler = handler_fn
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.processed = 0
        self.failed = 0

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        while self._running:
            self._queue.requeue_timed_out()
            msg = self._queue.dequeue()
            if msg is None:
                time.sleep(self._poll_interval)
                continue
            try:
                self._handler(msg)
                self._queue.ack(msg.id)
                self.processed += 1
            except Exception:
                self._queue.nack(msg.id)
                self.failed += 1


def _test():
    print("Testing exponential_backoff...")
    assert exponential_backoff(0, base=1.0, cap=60.0, jitter=False) == 1.0
    assert exponential_backoff(1, base=1.0, cap=60.0, jitter=False) == 2.0
    assert exponential_backoff(5, base=1.0, cap=60.0, jitter=False) == 32.0
    assert exponential_backoff(10, base=1.0, cap=60.0, jitter=False) == 60.0
    print("  exponential_backoff: OK")

    print("Testing MessageQueue (basic)...")
    q = MessageQueue()
    msg_id = q.enqueue({"task": "send_email", "to": "user@example.com"})
    assert q.queue_depth == 1
    msg = q.dequeue()
    assert msg is not None
    assert msg.body["to"] == "user@example.com"
    assert q.queue_depth == 0
    q.ack(msg.id)
    print("  basic enqueue/dequeue/ack: OK")

    print("Testing idempotency dedup...")
    q2 = MessageQueue()
    q2.enqueue("task", idempotency_key="idem-1")
    q2.enqueue("task", idempotency_key="idem-1")
    assert q2.queue_depth == 1
    m = q2.dequeue()
    q2.ack(m.id)
    print("  idempotency dedup: OK")

    print("Testing retry + DLQ...")
    q3 = MessageQueue()
    q3.enqueue("failing_task")
    msg = q3.dequeue()
    assert msg is not None
    # Exhaust retries; override deliver_at so backoff doesn't delay the test
    while msg.attempts < msg.max_attempts:
        if msg.attempts == msg.max_attempts - 1:
            q3.nack(msg.id, retry=False)  # final failure → DLQ
            break
        q3.nack(msg.id, retry=True)
        # Force the requeued message to be immediately ready
        with q3._lock:
            for m in q3._queue:
                m.deliver_at = 0.0
        msg = q3.dequeue()
        assert msg is not None
    assert q3.dlq_depth >= 1
    print("  retry + DLQ: OK")

    print("\nAll message queue tests passed!")


if __name__ == "__main__":
    _test()
